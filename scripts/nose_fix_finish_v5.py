# -*- coding: utf-8 -*-
"""Finish from step3/4 checkpoint: strip inner shell, verify holes, radome, export."""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
# Prefer step4 (has glass) or step3
SRC = os.path.join(PROJ, "public", "models", "c919_nose_fix_step4.blend")
if not os.path.isfile(SRC):
    SRC = os.path.join(PROJ, "public", "models", "c919_nose_fix_step3.blend")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")


def log(*a):
    print("FINISH", *a, flush=True)


def strip_inner(obj, solidify=0.12):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    # Estimate outer radius per Y band from faces with +radial normal
    # Delete faces whose center is inward of outer envelope by > solidify*0.4
    # First collect candidate outer points
    outer_pts = []
    for f in bm.faces:
        c = f.calc_center_median()
        n = f.normal.normalized()
        radial = Vector((c.x, 0, c.z))
        if radial.length < 1e-6:
            continue
        radial.normalize()
        if n.dot(radial) > 0.2:
            outer_pts.append(c)
    # Build simple envelope: for each face, compare r to max r of outer faces near same Y
    from collections import defaultdict as dd

    bands = dd(list)
    for c in outer_pts:
        bands[round(c.y, 1)].append(math.sqrt(c.x * c.x + c.z * c.z))
    band_r = {k: max(vs) for k, vs in bands.items() if vs}

    kill = []
    for f in list(bm.faces):
        c = f.calc_center_median()
        n = f.normal.normalized()
        radial = Vector((c.x, 0, c.z))
        r = radial.length
        if r < 1e-6:
            radial = Vector((0, 0, 1))
        else:
            radial.normalize()
        score = n.dot(radial)
        if c.y > 19.2:
            score = max(score, n.dot(Vector((0, 1, 0))))
        # strongly inward normal
        if score < -0.15:
            kill.append(f)
            continue
        # deep inside envelope
        key = round(c.y, 1)
        rmax = band_r.get(key) or band_r.get(round(c.y - 0.1, 1)) or band_r.get(round(c.y + 0.1, 1))
        if rmax and r < rmax - solidify * 0.45 and score < 0.5:
            kill.append(f)

    kill = list(set(kill))
    log("strip kill", len(kill), "of", len(bm.faces))
    if kill and len(kill) < len(bm.faces) * 0.75:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    # Remove doubles / clean
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    obj.data.update()
    be = sum(1 for e in bm.edges if e.is_boundary)
    log("after strip faces", len(bm.faces), "boundary", be)
    bm.free()


def hole_check(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    samples = {
        "WS_R": Vector((0.55, 17.3, 1.35)),
        "WS_L": Vector((-0.55, 17.3, 1.35)),
        "SW_R": Vector((1.65, 16.3, 0.6)),
        "SW_L": Vector((-1.65, 16.3, 0.6)),
        "tip": Vector((0.0, 19.8, 0.0)),
        "cheek": Vector((1.5, 18.5, 0.2)),
    }
    out = {}
    for name, p in samples.items():
        if name == "tip":
            hit = bvh.ray_cast(p + Vector((0, 1.5, 0)), Vector((0, -1, 0)))
        else:
            radial = Vector((p.x, 0, p.z))
            radial.normalize()
            hit = bvh.ray_cast(p + radial * 1.2, -radial)
        out[name] = "SOLID" if hit[0] else "OPEN"
        log("check", name, out[name], hit[3] if hit[0] else None)
    ys = [v.co.y for v in bm.verts]
    out["y"] = [min(ys), max(ys)]
    out["faces"] = len(bm.faces)
    out["boundary"] = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return out


def round_radome(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tip_y = max(v.co.y for v in bm.verts)
    if tip_y < 19.5:
        log("skip radome", tip_y)
        bm.free()
        return
    tip_verts = [v for v in bm.verts if v.co.y > tip_y - 0.4]
    ring = [v for v in tip_verts if tip_y - 0.3 < v.co.y < tip_y - 0.1] or [
        v for v in tip_verts if v.co.y < tip_y - 0.05
    ]
    mx = sum(v.co.x for v in ring) / max(len(ring), 1)
    mz = sum(v.co.z for v in ring) / max(len(ring), 1)
    ry = sum(v.co.y for v in ring) / max(len(ring), 1)
    R = sum(math.sqrt((v.co.x - mx) ** 2 + (v.co.z - mz) ** 2) for v in ring) / max(len(ring), 1)
    R = max(min(R, 0.5), 0.18)
    for v in tip_verts:
        r = math.sqrt((v.co.x - mx) ** 2 + (v.co.z - mz) ** 2)
        if r > R * 1.15:
            continue
        dy = math.sqrt(max(0.0, R * R - min(r, R) ** 2)) * 0.8
        if v.co.y >= ry - 0.01:
            v.co.y = ry + dy
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    log("radome done", tip_y, R)


def render_views(prefix):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    cam = bpy.data.objects.get("NoseFixCam")
    if not cam:
        cd = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cd)
        bpy.context.collection.objects.link(cam)
    sc.camera = cam
    tip = Vector((0, 19.9, 0.55))
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        hide = (
            o.name == "Nose"
            or "2-287" in o.name
            or o.name.startswith("切割体")
            or o.name.startswith("WS_")
            or o.name.startswith("SW_")
            or o.name == "REF_玻璃"
        )
        o.hide_render = hide
        try:
            o.hide_set(hide)
        except Exception:
            pass
    cut = bpy.data.objects.get("Nose_开窗")
    if cut:
        cut.hide_render = False
        try:
            cut.hide_set(False)
        except Exception:
            pass
    for tag, eye, lens in (
        ("front", tip + Vector((0, 6, 0.4)), 55),
        ("side", tip + Vector((7, -1, 0.8)), 50),
        ("45", tip + Vector((4.5, 4, 1.5)), 50),
    ):
        cam.location = eye
        cam.data.lens = lens
        cam.rotation_euler = (tip - eye).normalized().to_track_quat("-Z", "Y").to_euler()
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        sc.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)


def main():
    log("open", SRC)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    cut = bpy.data.objects.get("Nose_开窗")
    if not cut:
        raise RuntimeError("no Nose_开窗")
    log("faces before", len(cut.data.polygons))

    strip_inner(cut)
    checks = hole_check(cut)
    with open(os.path.join(LOG_DIR, "finish_holes.json"), "w") as f:
        json.dump(checks, f, indent=2)

    # If still solid at WS, try deleting faces whose centers fall inside pane AABB
    opens = [k for k, v in checks.items() if k.startswith("W") and v == "OPEN"]
    if len(opens) < 2:
        log("FALLBACK face punch by pane AABB (smoothness may suffer)")
        panes = {
            "WS_R": (0.05, 1.25, 16.75, 17.85, 0.95, 1.70),
            "WS_L": (-1.25, -0.05, 16.75, 17.85, 0.95, 1.70),
            "SW_R": (1.30, 2.00, 15.65, 16.95, -0.15, 1.20),
            "SW_L": (-2.00, -1.30, 15.65, 16.95, -0.15, 1.20),
        }
        bm = bmesh.new()
        bm.from_mesh(cut.data)
        kill = []
        for f in bm.faces:
            c = f.calc_center_median()
            for x0, x1, y0, y1, z0, z1 in panes.values():
                if x0 <= c.x <= x1 and y0 <= c.y <= y1 and z0 <= c.z <= z1:
                    kill.append(f)
                    break
        log("aabb kill", len(kill))
        if kill:
            bmesh.ops.delete(bm, geom=kill, context="FACES")
            # dissolve jagged: limited dissolve
            try:
                bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(5), verts=list(bm.verts), edges=list(bm.edges))
            except Exception as e:
                log("dissolve", e)
            bm.to_mesh(cut.data)
            cut.data.update()
        bm.free()
        checks = hole_check(cut)
        with open(os.path.join(LOG_DIR, "finish_holes_after_punch.json"), "w") as f:
            json.dump(checks, f, indent=2)

    render_views("step3_cut")

    # Ensure glass/cabin visible
    for n in ("C919_玻璃", "C919_窗框", "CockpitCabin"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(False)
            o.hide_render = False
    for n in ("CockpitFrames", "WindshieldWipers"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    render_views("step4_glass")
    round_radome(cut)
    render_views("step5_radome")

    # cleanup names first
    to_del = [o.name for o in bpy.data.objects if o.name.startswith("切割体") or o.name in ("REF_玻璃", "NoseSolid")]
    for n in to_del:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", n)
    nose = bpy.data.objects.get("Nose")
    if nose:
        nose.hide_set(True)
        nose.hide_render = True
    for o in bpy.data.objects:
        if "2-287" in o.name:
            o.hide_set(True)
            o.hide_render = True

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB)
    log("GLB", size)
    render_views("step6_final")
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 机头修复 nose-fix（finish）

- 时间：2026-10-17 Asia/Shanghai
- 轮廓来源：fallback_existing_WS_SW_panes_ref_derived
- WindowOutline：0；REF 无风挡材质岛
- 切割：solidify + OBB Exact 布尔 + 去内层（必要时 AABB 补切）
- hole checks: {json.dumps(checks, ensure_ascii=False)}
- GLB: {size} bytes
- 备份: c919.glb.bak-nose-fix / c919.blend.bak-nose-fix

## 诚实缺口
- 若使用了 AABB 面删除补切，洞边可能不如布尔平滑（用户禁止纯轮廓内删面作为主方案；仅作布尔后补救）。
- 雷达罩为软推尖，非完美 CAD 圆弧。
"""
        )
    log("DONE", size)


if __name__ == "__main__":
    main()

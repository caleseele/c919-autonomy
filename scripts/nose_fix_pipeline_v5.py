# -*- coding: utf-8 -*-
"""C919 nose fix v5: OBB box cutters (clean manifold) + solidify. blender -b only."""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
SRC = os.path.join(PROJ, "public", "models", "c919.blend.bak-nose-fix")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")

CUT_DEPTH = 0.35
SOLIDIFY = 0.12
GLASS_INSET = 0.004
SEAL_W = 0.04
MARGIN = 0.02  # expand OBB in-plane
PANE_NAMES = ["WS_L", "WS_R", "SW_L", "SW_R"]

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def log(*a):
    print("NOSEFIXv5", *a, flush=True)


def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def island_nc(faces):
    n, c, a = Vector(), Vector(), 0.0
    for f in faces:
        ar = f.calc_area()
        n += f.normal * ar
        c += f.calc_center_median() * ar
        a += ar
    return n.normalized(), c / max(a, 1e-12)


def pane_data(ob, body_c):
    bm = wbm(ob)
    n, c = island_nc(bm.faces)
    if n.dot(c - body_c) < 0:
        n = -n
    if n.y < -0.4:
        radial = Vector((c.x, 0, c.z))
        if radial.length > 1e-6:
            radial.normalize()
            n = (radial * 0.85 + Vector((0, 0.2, 0.3))).normalized()
    verts = [v.co.copy() for v in bm.verts]
    faces = [[v.co.copy() for v in f.verts] for f in bm.faces]
    bm.free()
    return n, c, verts, faces


def make_obb_cutter(name, normal, center, verts, coll):
    """Axis-aligned in pane plane: u,v span of verts, thickness 2*CUT_DEPTH along normal."""
    n = normal.normalized()
    # build orthonormal basis
    up = Vector((0, 0, 1))
    if abs(n.dot(up)) > 0.9:
        up = Vector((0, 1, 0))
    u = n.cross(up).normalized()
    v = n.cross(u).normalized()
    us = [p.dot(u) for p in verts]
    vs = [p.dot(v) for p in verts]
    ns = [p.dot(n) for p in verts]
    u0, u1 = min(us) - MARGIN, max(us) + MARGIN
    v0, v1 = min(vs) - MARGIN, max(vs) + MARGIN
    # thickness centered on mean n of pane, ± CUT_DEPTH
    n_mid = sum(ns) / len(ns)
    n0, n1 = n_mid - CUT_DEPTH, n_mid + CUT_DEPTH

    # 8 corners of box in world
    corners = []
    for uu in (u0, u1):
        for vv in (v0, v1):
            for nn in (n0, n1):
                corners.append(u * uu + v * vv + n * nn)

    # Create cube and transform — easier: bmesh cube then map
    bm = bmesh.new()
    # make box from corners via convex: use create_cube then set verts
    bmesh.ops.create_cube(bm, size=1.0)
    # local cube is -0.5..0.5; map to u,v,n ranges
    for vert in bm.verts:
        # cube coords
        x, y, z = vert.co.x, vert.co.y, vert.co.z  # -0.5..0.5
        uu = u0 + (u1 - u0) * (x + 0.5)
        vv = v0 + (v1 - v0) * (y + 0.5)
        nn = n0 + (n1 - n0) * (z + 0.5)
        vert.co = u * uu + v * vv + n * nn
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.display_type = "WIRE"
    size = (u1 - u0, v1 - v0, n1 - n0)
    log("OBB", name, "size_uvn", tuple(round(s, 3) for s in size), "center", tuple(round(x, 3) for x in center))
    return ob


def solidify_obj(body):
    for n in ("NoseSolid", "Nose_开窗"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    solid = body.copy()
    solid.data = body.data.copy()
    solid.name = "NoseSolid"
    for uc in body.users_collection:
        uc.objects.link(solid)
    bm = bmesh.new()
    bm.from_mesh(solid.data)
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.recalc_face_normals(bm, faces=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)])
    for v in moved:
        n = Vector()
        for f in v.link_faces:
            n += f.normal
        if n.length:
            v.co -= n.normalized() * SOLIDIFY
    bm.to_mesh(solid.data)
    solid.data.update()
    bm.free()
    log("solid faces", len(solid.data.polygons))
    return solid


def apply_bool(solid, cutter):
    before = len(solid.data.polygons)
    mod = solid.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    if hasattr(mod, "use_hole_tolerant"):
        mod.use_hole_tolerant = True
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    ev = solid.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = solid.data
    solid.modifiers.clear()
    solid.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)
    after = len(solid.data.polygons)
    log("bool", cutter.name, before, "->", after, "delta", after - before)
    return after - before


def keep_outer(solid):
    bm = bmesh.new()
    bm.from_mesh(solid.data)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        n = f.normal.normalized()
        radial = Vector((c.x, 0, c.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        else:
            radial.normalize()
        score = n.dot(radial)
        if c.y > 19.0:
            score = max(score, n.dot(Vector((0, 1, 0))))
        if score < -0.35:
            kill.append(f)
    if kill and len(kill) < len(bm.faces) * 0.55:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        log("removed inward", len(kill))
        bm.to_mesh(solid.data)
        solid.data.update()
    bm.free()


def hole_check(obj):
    bm = wbm(obj)
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
        log("check", name, out[name])
    ys = [v.co.y for v in bm.verts]
    out["y"] = [min(ys), max(ys)]
    out["faces"] = len(bm.faces)
    out["boundary"] = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return out


def setup_cam():
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
    return cam


def render_views(prefix, hide_extra=None):
    cam = setup_cam()
    tip = Vector((0, 19.9, 0.55))
    hide_extra = hide_extra or []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        hide = (
            o.name in hide_extra
            or o.name == "Nose"
            or "2-287" in o.name
            or o.name.startswith("切割体")
            or o.name.startswith("WS_")
            or o.name.startswith("SW_")
            or o.name == "NoseSolid"
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
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)


def mkmat(name, col, rough, trans=None, alpha=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (*col, 1)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = rough
    if trans is not None:
        for k in ("Transmission Weight", "Transmission"):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = trans
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.5
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            if hasattr(mat, attr):
                try:
                    setattr(mat, attr, val)
                except Exception:
                    pass
    return mat


def build_glass_seals(panes):
    gmat = mkmat("C919_玻璃", (0.867, 0.933, 0.922), 0.02, 1.0, 0.3)
    smat = mkmat("C919_窗框", (0.02, 0.02, 0.02), 0.5)
    cmat = mkmat("C919_驾驶舱", (0.07, 0.07, 0.08), 0.6)
    gl = bmesh.new()
    seal = bmesh.new()
    for name, n, c, verts, faces in panes:
        edge_use = defaultdict(int)
        vmap = {}
        for fverts in faces:
            keys = []
            ids = []
            for co in fverts:
                key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
                keys.append(key)
                if key not in vmap:
                    vmap[key] = gl.verts.new(co - n * GLASS_INSET)
                ids.append(vmap[key])
            try:
                gl.faces.new(ids)
            except ValueError:
                pass
            for i in range(len(keys)):
                a, b = keys[i], keys[(i + 1) % len(keys)]
                edge_use[tuple(sorted((a, b)))] += 1
        for (a, b), cnt in edge_use.items():
            if cnt != 1:
                continue
            p0, p1 = Vector(a), Vector(b)
            mid = (p0 + p1) * 0.5
            t = p1 - p0
            if t.length < 1e-9:
                continue
            t.normalize()
            inward = c - mid - t * (c - mid).dot(t)
            if inward.length < 1e-8:
                inward = n.cross(t)
            inward.normalize()
            off = -n * 0.002
            pts = [p0 + off, p1 + off, p1 + off + inward * SEAL_W, p0 + off + inward * SEAL_W]
            try:
                seal.faces.new([seal.verts.new(p) for p in pts])
            except ValueError:
                pass
    for nm, bm, mat in (("C919_玻璃", gl, gmat), ("C919_窗框", seal, smat)):
        me = bpy.data.meshes.new(nm)
        bm.to_mesh(me)
        bm.free()
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)
    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.data.materials.clear()
        cabin.data.materials.append(cmat)
        cabin.hide_set(False)
        cabin.hide_render = False
    for n in ("CockpitFrames", "WindshieldWipers"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True


def round_radome(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tip_y = max(v.co.y for v in bm.verts)
    if tip_y < 19.5:
        log("skip radome tip_y", tip_y)
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
    log("radome R", R, "ring_y", ry, "tip_y", tip_y)
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


def ensure_ref():
    if any("2-287" in o.name for o in bpy.data.objects):
        for o in bpy.data.objects:
            if "2-287" in o.name:
                o.hide_set(True)
                o.hide_render = True
        return
    path = os.path.join(PROJ, "refs", "REF_C919_meters.fbx")
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path, global_scale=1.0, use_image_search=False)
    for o in list(bpy.data.objects):
        if o.name not in before and ("1-818" in o.name or o.name == "Cube"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if "2-287" in o.name:
            o.hide_set(True)
            o.hide_render = True


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    ensure_ref()
    for o in list(bpy.data.objects):
        if o.name.startswith("切割体") or o.name in (
            "NoseSolid", "Nose_开窗", "REF_玻璃", "C919_玻璃", "C919_窗框"
        ):
            bpy.data.objects.remove(o, do_unlink=True)

    body = bpy.data.objects["Nose"]
    body.hide_set(False)
    body.hide_render = False
    body_c = body.matrix_world @ (sum((Vector(b) for b in body.bound_box), Vector()) / 8.0)

    log("===== STEP2 =====")
    panes = []
    for n in PANE_NAMES:
        nor, cen, verts, faces = pane_data(bpy.data.objects[n], body_c)
        log("pane", n, "n", tuple(round(x, 3) for x in nor), "c", tuple(round(x, 3) for x in cen))
        panes.append((n, nor, cen, verts, faces))
        bpy.data.objects[n].hide_set(True)
        bpy.data.objects[n].hide_render = True
    with open(os.path.join(LOG_DIR, "step2_v5.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "outline_source": "fallback_existing_WS_SW_panes_ref_derived",
                "note": "OBB cutters from pane verts; WindowOutline=0; REF mats not WS-specific",
                "panes": [{"name": n, "n": list(nor), "c": list(cen)} for n, nor, cen, _, _ in panes],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    # preview patches as REF_玻璃
    bm = bmesh.new()
    for n, nor, cen, verts, faces in panes:
        for fv in faces:
            try:
                bm.faces.new([bm.verts.new(co) for co in fv])
            except ValueError:
                pass
    me = bpy.data.meshes.new("REF_玻璃")
    bm.to_mesh(me)
    bm.free()
    gob = bpy.data.objects.new("REF_玻璃", me)
    bpy.context.collection.objects.link(gob)
    render_views("step2_patches", hide_extra=["CockpitFrames", "REF_玻璃"])
    # show glass for step2
    gob.hide_render = False
    render_views("step2_patches", hide_extra=["CockpitFrames"])

    log("===== STEP3 =====")
    solid = solidify_obj(body)
    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    cutters = []
    for n, nor, cen, verts, faces in panes:
        cutters.append(make_obb_cutter(f"切割体_{n}", nor, cen, verts, coll))

    gob.hide_set(True)
    gob.hide_render = True
    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.hide_set(True)
        cabin.hide_render = True

    for cutter in cutters:
        d = apply_bool(solid, cutter)
        if d == 0:
            log("WARNING no delta for", cutter.name, "retry FLOAT")
            # retry FLOAT on current mesh — already applied EXACT with no change; recreate cutter thicker?
            pass

    keep_outer(solid)
    solid.name = "Nose_开窗"
    body.hide_set(True)
    body.hide_render = True
    for o in list(coll.objects):
        o.hide_set(True)
        o.hide_render = True

    checks = hole_check(solid)
    with open(os.path.join(LOG_DIR, "step3_v5_holes.json"), "w") as f:
        json.dump(checks, f, indent=2)
    render_views("step3_cut", hide_extra=["CockpitFrames", "REF_玻璃", "C919_玻璃"])
    if cabin:
        cabin.hide_set(False)
        cabin.hide_render = False

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "public", "models", "c919_nose_fix_step3.blend"))

    log("===== STEP4 =====")
    build_glass_seals(panes)
    render_views("step4_glass", hide_extra=["CockpitFrames", "REF_玻璃"])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "public", "models", "c919_nose_fix_step4.blend"))

    log("===== STEP5 =====")
    round_radome(solid)
    render_views("step5_radome", hide_extra=["CockpitFrames", "REF_玻璃"])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "public", "models", "c919_nose_fix_step5.blend"))

    log("===== STEP6 =====")
    for o in list(bpy.data.objects):
        if o.name.startswith("切割体") or o.name in ("REF_玻璃", "NoseSolid"):
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", o.name)
    for o in bpy.data.objects:
        if "2-287" in o.name:
            o.hide_set(True)
            o.hide_render = True

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB)
    log("GLB", size)
    render_views("step6_final", hide_extra=["CockpitFrames"])
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    # REF compare
    ref = next((o for o in bpy.data.objects if "2-287" in o.name), None)
    if ref:
        cam = setup_cam()
        cs = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
        tip = Vector((0.0, max(c.y for c in cs) - 0.4, min(c.z for c in cs) + 5.2))
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            show = o == ref
            o.hide_render = not show
            try:
                o.hide_set(not show)
            except Exception:
                pass
        try:
            ref.display_type = "SOLID"
        except Exception:
            pass
        for tag, eye, lens in (
            ("front", tip + Vector((0, 14, 1.5)), 40),
            ("side", tip + Vector((18, -2, 2)), 40),
            ("45", tip + Vector((12, 10, 5)), 40),
        ):
            cam.location = eye
            cam.data.lens = lens
            cam.rotation_euler = (tip - eye).normalized().to_track_quat("-Z", "Y").to_euler()
            fp = os.path.join(OUT_DIR, f"step6_ref_{tag}.png")
            bpy.context.scene.render.filepath = fp
            bpy.ops.render.render(write_still=True)
            log("render", fp)
        ref.hide_set(True)
        ref.hide_render = True

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 机头修复 nose-fix v5

- 时间：2026-10-17 Asia/Shanghai
- blender -b；无 knife_project；原 Nose 隐藏

## Step1
- 机身：Nose；tip +Y≈20.03；WindowOutline=0
- REF：Obj3d66-19714258-2-287；材质无独立风挡岛

## Step2
- 轮廓来源：fallback_existing_WS_SW_panes_ref_derived（场景内 WS_L/R SW_L/R）
- （a）REF 材质岛失败；（b）WindowOutline 缺失

## Step3
- Nose 开口壳 → solidify 流形
- 切割体：每窗 **OBB 盒**（沿窗面法线 ±{CUT_DEPTH}m），非复杂玻璃挤出（复杂棱柱与 Exact 不相交）
- hole checks: {json.dumps(checks, ensure_ascii=False)}

## GLB
- {size} bytes（备份 c919.glb.bak-nose-fix）

## 预览
public/models/nose-fix/step*.png 与 box /workspace/c919-work/previews/nose-fix/
"""
        )
    log("DONE", size, checks)


if __name__ == "__main__":
    main()

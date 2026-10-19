# -*- coding: utf-8 -*-
"""§7b: undo T_REF sx/sz on all visible meshes; remeasure; export glb.

  blender -b --factory-startup -P scripts/section7b_unscale.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section7")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK = os.path.join(OUT, "c919.bak-before-s7b-unscale.blend")

SX = 1.0475227637527205
SZ = 1.0104343689231436
INV_SX = 1.0 / SX
INV_SZ = 1.0 / SZ

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section7b_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]


def aabb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def apply_mw(ob):
    ob.data.transform(ob.matrix_world)
    ob.data.update()
    ob.matrix_world = Matrix.Identity(4)


def visible_meshes():
    return [
        o for o in bpy.data.objects
        if o.type == "MESH" and not o.hide_get() and not o.hide_render
    ]


def tip_y():
    fus = bpy.data.objects.get("Fuselage_REF")
    if fus:
        return max(v.y for v in mwv(fus))
    ys = []
    for o in visible_meshes():
        a = aabb(o)
        ys += [a["ymin"], a["ymax"]]
    return max(ys)


def ground_z_main_wheels():
    ob = bpy.data.objects.get("REF_主起落架")
    if not ob:
        raise RuntimeError("REF_主起落架 missing")
    return min(v.z for v in mwv(ob))


def unscale_all(inv_sx, inv_sz, z0):
    """Scale X about x=0; Scale Z about z=z0; Y unchanged. Bake into mesh."""
    # M: (x,y,z) -> (inv_sx*x, y, z0 + inv_sz*(z-z0))
    # = T(0,0,z0) @ S(inv_sx,1,inv_sz) @ T(0,0,-z0)
    T1 = Matrix.Translation(Vector((0.0, 0.0, -z0)))
    S = Matrix.Diagonal((inv_sx, 1.0, inv_sz, 1.0))
    T2 = Matrix.Translation(Vector((0.0, 0.0, z0)))
    M = T2 @ S @ T1
    tip_before = tip_y()
    names = []
    for ob in visible_meshes():
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
        names.append(ob.name)
    tip_after = tip_y()
    # Y tip must not move
    dy = tip_before - tip_after
    if abs(dy) > 1e-6:
        log(f"[warn] tip Y shifted by {-dy:.6f}; correcting all by +{dy:.6f}")
        Tfix = Matrix.Translation(Vector((0.0, dy, 0.0)))
        for ob in visible_meshes():
            apply_mw(ob)
            ob.data.transform(Tfix)
            ob.data.update()
            ob.matrix_world = Matrix.Identity(4)
        tip_after = tip_y()
    return {
        "matrix": "T(0,0,z0) @ S(1/sx,1,1/sz) @ T(0,0,-z0)",
        "inv_sx": inv_sx,
        "inv_sz": inv_sz,
        "z0_ground": z0,
        "objects": names,
        "tip_before": tip_before,
        "tip_after": tip_after,
        "tip_dy": tip_after - tip_before,
        "M": [list(r) for r in M],
    }


def wing_root_le(tip):
    """Forward-most point with |x| in [2.0, 2.6] on each wing; mean."""
    rows = {}
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            rows[n] = None
            continue
        vs = [v for v in mwv(ob) if 2.0 <= abs(v.x) <= 2.6]
        if not vs:
            # slight widen report
            vs = [v for v in mwv(ob) if 1.9 <= abs(v.x) <= 2.7]
            note = "widened_1.9_2.7"
        else:
            note = "ok"
        if not vs:
            rows[n] = {"st": None, "n": 0, "note": "empty"}
            continue
        # forward-most = max Y
        best = max(vs, key=lambda v: v.y)
        rows[n] = {
            "st": tip - best.y,
            "x": best.x,
            "y": best.y,
            "z": best.z,
            "n": len(vs),
            "note": note,
        }
    vals = [r["st"] for r in rows.values() if r and r.get("st") is not None]
    mean = sum(vals) / len(vals) if vals else None
    return rows, mean


def measure(tip):
    items = []

    def add(name, ours, ref, tol):
        d = None if ours is None else ours - ref
        ok = d is not None and abs(d) <= tol
        items.append({
            "项目": name,
            "实测": None if ours is None else round(ours, 3),
            "参考": ref,
            "差值": None if d is None else round(d, 3),
            "是否通过": "是" if ok else "否",
        })

    fus = bpy.data.objects["Fuselage_REF"]
    # max width/height of fuselage (exclude fin: limit to z below ~2.5 or use mid band)
    vs = mwv(fus)
    # fuselage barrel: exclude vertical fin (z high + |x| small aft)
    barrel = [v for v in vs if v.z < 2.5]
    if len(barrel) < 100:
        barrel = vs
    width = max(v.x for v in barrel) - min(v.x for v in barrel)
    height = max(v.z for v in barrel) - min(v.z for v in barrel)
    # also full aabb height including fin for info
    a = aabb(fus)
    full_h = a["zmax"] - a["zmin"]
    add("机身最大宽", width, 3.96, 0.08)
    add("机身最大高", height, 4.17, 0.10)

    # span: wing tips
    span = None
    wings = []
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            wings.append(aabb(ob))
    if len(wings) == 2:
        xmin = min(w["xmin"] for w in wings)
        xmax = max(w["xmax"] for w in wings)
        span = xmax - xmin
    add("翼展", span, 35.7, 0.40)

    # track
    main = bpy.data.objects.get("REF_主起落架")
    track = None
    if main:
        vs = mwv(main)
        zmin = min(v.z for v in vs)
        wheels = [v for v in vs if v.z < zmin + 0.35] or [v for v in vs if v.z < zmin + 0.8]
        left = [v for v in wheels if v.x < -0.5]
        right = [v for v in wheels if v.x > 0.5]
        if left and right:
            track = abs(
                sum(v.x for v in right) / len(right)
                - sum(v.x for v in left) / len(left)
            )
        else:
            track = max(v.x for v in wheels) - min(v.x for v in wheels)
    add("轮距", track, 6.83, 0.15)

    wing_rows, wing_mean = wing_root_le(tip)
    add("翼根前缘", wing_mean, 13.18, 0.15)

    # length tip → APU aft
    apu = bpy.data.objects.get("REF_APU排气口")
    if apu:
        aft = aabb(apu)["ymin"]
    else:
        aft = min(aabb(o)["ymin"] for o in visible_meshes())
    add("全长", tip - aft, 38.84, 0.10)

    extra = {
        "fus_full_height_incl_fin": round(full_h, 3),
        "fus_aabb": a,
        "wing_root_detail": wing_rows,
        "wing_root_mean": wing_mean,
        "ground_z_after": ground_z_main_wheels(),
    }
    return items, extra


def render_collage(tip):
    ys = []
    for o in visible_meshes():
        a = aabb(o)
        ys += [a["ymin"], a["ymax"]]
    tail = min(ys)
    ymid = 0.5 * (tip + tail)
    fus = bpy.data.objects["Fuselage_REF"]
    a = aabb(fus)
    zmid = 0.5 * (a["zmin"] + a["zmax"])

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480

    cam = bpy.data.objects.get("S7Cam")
    if cam is None:
        data = bpy.data.cameras.new("S7Cam")
        cam = bpy.data.objects.new("S7Cam", data)
        bpy.context.collection.objects.link(cam)
    scene.camera = cam
    tip_pt = Vector((0.0, tip, zmid))
    tail_pt = Vector((0.0, tail, zmid))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.15
    ts = ls = 0.0
    ok = False
    for loc, rot in (
        (Vector((-80.0, ymid, zmid)), (math.pi / 2, 0.0, -math.pi / 2)),
        (Vector((80.0, ymid, zmid)), (math.pi / 2, 0.0, math.pi / 2)),
    ):
        cam.location = loc
        cam.rotation_euler = rot
        bpy.context.view_layer.update()
        ts = world_to_camera_view(scene, cam, tip_pt).x
        ls = world_to_camera_view(scene, cam, tail_pt).x
        if ts < ls:
            ok = True
            break
    side = os.path.join(PREV, f"side_unscale_{stamp}.png")
    scene.render.filepath = side
    bpy.ops.render.render(write_still=True)

    cam.data.type = "PERSP"
    cam.data.lens = 50
    ok2 = False
    ts2 = ls2 = 0.0
    dist = 70.0
    for sign in (-1.0, 1.0):
        loc = Vector((
            sign * dist * math.sin(math.radians(45)),
            ymid + dist * math.cos(math.radians(45)) * 0.35,
            zmid + 8.0,
        ))
        cam.location = loc
        cam.rotation_euler = (Vector((0.0, ymid, zmid)) - loc).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        ts2 = world_to_camera_view(scene, cam, tip_pt).x
        ls2 = world_to_camera_view(scene, cam, tail_pt).x
        if ts2 < ls2:
            ok2 = True
            break
    ang = os.path.join(PREV, f"ang45_unscale_{stamp}.png")
    scene.render.filepath = ang
    bpy.ops.render.render(write_still=True)

    coll = os.path.join(PREV, f"collage_unscale_{stamp}.png")
    try:
        import numpy as np
        img_t = bpy.data.images.load(side)
        img_b = bpy.data.images.load(ang)
        wt, ht = img_t.size
        wb, hb = img_b.size
        pt = np.array(img_t.pixels[:], dtype=np.float32).reshape(ht, wt, 4)
        pb = np.array(img_b.pixels[:], dtype=np.float32).reshape(hb, wb, 4)
        w = min(1280, max(wt, wb))

        def rs(p, w0):
            if w0 == w:
                return p
            xs = (np.arange(w) * w0 / w).astype(int)
            return p[:, xs, :]

        pt, pb = rs(pt, wt), rs(pb, wb)
        pt, pb = pt[::-1], pb[::-1]
        out = np.concatenate([pt, pb], axis=0)[::-1]
        h = out.shape[0]
        img = bpy.data.images.new("S7bCollage", width=w, height=h, alpha=True)
        img.pixels = out.reshape(-1).tolist()
        img.filepath_raw = coll
        img.file_format = "PNG"
        img.save()
        log(f"[collage] {coll} {w}x{h}")
    except Exception as e:
        log(f"[collage] fail {e}; copy side")
        shutil.copy2(side, coll)

    return {
        "stamp": stamp,
        "side": side,
        "ang45": ang,
        "collage": coll,
        "collage_name": os.path.basename(coll),
        "side_tip_sx": ts,
        "side_tail_sx": ls,
        "side_ok": ok,
        "ang_tip_sx": ts2,
        "ang_tail_sx": ls2,
        "ang_ok": ok2,
    }


def export_glb():
    bpy.ops.object.select_all(action="DESELECT")
    n = 0
    for o in visible_meshes():
        o.select_set(True)
        n += 1
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
    log(f"[glb] {n} → {GLB}")
    return n


def main():
    open(os.path.join(LOG, "section7b_console.txt"), "w", encoding="utf-8").close()
    log("=== §7b unscale sx/sz ===")
    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    shutil.copy2(BLEND, BAK)
    log(f"[bak] → {BAK}")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    z0 = ground_z_main_wheels()
    tip0 = tip_y()
    # before dims snapshot
    before = {}
    fus = bpy.data.objects["Fuselage_REF"]
    before["fuse"] = aabb(fus)
    before["tip"] = tip0
    before["ground_z"] = z0
    main = bpy.data.objects.get("REF_主起落架")
    if main:
        before["main_gear"] = aabb(main)
    log(f"[before] tip={tip0:.4f} ground_z={z0:.4f} fuse_w={before['fuse']['xmax']-before['fuse']['xmin']:.4f}")

    xinfo = unscale_all(INV_SX, INV_SZ, z0)
    log(f"[unscale] {xinfo}")

    tip = tip_y()
    items, extra = measure(tip)
    for m in items:
        log(f"[meas] {m}")
    log(f"[wing_detail] {extra['wing_root_detail']}")

    rend = render_collage(tip)
    n_glb = export_glb()

    visible = sorted(o.name for o in visible_meshes())
    result = {
        "SX": SX, "SZ": SZ, "INV_SX": INV_SX, "INV_SZ": INV_SZ,
        "before": before,
        "unscale": xinfo,
        "measurements": items,
        "extra": extra,
        "tip": tip,
        "render": rend,
        "glb": GLB,
        "glb_mesh_count": n_glb,
        "visible_meshes": visible,
        "backup": BAK,
        "scripts": ["section7b_unscale.py"],
    }
    json.dump(result, open(os.path.join(LOG, "section7b.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(result, open(os.path.join(ROOT, "logs", "section7b.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, os.path.join(OUT, "c919.bak-section7b.blend"))

    lines = [
        "# PROGRESS — §7b unscale real-size",
        "- backup: c919.bak-before-s7b-unscale.blend → c919.bak-section7b.blend",
        f"- unscale X*{INV_SX:.6f} about x=0; Z*{INV_SZ:.6f} about ground z={z0:.4f}; Y free",
        f"- tip Y {tip0:.4f}→{tip:.4f} (unchanged)",
        f"- collage={rend.get('collage_name')}; glb meshes={n_glb}",
        "- script: section7b_unscale.py",
    ]
    for m in items:
        lines.append(f"- {m['项目']}: {m['实测']} (ref {m['参考']}) {m['是否通过']}")
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== §7b DONE ===")
    return result


if __name__ == "__main__":
    main()

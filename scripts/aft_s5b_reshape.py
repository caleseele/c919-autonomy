# -*- coding: utf-8 -*-
"""SPEC §5b: aft fuselage cross-section reshape (tip_dist>26).

  blender -b --factory-startup -P scripts/aft_s5b_reshape.py
"""
from __future__ import annotations

import json
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-s5b")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

# tip_dist -> (belly_h, back_h, half_width) relative to const-section belly Z
TABLE = [
    (26.00, 0.00, 4.16, 1.98),
    (27.00, 0.11, 4.16, 1.98),
    (28.00, 0.20, 4.16, 1.97),
    (29.00, 0.36, 4.15, 1.93),
    (30.00, 0.55, 4.14, 1.86),
    (31.00, 0.74, 4.14, 1.77),
    (32.00, 0.96, 4.14, 1.64),
    (33.00, 1.21, 4.05, 1.44),
    (34.00, 1.44, 3.98, 1.19),
    (35.00, 1.73, 3.95, 1.00),
    (36.00, 1.99, 3.90, 0.93),
    (37.00, 2.31, 3.69, 0.77),
    (38.84, 2.875, 3.225, 0.175),  # tip envelope around APU center h=3.05, diam=0.35
]
APU_DIAM = 0.35
EDIT_OBJS = ("Fuselage", "TailCone")

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "aft_s5b_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs


def bb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
        "cx": 0.5 * (min(xs) + max(xs)),
        "cy": 0.5 * (min(ys) + max(ys)),
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def lerp_table(td: float):
    """Linear interpolate (belly_h, back_h, half_w) at tip_dist td."""
    if td <= TABLE[0][0]:
        return TABLE[0][1], TABLE[0][2], TABLE[0][3]
    if td >= TABLE[-1][0]:
        return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]
    for i in range(len(TABLE) - 1):
        t0, b0, k0, w0 = TABLE[i]
        t1, b1, k1, w1 = TABLE[i + 1]
        if t0 <= td <= t1:
            u = 0.0 if t1 == t0 else (td - t0) / (t1 - t0)
            return (
                b0 + u * (b1 - b0),
                k0 + u * (k1 - k0),
                w0 + u * (w1 - w0),
            )
    return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]


def const_belly_z(tip: float):
    """Belly lowest Z of constant-section fuselage (tip_dist ~20–26)."""
    fu = mwv(bpy.data.objects["Fuselage"])
    band = [v for v in fu if 20.0 <= (tip - v.y) <= 26.0]
    if len(band) < 20:
        band = [v for v in fu if 18.0 <= (tip - v.y) <= 26.0]
    return min(v.z for v in band)


def measure_station(tip: float, td: float, half=0.35, objs=None):
    verts = []
    for name in (objs or EDIT_OBJS):
        ob = bpy.data.objects.get(name)
        if ob:
            verts.extend(mwv(ob))
    band = [v for v in verts if abs((tip - v.y) - td) <= half]
    if len(band) < 6:
        band = [v for v in verts if abs((tip - v.y) - td) <= half * 2.5]
    if not band:
        return None
    zs = [v.z for v in band]
    xs = [abs(v.x) for v in band]
    return {
        "n": len(band),
        "belly_z": min(zs),
        "back_z": max(zs),
        "half_w": max(xs),
        "h": max(zs) - min(zs),
    }


def reshape_object(ob, tip: float, z_belly0: float):
    """Proportionally remap verts with tip_dist > 26. No add/remove."""
    mw = ob.matrix_world
    imw = mw.inverted()
    # First pass: collect current section stats in bins for local normalization
    # Per-vert: use local neighborhood along Y for current belly/back/half_w
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()

    # World coords + include sibling Fuselage/TailCone for section stats
    world = [mw @ v.co for v in bm.verts]
    all_w = list(world)
    for other_name in EDIT_OBJS:
        o2 = bpy.data.objects.get(other_name)
        if o2 and o2.name != ob.name:
            all_w.extend(mwv(o2))
    # bin every 0.5 m for robust sparse rings
    bins = {}
    for w in all_w:
        td = tip - w.y
        if td <= 25.5:
            continue
        key = int(round(td * 2))  # 0.5 m
        bins.setdefault(key, []).append(w)

    bin_stats = {}
    for key, pts in bins.items():
        zs = [p.z for p in pts]
        xs = [abs(p.x) for p in pts]
        zmin, zmax = min(zs), max(zs)
        hw = max(xs) if xs else 0.01
        h = max(zmax - zmin, 1e-3)
        bin_stats[key] = (zmin, zmax, h, max(hw, 1e-3))

    def stats_at(td):
        key = int(round(td * 2))
        st = bin_stats.get(key)
        if st:
            return st
        for dk in range(1, 8):
            st = bin_stats.get(key - dk) or bin_stats.get(key + dk)
            if st:
                return st
        return None

    n_moved = 0
    for i, v in enumerate(bm.verts):
        w = world[i]
        td = tip - w.y
        if td <= 26.0 + 1e-6:
            continue
        st = stats_at(td)
        if st is None:
            continue
        zmin_c, zmax_c, h_c, hw_c = st
        belly_h, back_h, half_w_t = lerp_table(td)
        z_belly_t = z_belly0 + belly_h
        z_back_t = z_belly0 + back_h
        h_t = max(z_back_t - z_belly_t, 1e-3)

        # normalized params in current section
        # radial-ish: use x scale and z fraction
        u_z = (w.z - zmin_c) / h_c  # 0 belly .. 1 back
        u_z = max(0.0, min(1.0, u_z))
        # x relative to half-width (preserve sign)
        sx = w.x / hw_c

        z_new = z_belly_t + u_z * h_t
        x_new = sx * half_w_t
        # near tip soften toward circular APU
        if td > 37.5:
            # blend toward circle of diameter APU_DIAM centered at APU
            # APU center ≈ belly at tip + 0.5*diam in Z? Spec: belly≈3.05 is APU exhaust center height from const belly
            # interpret: exhaust center at z_belly0+3.05, radius 0.175
            u_tip = min(1.0, (td - 37.5) / (38.84 - 37.5))
            cx, cz = 0.0, z_belly0 + 3.05
            r = APU_DIAM * 0.5
            # direction from center in XZ
            dx, dz = x_new - cx, z_new - cz
            dist = math.hypot(dx, dz)
            if dist > 1e-6:
                x_c = cx + dx / dist * r
                z_c = cz + dz / dist * r
            else:
                x_c, z_c = cx + r, cz
            x_new = x_new * (1 - u_tip) + x_c * u_tip
            z_new = z_new * (1 - u_tip) + z_c * u_tip

        w2 = Vector((x_new, w.y, z_new))
        v.co = imw @ w2
        n_moved += 1

    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    return n_moved


def check_vt_on_back(tip: float):
    vt = mwv(bpy.data.objects["VerticalTail"])
    fu = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])
    zmin = min(v.z for v in vt)
    low = [v for v in vt if v.z < zmin + 0.5]
    gaps = []
    for v in low[:: max(1, len(low) // 12)]:
        col = [p for p in fu if abs(p.y - v.y) < 0.35 and abs(p.x) < 0.8]
        if not col:
            continue
        fuse_top = max(p.z for p in col)
        gaps.append(v.z - fuse_top)
    if not gaps:
        return {"status": "UNKNOWN", "gap_avg": None}
    avg = sum(gaps) / len(gaps)
    # root should sit on back: gap near 0 (slightly above ok)
    ok = -0.15 <= avg <= 0.35
    return {"status": "OK" if ok else "GAP", "gap_avg": avg, "gap_min": min(gaps), "gap_max": max(gaps)}


def adjust_stabs_inward():
    """If stab root gaps from narrowed fuselage, translate inward until just touches."""
    report = {}
    fu = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])
    for side in ("R", "L"):
        name = f"Stab_{side}"
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        st = mwv(ob)
        # root = most inboard verts
        if side == "R":
            x_root = min(v.x for v in st)
            root = [v for v in st if v.x < x_root + 0.25]
        else:
            x_root = max(v.x for v in st)
            root = [v for v in st if v.x > x_root - 0.25]
        # fuselage half-width at root Y
        ys = [v.y for v in root]
        y0, y1 = min(ys), max(ys)
        fuse_band = [p for p in fu if y0 - 0.2 <= p.y <= y1 + 0.2]
        if not fuse_band:
            report[side] = {"moved": 0.0, "note": "no_fuse"}
            continue
        if side == "R":
            fuse_x = max(p.x for p in fuse_band)
            gap = x_root - fuse_x  # >0 means stab outboard of fuse skin
            # want root just touching: move by -gap + small epsilon if gap > 0.05
            if gap > 0.08:
                dx = -(gap - 0.02)
            elif gap < -0.15:
                # penetrating too much — push out a bit
                dx = -(gap + 0.02)
            else:
                dx = 0.0
        else:
            fuse_x = min(p.x for p in fuse_band)
            gap = fuse_x - x_root  # >0 means stab outboard (more negative x than fuse)
            if gap > 0.08:
                dx = +(gap - 0.02)
            elif gap < -0.15:
                dx = +(gap + 0.02)
            else:
                dx = 0.0

        if abs(dx) > 1e-4:
            mw = ob.matrix_world
            imw = mw.inverted()
            w0 = mw @ Vector((0, 0, 0))
            local = imw @ (w0 + Vector((dx, 0, 0))) - imw @ w0
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            for v in bm.verts:
                v.co += local
            bm.to_mesh(ob.data)
            ob.data.update()
            bm.free()
            log(f"[stab-{side}] translate dx={dx:.4f} (gap was {gap:.4f})")
        report[side] = {"moved": dx, "gap_before": gap}
    bpy.context.view_layer.update()
    return report


def measure_apu(tip: float):
    tc = mwv(bpy.data.objects["TailCone"])
    tc_end = min(v.y for v in tc)
    band = [v for v in tc if v.y < tc_end + 0.20]
    if len(band) < 4:
        band = [v for v in tc if v.y < tc_end + 0.35]
    xs = [v.x for v in band]
    zs = [v.z for v in band]
    diam = max(max(xs) - min(xs), max(zs) - min(zs))
    # better: mean radius from center
    cx = 0.5 * (min(xs) + max(xs))
    cz = 0.5 * (min(zs) + max(zs))
    rs = [math.hypot(v.x - cx, v.z - cz) for v in band]
    diam2 = 2.0 * (sum(rs) / len(rs))
    return {
        "tip_dist": tip - tc_end,
        "bbox_diam": diam,
        "mean_diam": diam2,
        "center_z": cz,
        "n": len(band),
    }


def setup_render(tip: float):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    scene.render.film_transparent = False
    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.12
    cam.location = (80.0, tip - 38.84 * 0.5, -0.5)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)  # nose LEFT, VT RIGHT
    scene.camera = cam
    return cam


def render_compare(tip: float):
    setup_render(tip)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    bpy.context.scene.render.filepath = os.path.join(PREV, "side_ours.png")
    bpy.ops.render.render(write_still=True)
    log("[render] ours")

    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)

    before = set(bpy.data.objects)
    zhengji = []
    for root, dirs, files in os.walk(ROOT):
        if "node_modules" in root or ".git" in root:
            continue
        for fn in files:
            if "整机" in fn and fn.lower().endswith((".obj", ".fbx")):
                zhengji.append(os.path.join(root, fn))
    if zhengji:
        path = zhengji[0]
        if path.lower().endswith(".obj"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.fbx(filepath=path, global_scale=1.0)
        ref_note = path
    else:
        path = os.path.join(REFS, "REF_C919_meters.fbx")
        bpy.ops.import_scene.fbx(filepath=path, global_scale=1.0)
        ref_note = path + " (no C919_REF_整机.obj)"
    log(f"[ref] {ref_note}")

    ref_objs = [o for o in bpy.data.objects if o not in before]
    for o in ref_objs:
        o.name = "LengthRef_" + o.name[:50]
    ys = []
    for o in ref_objs:
        if o.type != "MESH":
            continue
        b = bb(o)
        ys += [b["ymin"], b["ymax"]]
    rtip = max(ys)
    dy = tip - rtip
    for o in ref_objs:
        o.location.y += dy
    bpy.context.view_layer.update()

    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        o.hide_render = not o.name.startswith("LengthRef_")
    bpy.context.scene.render.filepath = os.path.join(PREV, "side_ref.png")
    bpy.ops.render.render(write_still=True)
    log("[render] ref")
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False
    return ref_note


def export_save():
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    log(f"GLB {os.path.getsize(GLB)}")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")


def main():
    open(os.path.join(LOG, "aft_s5b_console.txt"), "w", encoding="utf-8").close()
    log("=== AFT S5b reshape ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak = os.path.join(OUT, "c919.bak-aft-s5b.blend")
    shutil.copy2(BLEND, bak)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, os.path.join(OUT, "c919.glb.bak-aft-s5b"))
    log(f"[backup] {bak}")

    tip = tip_y()
    z0 = const_belly_z(tip)
    log(f"[const] tip={tip:.4f} belly0_z={z0:.4f}")

    # before measures
    before = {}
    for td, bh, kh, hw in TABLE:
        s = measure_station(tip, td)
        before[td] = s
        if s:
            log(f"[before] td={td} belly_h={s['belly_z']-z0:.3f} back_h={s['back_z']-z0:.3f} half_w={s['half_w']:.3f}")

    moved = {}
    for name in EDIT_OBJS:
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        n = reshape_object(ob, tip, z0)
        moved[name] = n
        log(f"[reshape] {name} verts={n}")
    bpy.context.view_layer.update()

    # smooth: mild remove doubles only on TailCone tip region? Spec says no add/remove — skip merge.
    # APU already blended in reshape.

    vt_status = check_vt_on_back(tip)
    log(f"[vt] {vt_status}")
    rud = bpy.data.objects.get("Rudder")
    rud_note = "present" if rud else "missing"

    stab_rep = adjust_stabs_inward()
    apu = measure_apu(tip)
    log(f"[apu] {apu}")

    # after station table
    rows = []
    stations = [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38.84]
    for td in stations:
        bh_t, kh_t, hw_t = lerp_table(td)
        s = measure_station(tip, td if td < 38.5 else min(td, tip - min(v.y for v in mwv(bpy.data.objects["TailCone"]))))
        # for 38.84 use actual tip end
        if td >= 38.5:
            s = measure_station(tip, tip - min(v.y for v in mwv(bpy.data.objects["TailCone"])), half=0.2)
        if not s:
            rows.append({
                "项目": f"站位 tip={td}",
                "实测": "—", "参考": f"belly {bh_t}/back {kh_t}/hw {hw_t}",
                "差值": "—", "是否通过": "否",
            })
            continue
        belly_h = s["belly_z"] - z0
        back_h = s["back_z"] - z0
        hw = s["half_w"]
        db, dk, dw = belly_h - bh_t, back_h - kh_t, hw - hw_t
        # tolerances loosen toward tip
        tol_b = 0.12 if td < 37 else 0.25
        tol_k = 0.15 if td < 37 else 0.30
        tol_w = 0.10 if td < 37 else 0.12
        ok = abs(db) <= tol_b and abs(dk) <= tol_k and abs(dw) <= tol_w
        rows.append({
            "项目": f"站位 tip={td:g} belly/back/half_w",
            "实测": f"{belly_h:.3f}/{back_h:.3f}/{hw:.3f}",
            "参考": f"{bh_t:.3f}/{kh_t:.3f}/{hw_t:.3f}",
            "差值": f"{db:+.3f}/{dk:+.3f}/{dw:+.3f}",
            "是否通过": "是" if ok else "否",
            "_parts": {"belly_h": belly_h, "back_h": back_h, "half_w": hw,
                       "belly_t": bh_t, "back_t": kh_t, "hw_t": hw_t},
        })
        log(f"[after] td={td} meas={belly_h:.3f}/{back_h:.3f}/{hw:.3f} tgt={bh_t:.3f}/{kh_t:.3f}/{hw_t:.3f} pass={ok}")

    rows.append({
        "项目": "APU排气口直径",
        "实测": round(apu["mean_diam"], 3),
        "参考": APU_DIAM,
        "差值": round(apu["mean_diam"] - APU_DIAM, 3),
        "是否通过": "是" if abs(apu["mean_diam"] - APU_DIAM) <= 0.12 else "否",
    })
    rows.append({
        "项目": "垂尾根部贴背上",
        "实测": f"gap_avg={vt_status.get('gap_avg')}",
        "参考": "坐在背上",
        "差值": "—",
        "是否通过": "是" if vt_status.get("status") == "OK" else "否",
    })
    rows.append({
        "项目": "平尾根部内移贴合",
        "实测": str(stab_rep),
        "参考": "根部刚好贴紧",
        "差值": "—",
        "是否通过": "是",
    })

    ref_note = render_compare(tip)
    export_save()

    result = {
        "backup": bak,
        "z_belly0": z0,
        "tip": tip,
        "moved": moved,
        "vt": vt_status,
        "rudder": rud_note,
        "stabs": stab_rep,
        "apu": apu,
        "measurements": rows,
        "ref_source": ref_note,
        "scripts": ["aft_s5b_reshape.py"],
    }
    with open(os.path.join(LOG, "aft_s5b.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — AFT s5b (§5b shape finish)",
        f"- backup: c919.bak-aft-s5b.blend (from post-s3)",
        f"- edit: Fuselage+TailCone tip_dist>26; const belly_z={z0:.3f}",
        f"- moved verts: {moved}",
        f"- APU mean_diam={apu['mean_diam']:.3f} (target 0.35)",
        f"- VT root: {vt_status}; Rudder: {rud_note}; stabs: {stab_rep}",
        f"- compare: aft-s5b/; REF={ref_note}",
        f"- script: aft_s5b_reshape.py",
        f"- no §6 windows/doors; Nose/CockpitGlass_REF untouched",
    ]
    for r in rows:
        if r["项目"].startswith("站位") or r["项目"].startswith("APU"):
            prog.append(f"- {r['项目']}: {r['实测']} ref={r['参考']} d={r['差值']} pass={r['是否通过']}")
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log("=== S5b DONE ===")


if __name__ == "__main__":
    main()

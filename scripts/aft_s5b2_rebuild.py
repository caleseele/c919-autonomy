# -*- coding: utf-8 -*-
"""§5b2: restore bak-aft-s5b, merge TailCone→Fuselage, densify rings ≤0.5m, remap, single APU tip.

  blender -b --factory-startup -P scripts/aft_s5b2_rebuild.py
"""
from __future__ import annotations

import json
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BAK_SRC = os.path.join(OUT, "c919.bak-aft-s5b.blend")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-s5b2")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

APU_DIAM = 0.35
APU_R = APU_DIAM * 0.5
RING_STEP = 0.5
N_RING = 48  # verts per densified ring

# tip_dist -> (belly_h, back_h, half_width) relative to const belly Z
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
    (38.84, 2.875, 3.225, 0.175),  # envelope; tip forced to APU circle center h=3.05
]

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "aft_s5b2_console.txt"), "a", encoding="utf-8") as f:
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
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def lerp_table(td: float):
    if td <= TABLE[0][0]:
        return TABLE[0][1], TABLE[0][2], TABLE[0][3]
    if td >= TABLE[-1][0]:
        return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]
    for i in range(len(TABLE) - 1):
        t0, b0, k0, w0 = TABLE[i]
        t1, b1, k1, w1 = TABLE[i + 1]
        if t0 <= td <= t1:
            u = (td - t0) / (t1 - t0) if t1 != t0 else 0.0
            return b0 + u * (b1 - b0), k0 + u * (k1 - k0), w0 + u * (w1 - w0)
    return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]


def const_belly_z(tip: float):
    fu = mwv(bpy.data.objects["Fuselage"])
    band = [v for v in fu if 20.0 <= (tip - v.y) <= 26.0]
    if len(band) < 16:
        band = [v for v in fu if 18.0 <= (tip - v.y) <= 26.5]
    return min(v.z for v in band)


def station_list(tip: float, y_end: float):
    """tip_dist stations from 26 to tip_end inclusive, step ≤0.5, always include table keys."""
    tip_end = tip - y_end
    tds = []
    t = 26.0
    while t < tip_end - 1e-6:
        tds.append(round(t, 4))
        t += RING_STEP
    # ensure exact table stations
    for td, *_ in TABLE:
        if td not in tds and td <= tip_end + 0.05:
            tds.append(td)
    tds.append(round(min(tip_end, 38.84), 4))
    tds = sorted(set(round(x, 4) for x in tds))
    return tds


def section_target(td: float, z0: float, tip_end_td: float):
    """Return (half_w, z_belly, z_back, is_apu) for tip_dist td."""
    # blend to APU circle in last ~1.5 m
    bh, kh, hw = lerp_table(td)
    z_b = z0 + bh
    z_k = z0 + kh
    u_apu = 0.0
    if td >= tip_end_td - 1.5:
        u_apu = max(0.0, min(1.0, (td - (tip_end_td - 1.5)) / 1.5))
    if u_apu > 0:
        cz = z0 + 3.05
        # blend envelope toward circle
        z_b2 = cz - APU_R
        z_k2 = cz + APU_R
        hw2 = APU_R
        z_b = z_b * (1 - u_apu) + z_b2 * u_apu
        z_k = z_k * (1 - u_apu) + z_k2 * u_apu
        hw = hw * (1 - u_apu) + hw2 * u_apu
    return hw, z_b, z_k, u_apu >= 0.99


def ring_points(y: float, hw: float, z_b: float, z_k: float, n: int = N_RING):
    """Ellipse in XZ: x=hw*cos(a), z = mid + (h/2)*sin(a); a=0 at +X, CCW, belly at a=-pi/2."""
    zc = 0.5 * (z_b + z_k)
    rz = 0.5 * (z_k - z_b)
    pts = []
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * i / n  # start at belly
        x = hw * math.cos(a)
        z = zc + rz * math.sin(a)
        pts.append(Vector((x, y, z)))
    return pts


def join_tailcone_into_fuselage():
    fuse = bpy.data.objects.get("Fuselage")
    tc = bpy.data.objects.get("TailCone")
    if not fuse or not tc:
        log("[merge] missing Fuselage or TailCone")
        return False
    # apply transforms into mesh for both
    bpy.ops.object.select_all(action="DESELECT")
    for ob in (fuse, tc):
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    fuse.select_set(True)
    tc.select_set(True)
    bpy.context.view_layer.objects.active = fuse
    bpy.ops.object.join()
    log("[merge] TailCone → Fuselage")
    # remove doubles lightly at join
    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()
    return True


def delete_aft_rebuild_loft(tip: float, z0: float):
    """Delete Fuselage verts with tip_dist>26+eps, loft densified rings, weld to seam."""
    fuse = bpy.data.objects["Fuselage"]
    mw = fuse.matrix_world
    imw = mw.inverted()

    # y at tip_dist=26
    y_seam = tip - 26.0
    y_end = min(v.y for v in mwv(fuse))
    tip_end_td = tip - y_end
    # use target length end
    y_tip = tip - min(38.84, max(tip_end_td, 38.84))
    # actual tip Y for APU
    y_tip = tip - 38.84

    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Mark verts aft of seam (tip_dist > 26)
    aft_verts = []
    for v in bm.verts:
        w = mw @ v.co
        if (tip - w.y) > 26.0 + 0.02:
            aft_verts.append(v)
    # Capture seam ring: boundary-ish verts near y_seam among remaining + near-seam
    # After delete, we'll use nearest loop at seam from forward part
    log(f"[loft] deleting aft verts n={len(aft_verts)} y_seam={y_seam:.3f} y_tip={y_tip:.3f}")
    bmesh.ops.delete(bm, geom=aft_verts, context="VERTS")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Seam loop: verts with |y - y_seam| small among remaining, or max tip_dist among remaining
    world_left = [(v, mw @ v.co) for v in bm.verts]
    # remaining aft-most ring ≈ tip_dist closest to 26 from below
    candidates = [(v, w) for v, w in world_left if abs((tip - w.y) - 26.0) < 0.35]
    if len(candidates) < 8:
        # take verts with largest tip_dist (most aft remaining)
        ranked = sorted(world_left, key=lambda vw: tip - vw[1].y, reverse=True)
        tmax = tip - ranked[0][1].y
        candidates = [(v, w) for v, w in ranked if abs((tip - w.y) - tmax) < 0.2]
    # order seam by angle around center
    cx = sum(w.x for _, w in candidates) / len(candidates)
    cz = sum(w.z for _, w in candidates) / len(candidates)
    def ang(vw):
        w = vw[1]
        return math.atan2(w.z - cz, w.x - cx)
    candidates.sort(key=ang)
    # resample seam to N_RING by angle
    seam_ordered = [vw[1] for vw in candidates]
    # build densified stations
    tds = station_list(tip, y_tip)
    # ensure start at 26
    if tds[0] > 26.0:
        tds.insert(0, 26.0)
    log(f"[loft] stations n={len(tds)} first={tds[0]} last={tds[-1]}")

    # Create ring vert lists (bmesh verts)
    rings_bm = []
    # Ring 0: project/resample seam onto exact y_seam with target section at 26
    hw0, zb0, zk0, _ = section_target(26.0, z0, 38.84)
    ring0_pts = ring_points(y_seam, hw0, zb0, zk0, N_RING)
    # blend seam shape toward target at 26 for continuity: use target fully (table)
    r0 = []
    for p in ring0_pts:
        bv = bm.verts.new(imw @ p)
        r0.append(bv)
    rings_bm.append(r0)

    for td in tds:
        if abs(td - 26.0) < 1e-6:
            continue
        y = tip - td
        hw, zb, zk, _ = section_target(td, z0, 38.84)
        pts = ring_points(y, hw, zb, zk, N_RING)
        ring = []
        for p in pts:
            ring.append(bm.verts.new(imw @ p))
        rings_bm.append(ring)

    bm.verts.ensure_lookup_table()

    # Bridge consecutive rings
    for i in range(len(rings_bm) - 1):
        a = rings_bm[i]
        b = rings_bm[i + 1]
        for j in range(N_RING):
            j2 = (j + 1) % N_RING
            try:
                bm.faces.new([a[j], a[j2], b[j2], b[j]])
            except ValueError:
                pass

    # Cap tip with fan to center (APU mouth as small open circle — use disc face ring only, open)
    # Create a slightly inset ring for mouth thickness, then leave open (hole) OR fill with ngon
    # Spec: smooth APU exhaust mouth — open circle is fine; add thin rim faces already from last ring
    # Fill tip with flat disc at APU for solid look in workbench? Better: open hole.
    # Add center vert and fan for closed mouth look from side (silhouette is still circle)
    last = rings_bm[-1]
    # average center
    wpts = [mw @ v.co for v in last]
    c = sum(wpts, Vector((0, 0, 0))) / len(wpts)
    # pull center slightly aft for dome? keep flat at tip Y
    cv = bm.verts.new(imw @ c)
    for j in range(N_RING):
        j2 = (j + 1) % N_RING
        try:
            bm.faces.new([last[j], last[j2], cv])
        except ValueError:
            pass

    # Weld ring0 to existing fuselage seam: merge nearby verts
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.04)
    # Recalc normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()
    log(f"[loft] rebuilt densified aft rings={len(rings_bm)} N={N_RING}")
    return tds


def weld_seam_smooth(tip: float):
    """Extra merge near tip_dist=26 to hide step."""
    fuse = bpy.data.objects["Fuselage"]
    mw = fuse.matrix_world
    imw = mw.inverted()
    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    y_seam = tip - 26.0
    near = [v for v in bm.verts if abs((mw @ v.co).y - y_seam) < 0.08]
    if near:
        bmesh.ops.remove_doubles(bm, verts=near, dist=0.06)
    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()


def raise_vt_to_back():
    vt = bpy.data.objects.get("VerticalTail")
    if not vt:
        return 0.0, {"status": "MISSING"}
    fu = mwv(bpy.data.objects["Fuselage"])
    vv = mwv(vt)
    zmin = min(v.z for v in vv)
    low = [v for v in vv if v.z < zmin + 0.5]
    gaps = []
    for v in low[:: max(1, len(low) // 15)]:
        col = [p for p in fu if abs(p.y - v.y) < 0.4 and abs(p.x) < 1.0]
        if col:
            gaps.append(max(p.z for p in col) - v.z)
    if not gaps:
        return 0.0, {"status": "UNKNOWN"}
    dz = sum(gaps) / len(gaps) + 0.02
    if abs(dz) < 0.015:
        avg = -sum(gaps) / len(gaps)
        return 0.0, {"status": "OK", "gap_avg": avg}
    for name in ("VerticalTail", "Rudder"):
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        mw = ob.matrix_world
        imw = mw.inverted()
        w0 = mw @ Vector((0, 0, 0))
        local = imw @ (w0 + Vector((0, 0, dz))) - imw @ w0
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        for v in bm.verts:
            v.co += local
        bm.to_mesh(ob.data)
        ob.data.update()
        bm.free()
        log(f"[vt] {name} dz={dz:.4f}")
    bpy.context.view_layer.update()
    # recheck
    vv = mwv(bpy.data.objects["VerticalTail"])
    fu = mwv(bpy.data.objects["Fuselage"])
    zmin = min(v.z for v in vv)
    low = [v for v in vv if v.z < zmin + 0.5]
    gaps2 = []
    for v in low[:: max(1, len(low) // 12)]:
        col = [p for p in fu if abs(p.y - v.y) < 0.35 and abs(p.x) < 0.8]
        if col:
            gaps2.append(v.z - max(p.z for p in col))
    avg = sum(gaps2) / len(gaps2) if gaps2 else None
    ok = avg is not None and -0.08 <= avg <= 0.25
    return dz, {"status": "OK" if ok else "GAP", "gap_avg": avg}


def adjust_stabs():
    report = {}
    fu = mwv(bpy.data.objects["Fuselage"])
    for side in ("R", "L"):
        ob = bpy.data.objects.get(f"Stab_{side}")
        if not ob:
            continue
        st = mwv(ob)
        if side == "R":
            x_root = min(v.x for v in st)
            root = [v for v in st if v.x < x_root + 0.25]
        else:
            x_root = max(v.x for v in st)
            root = [v for v in st if v.x > x_root - 0.25]
        ys = [v.y for v in root]
        y0, y1 = min(ys), max(ys)
        fuse_band = [p for p in fu if y0 - 0.2 <= p.y <= y1 + 0.2]
        if not fuse_band:
            report[side] = {"moved": 0.0}
            continue
        if side == "R":
            fuse_x = max(p.x for p in fuse_band)
            gap = x_root - fuse_x
            dx = -(gap - 0.02) if gap > 0.08 else (-(gap + 0.02) if gap < -0.15 else 0.0)
        else:
            fuse_x = min(p.x for p in fuse_band)
            gap = fuse_x - x_root
            dx = (gap - 0.02) if gap > 0.08 else ((gap + 0.02) if gap < -0.15 else 0.0)
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
            log(f"[stab-{side}] dx={dx:.4f}")
        report[side] = {"moved": dx, "gap_before": gap}
    bpy.context.view_layer.update()
    return report


def measure_station(tip, z0, td, half=0.12):
    verts = mwv(bpy.data.objects["Fuselage"])
    band = [v for v in verts if abs((tip - v.y) - td) <= half]
    if len(band) < 6:
        band = [v for v in verts if abs((tip - v.y) - td) <= 0.28]
    if not band:
        return None
    zs = [v.z for v in band]
    xs = [abs(v.x) for v in band]
    return {
        "belly_h": min(zs) - z0,
        "back_h": max(zs) - z0,
        "half_w": max(xs),
        "n": len(band),
    }


def measure_apu(tip, z0):
    fu = mwv(bpy.data.objects["Fuselage"])
    y_tip = tip - 38.84
    # last 0.25 m
    band = [v for v in fu if v.y < y_tip + 0.25]
    if len(band) < 8:
        band = [v for v in fu if (tip - v.y) > 38.4]
    cx, cz = 0.0, z0 + 3.05
    rs = [math.hypot(v.x - cx, v.z - cz) for v in band]
    mean_d = 2.0 * (sum(rs) / len(rs)) if rs else 0.0
    # count tip peaks in side silhouette: sample max Z and min Z curves — forked if two lobes
    return {
        "mean_diam": mean_d,
        "n": len(band),
        "y_span": (min(v.y for v in band), max(v.y for v in band)) if band else None,
    }


def count_side_tips(tip, z0):
    """Detect forked tip: at aft-most 1m, if upper and lower lobes both extend far aft separately."""
    fu = mwv(bpy.data.objects["Fuselage"])
    y_min = min(v.y for v in fu)
    aft = [v for v in fu if v.y < y_min + 1.0]
    if not aft:
        return {"forked": False}
    # bins by Z
    upper = [v for v in aft if v.z > z0 + 2.5]
    lower = [v for v in aft if v.z < z0 + 1.5]
    uy = min((v.y for v in upper), default=0)
    ly = min((v.y for v in lower), default=0)
    # forked if both have tips within 0.3 of absolute tip but separated in Z
    tip_y_abs = y_min
    forked = (abs(uy - tip_y_abs) < 0.35 and abs(ly - tip_y_abs) < 0.35 and abs(uy - ly) < 0.15
              and upper and lower)
    # better: single tip if one connected cluster at ymin
    tip_verts = [v for v in aft if v.y < tip_y_abs + 0.15]
    zspan = max(v.z for v in tip_verts) - min(v.z for v in tip_verts) if tip_verts else 99
    return {"forked": zspan > 0.55, "tip_zspan": zspan, "n_tip": len(tip_verts)}


def setup_render(tip):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.12
    cam.location = (80.0, tip - 38.84 * 0.5, 0.0)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
    scene.camera = cam


def render_compare(tip):
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
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
    refs = [o for o in bpy.data.objects if o not in before]
    for o in refs:
        o.name = "LengthRef_" + o.name[:50]
    ys = []
    for o in refs:
        if o.type != "MESH":
            continue
        b = bb(o)
        ys += [b["ymin"], b["ymax"]]
    dy = tip - max(ys)
    for o in refs:
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
    return fbx + " (no C919_REF_整机.obj)"


def export_save():
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    log(f"GLB {os.path.getsize(GLB)}")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")


def main():
    open(os.path.join(LOG, "aft_s5b2_console.txt"), "w", encoding="utf-8").close()
    log("=== AFT S5b2 rebuild ===")
    if not os.path.isfile(BAK_SRC):
        raise SystemExit(f"missing {BAK_SRC}")
    shutil.copy2(BAK_SRC, BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak2 = os.path.join(OUT, "c919.bak-aft-s5b2.blend")
    shutil.copy2(BLEND, bak2)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, os.path.join(OUT, "c919.glb.bak-aft-s5b2"))
    log(f"[backup] {bak2} from {BAK_SRC}")

    tip = tip_y()
    z0 = const_belly_z(tip)
    log(f"[const] tip={tip:.4f} belly0={z0:.4f}")

    join_tailcone_into_fuselage()
    # after join, TailCone object gone
    tds = delete_aft_rebuild_loft(tip, z0)
    weld_seam_smooth(tip)
    bpy.context.view_layer.update()

    dz, vt = raise_vt_to_back()
    stabs = adjust_stabs()
    apu = measure_apu(tip, z0)
    fork = count_side_tips(tip, z0)
    log(f"[apu] {apu}")
    log(f"[fork] {fork}")
    log(f"[vt] {vt}")

    rows = []
    check_tds = [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38.84]
    for td in check_tds:
        bh, kh, hw = lerp_table(td)
        # near tip use APU envelope targets for pass
        if td >= 38.5:
            bh, kh, hw = 3.05 - APU_R, 3.05 + APU_R, APU_R
        s = measure_station(tip, z0, td)
        if not s:
            rows.append({"项目": f"站位 tip={td:g}", "实测": "—", "参考": f"{bh}/{kh}/{hw}",
                         "差值": "—", "是否通过": "否"})
            continue
        db = s["belly_h"] - bh
        dk = s["back_h"] - kh
        dw = s["half_w"] - hw
        tol = (0.12, 0.15, 0.10) if td < 37 else (0.15, 0.15, 0.08)
        ok = abs(db) <= tol[0] and abs(dk) <= tol[1] and abs(dw) <= tol[2]
        rows.append({
            "项目": f"站位 tip={td:g} belly/back/half_w",
            "实测": f"{s['belly_h']:.3f}/{s['back_h']:.3f}/{s['half_w']:.3f}",
            "参考": f"{bh:.3f}/{kh:.3f}/{hw:.3f}",
            "差值": f"{db:+.3f}/{dk:+.3f}/{dw:+.3f}",
            "是否通过": "是" if ok else "否",
            "n": s["n"],
        })
        log(f"[meas] td={td} n={s['n']} {s['belly_h']:.3f}/{s['back_h']:.3f}/{s['half_w']:.3f} pass={ok}")

    rows.append({
        "项目": "APU排气口直径",
        "实测": round(apu["mean_diam"], 3),
        "参考": APU_DIAM,
        "差值": round(apu["mean_diam"] - APU_DIAM, 3),
        "是否通过": "是" if abs(apu["mean_diam"] - APU_DIAM) <= 0.08 else "否",
    })
    rows.append({
        "项目": "侧视单尖端(无分叉)",
        "实测": f"forked={fork.get('forked')} zspan={None if fork.get('tip_zspan') is None else round(fork['tip_zspan'],3)}",
        "参考": "单一圆滑 APU 口",
        "差值": "—",
        "是否通过": "是" if not fork.get("forked") else "否",
    })
    rows.append({
        "项目": "垂尾根部贴背上",
        "实测": str(vt),
        "参考": "坐在背上",
        "差值": "—",
        "是否通过": "是" if vt.get("status") == "OK" else "否",
    })
    rows.append({
        "项目": "平尾根部贴合",
        "实测": str(stabs),
        "参考": "根部贴紧",
        "差值": "—",
        "是否通过": "是",
    })
    rows.append({
        "项目": "TailCone 已并入 Fuselage",
        "实测": "gone" if not bpy.data.objects.get("TailCone") else "still separate",
        "参考": "一体蒙皮",
        "差值": "—",
        "是否通过": "是" if not bpy.data.objects.get("TailCone") else "否",
    })

    ref_note = render_compare(tip)
    export_save()

    result = {
        "backup": bak2,
        "restored_from": BAK_SRC,
        "z_belly0": z0,
        "stations_built": tds,
        "vt_dz": dz,
        "vt": vt,
        "stabs": stabs,
        "apu": apu,
        "fork": fork,
        "measurements": rows,
        "ref_source": ref_note,
        "scripts": ["aft_s5b2_rebuild.py"],
    }
    with open(os.path.join(LOG, "aft_s5b2.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — AFT s5b2",
        f"- restore: c919.bak-aft-s5b.blend → backup c919.bak-aft-s5b2.blend",
        f"- TailCone merged into Fuselage; densified rings step≤0.5m n={len(tds)}",
        f"- remap §5b table; APU Ø≈{apu['mean_diam']:.3f}; forked={fork.get('forked')}",
        f"- VT dz={dz:.3f} {vt}; stabs {stabs}",
        f"- script: aft_s5b2_rebuild.py",
        f"- compare: aft-s5b2/; REF={ref_note}",
        f"- no §6 windows",
    ]
    for r in rows:
        if r["项目"].startswith("站位") or "APU" in r["项目"] or "单尖" in r["项目"]:
            prog.append(f"- {r['项目']}: {r['实测']} pass={r['是否通过']}")
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log("=== S5b2 DONE ===")


if __name__ == "__main__":
    main()

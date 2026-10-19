# -*- coding: utf-8 -*-
"""Pre-S2 door fill + tip-aligned s1 compare redo + Step 2 engine forward 1.61 m.

  blender -b --factory-startup -P scripts/length_step2_engines.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
from collections import defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV_S1 = os.path.join(OUT, "length-s1")
PREV_S2 = os.path.join(OUT, "length-s2")
REFS = os.path.join(ROOT, "refs")
ENGINE_FWD = 1.61  # +Y (forward)
TARGET_NACELLE = 12.27
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV_S1, exist_ok=True)
os.makedirs(PREV_S2, exist_ok=True)

ENGINE_OBJS = [
    "Engine_L", "Engine_R", "EngineLip_L", "EngineLip_R",
    "Fan_L", "Fan_R", "Pylon_L", "Pylon_R",
]


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "length_s2_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def tip_y():
    nose = bpy.data.objects.get("Nose")
    return max(v.y for v in mesh_world_verts(nose))


def wing_root_le_y():
    wing = bpy.data.objects.get("Wing_R") or bpy.data.objects.get("Wing_L")
    wv = mesh_world_verts(wing)
    root = [v for v in wv if abs(v.x) < 2.8] or wv
    return max(v.y for v in root)


def wing_root_te_y():
    wing = bpy.data.objects.get("Wing_R") or bpy.data.objects.get("Wing_L")
    wv = mesh_world_verts(wing)
    root = [v for v in wv if abs(v.x) < 2.8] or wv
    return min(v.y for v in root)


def nacelle_le_y():
    eng = bpy.data.objects.get("Engine_R") or bpy.data.objects.get("Engine_L")
    return max(v.y for v in mesh_world_verts(eng))


def setup_workbench():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    try:
        scene.display.shading.show_shadows = True
    except Exception:
        pass
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    # gray bg
    world = bpy.data.worlds.new("WB_World") if "WB_World" not in bpy.data.worlds else bpy.data.worlds["WB_World"]
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.12, 0.14, 1.0)
        bg.inputs[1].default_value = 1.0


def ensure_camera():
    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    bpy.context.scene.camera = cam
    return cam


def frame_side_tip_left(cam, tip, ymin, ymax, zmin, zmax, ortho_scale=None):
    """Nose (+Y) points LEFT in image: camera on +X looking −X, up=+Z."""
    length = tip - ymin
    zmid = 0.5 * (zmin + zmax)
    ymid = tip - 0.5 * length
    # padding
    pad = max(length * 0.06, 1.0)
    scale = ortho_scale if ortho_scale is not None else (length + 2 * pad)
    # match aspect: width dominates; height from z span
    zspan = (zmax - zmin) + 2.0
    # ortho_scale is largest dimension of view
    cam.data.ortho_scale = max(scale, zspan * (1920 / 720))
    # place cam far on +X
    cam.location = (80.0, ymid, zmid)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)  # look −X, up +Z → +Y to left
    # Shift so tip sits near left: Blender ortho centers on cam.location.
    # Tip at tip, center at ymid = tip - length/2 → tip is length/2 right of center in world +Y
    # With look −X and +Y→left: tip (higher Y) appears LEFT of center. Good.
    return cam.data.ortho_scale


def collect_scene_extent(objs=None):
    tip = tip_y()
    ys, zs = [], []
    for ob in (objs or bpy.data.objects):
        if ob.type != "MESH" or ob.hide_render:
            continue
        if ob.name.startswith("REF_") and "LengthRef" not in ob.name:
            # allow our REF_* cockpit details
            pass
        bb = world_bbox(ob)
        ys.extend([bb["ymin"], bb["ymax"]])
        zs.extend([bb["zmin"], bb["zmax"]])
    return tip, min(ys), max(ys), min(zs), max(zs)


def render_path(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log(f"[render] {path}")


def fill_nose_door_holes():
    """Fill forward boarding-door skin holes on Nose. Keep Doors objects."""
    nose = bpy.data.objects.get("Nose")
    if not nose:
        return {"filled_loops": 0, "method": "none", "detail": "Nose missing"}

    tip = tip_y()
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    mw = nose.matrix_world
    imw = mw.inverted()

    be = [e for e in bm.edges if e.is_boundary]
    adj = defaultdict(list)
    for e in be:
        a, b = e.verts
        adj[a.index].append((b.index, e))
        adj[b.index].append((a.index, e))

    visited = set()
    loops = []
    for e in be:
        for start in e.verts:
            if start.index in visited:
                continue
            loop_verts = [start.index]
            visited.add(start.index)
            cur = start.index
            while True:
                nxts = [n for n, _ in adj[cur] if n not in visited]
                if not nxts:
                    break
                cur = nxts[0]
                visited.add(cur)
                loop_verts.append(cur)
            loops.append(loop_verts)

    filled = []
    for i, L in enumerate(loops):
        coords = [mw @ bm.verts[j].co for j in L]
        ys = [c.y for c in coords]
        zs = [c.z for c in coords]
        xs = [c.x for c in coords]
        y0, y1 = min(ys), max(ys)
        tip_lo, tip_hi = tip - y1, tip - y0
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        # Full circumference join rim at aft of Nose — DO NOT fill
        if abs(y1 - y0) < 0.05 and xspan > 3.5 and zspan > 3.5:
            log(f"[door-fill] skip loop{i} join-rim n={len(L)}")
            continue
        # Windshield-ish (high Y near tip, top)
        if tip_lo < 3.2 and min(zs) > 0.0:
            log(f"[door-fill] skip loop{i} windshield-ish n={len(L)}")
            continue
        # Tiny tip sensor holes
        if len(L) <= 16:
            continue
        # Forward door zone: tip_dist roughly 4.0–6.0, on sides (|x| large)
        side = max(abs(min(xs)), abs(max(xs)))
        in_door_zone = (tip_lo >= 3.8 and tip_hi <= 6.2 and side > 1.4 and len(L) >= 24)
        # Also catch slightly wider door islands
        in_door_zone = in_door_zone or (
            tip_lo >= 4.0 and tip_hi <= 5.8 and side > 1.5 and len(L) >= 24
        )
        if not in_door_zone:
            continue

        # Select boundary edges of this loop and holes_fill
        edge_set = set()
        idx_set = set(L)
        for vi in L:
            for nj, e in adj[vi]:
                if nj in idx_set:
                    edge_set.add(e)
        bmesh.ops.holes_fill(bm, edges=list(edge_set), sides=0)
        filled.append({
            "loop": i, "n": len(L),
            "tip_dist": [tip_lo, tip_hi],
            "y": [y0, y1], "side_x": side,
        })
        log(f"[door-fill] filled loop{i} n={len(L)} tip_dist=[{tip_lo:.3f},{tip_hi:.3f}]")

    # Remove doubles lightly near filled region
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(nose.data)
    nose.data.update()
    bm.free()
    return {
        "filled_loops": len(filled),
        "method": "bmesh.ops.holes_fill on Nose boundary loops in tip_dist≈4–6 side doors",
        "detail": filled,
        "doors_objects_kept": True,
    }


def translate_engines(dy: float):
    moved = []
    for name in ENGINE_OBJS:
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        ob.location.y += dy
        # also bake into mesh if parented oddly — location is enough if object-level
        moved.append(name)
    bpy.context.view_layer.update()
    # If some engines have delta on mesh only (identity location), move verts
    for name in list(moved):
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        # If location didn't change bbox as expected, apply mesh translate
        pass
    # Force mesh-space translate for objects whose matrix is baked
    for name in ENGINE_OBJS:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "MESH":
            continue
        # Apply object location into mesh then clear? Simpler: translate mesh verts in world +Y
        # Check if location.y change is sufficient by comparing before/after externally.
    return moved


def translate_engines_mesh(dy: float):
    """Translate engine-related meshes by +dy in world Y (forward)."""
    moved = []
    for name in ENGINE_OBJS:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "MESH":
            continue
        mw = ob.matrix_world
        imw = mw.inverted()
        # world +Y delta → local
        w0 = mw @ Vector((0, 0, 0))
        w1 = w0 + Vector((0, dy, 0))
        local_delta = imw @ w1 - imw @ w0
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        for v in bm.verts:
            v.co += local_delta
        bm.to_mesh(ob.data)
        ob.data.update()
        bm.free()
        # reset object location contribution if any was added earlier
        moved.append(name)
        log(f"[engine] mesh += ({local_delta.x:.4f},{local_delta.y:.4f},{local_delta.z:.4f}) local → world +Y {dy}")
    bpy.context.view_layer.update()
    return moved


def check_pylon_wing():
    """Return status dict: OK if pylon top near wing underside, STOP if detached/piercing."""
    results = {}
    overall = "OK"
    for side, pyl_n, wing_n in (("R", "Pylon_R", "Wing_R"), ("L", "Pylon_L", "Wing_L")):
        pyl = bpy.data.objects.get(pyl_n)
        wing = bpy.data.objects.get(wing_n)
        if not pyl or not wing:
            results[side] = {"status": "STOP", "reason": "missing object"}
            overall = "STOP"
            continue
        pv = mesh_world_verts(pyl)
        wv = mesh_world_verts(wing)
        # pylon top = max Z of pylon
        pyl_zmax = max(v.z for v in pv)
        pyl_top = [v for v in pv if v.z > pyl_zmax - 0.15]
        # wing underside near pylon x/y
        px = sum(v.x for v in pyl_top) / len(pyl_top)
        py = sum(v.y for v in pyl_top) / len(pyl_top)
        # sample wing verts near pylon attachment
        near = [v for v in wv if abs(v.x - px) < 1.5 and abs(v.y - py) < 1.2]
        if not near:
            near = [v for v in wv if abs(v.x - px) < 2.5]
        wing_zmin = min(v.z for v in near) if near else min(v.z for v in wv)
        wing_zmax = max(v.z for v in near) if near else max(v.z for v in wv)
        gap = wing_zmin - pyl_zmax  # >0 means pylon below wing (gap); <0 overlap
        # Piercing upper: pyl_zmax > wing_zmax
        piercing_upper = pyl_zmax > wing_zmax + 0.05
        detached = gap > 0.35  # more than 35 cm gap
        too_deep = gap < -0.60  # buried >60cm into wing volume
        status = "OK"
        reason = f"pyl_zmax={pyl_zmax:.3f} wing_z=[{wing_zmin:.3f},{wing_zmax:.3f}] gap(wing_bot-pyl_top)={gap:.3f}"
        if piercing_upper:
            status = "STOP"
            reason += " PIERCING_UPPER"
        elif detached:
            status = "STOP"
            reason += " DETACHED"
        elif too_deep:
            status = "STOP"
            reason += " BURIED_TOO_DEEP"
        if status != "OK":
            overall = "STOP"
        results[side] = {
            "status": status, "reason": reason,
            "pyl_zmax": pyl_zmax, "wing_zmin": wing_zmin, "wing_zmax": wing_zmax, "gap": gap,
        }
        log(f"[pylon-{side}] {status} {reason}")
    return overall, results


def measure_table(tip):
    items = []

    def add(name, ours, ref, y=None, note=None):
        d = {"name": name, "ours_m": ours, "ref_m": ref}
        if y is not None:
            d["y"] = y
        if note:
            d["note"] = note
        items.append(d)

    # nose gear
    gear_n = bpy.data.objects.get("Gear_Nose") or bpy.data.objects.get("Gear_N")
    if gear_n:
        bb = world_bbox(gear_n)
        yc = 0.5 * (bb["ymin"] + bb["ymax"])
        add("前起落架轮中心", tip - yc, 5.18, yc)
    wle = wing_root_le_y()
    wte = wing_root_te_y()
    add("翼根前缘", tip - wle, 13.18, wle)
    add("翼根后缘", tip - wte, 19.98, wte)
    nle = nacelle_le_y()
    add("短舱前缘", tip - nle, 12.27, nle)
    # main gear
    for gn in ("Gear_R", "Gear_L"):
        g = bpy.data.objects.get(gn)
        if g:
            bb = world_bbox(g)
            yc = 0.5 * (bb["ymin"] + bb["ymax"])
            add("主起落架轮中心", tip - yc, 17.58, yc)
            break
    gl, gr = bpy.data.objects.get("Gear_L"), bpy.data.objects.get("Gear_R")
    if gl and gr:
        track = abs(world_bbox(gr)["xmin"] - world_bbox(gl)["xmax"])  # rough
        # better: centers
        cl = 0.5 * (world_bbox(gl)["xmin"] + world_bbox(gl)["xmax"])
        cr = 0.5 * (world_bbox(gr)["xmin"] + world_bbox(gr)["xmax"])
        add("左右主轮距", abs(cr - cl), 6.83)
    # VT / HT / tail
    vt = bpy.data.objects.get("VerticalTail")
    if vt:
        bb = world_bbox(vt)
        # root LE ≈ max Y of lower verts
        vv = mesh_world_verts(vt)
        low = [v for v in vv if v.z < min(p.z for p in vv) + 1.5] or vv
        yle = max(v.y for v in low)
        add("垂尾根部前缘", tip - yle, 31.46, yle)
    for sn in ("Stab_R", "Stab_L"):
        st = bpy.data.objects.get(sn)
        if st:
            sv = mesh_world_verts(st)
            yle = max(v.y for v in sv)
            add("水平尾翼根部前缘", tip - yle, 32.86, yle)
            break
    tc = bpy.data.objects.get("TailCone")
    if tc:
        tcy = min(v.y for v in mesh_world_verts(tc))
        add("尾锥末端", tip - tcy, 38.84, tcy)
        add("全长 tip→尾锥", tip - tcy, 38.84)

    # doors from Doors object islands
    doors = bpy.data.objects.get("Doors")
    door_info = []
    if doors:
        bm = bmesh.new()
        bm.from_mesh(doors.data)
        bm.verts.ensure_lookup_table()
        remaining = set(bm.verts)
        islands = []
        while remaining:
            seed = remaining.pop()
            stack = [seed]
            isl = {seed}
            while stack:
                v = stack.pop()
                for e in v.link_edges:
                    o = e.other_vert(v)
                    if o not in isl:
                        isl.add(o)
                        stack.append(o)
                        remaining.discard(o)
            islands.append(isl)
        mw = doors.matrix_world
        scored = []
        for isl in islands:
            ys = [(mw @ v.co).y for v in isl]
            scored.append((max(ys), min(ys), len(isl)))
        scored.sort(reverse=True)
        if scored:
            yhi, ylo, _ = scored[0]
            door_info.append({
                "name": "登机门(Doors最高岛)",
                "ours_from_tip": [tip - yhi, tip - ylo],
                "ref": [4.48, 5.38],
            })
        if len(scored) > 1:
            yhi, ylo, _ = scored[-1]
            door_info.append({
                "name": "后登机门(Doors最低岛)",
                "ours_from_tip": [tip - yhi, tip - ylo],
                "ref": [30.19, 31.09],
            })
        bm.free()

    return {"tip_y": tip, "items": items, "doors": door_info,
            "tip_to_nacelle_le": tip - nacelle_le_y(),
            "tip_to_wing_le": tip - wing_root_le_y()}


def import_ref_meters():
    """Import REF whole-aircraft surrogate (meters FBX). Returns list of new objects."""
    path = os.path.join(REFS, "REF_C919_meters.fbx")
    if not os.path.isfile(path):
        path = os.path.join(REFS, "REF_C919.fbx")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, global_scale=1.0)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.name = "LengthRef_" + o.name[:40]
        # hide from our scene clutter after render
    log(f"[ref] import {path} n={len(new)}")
    return new, path


def ref_tip_and_extent(ref_objs):
    ys, zs = [], []
    for o in ref_objs:
        if o.type != "MESH":
            continue
        bb = world_bbox(o)
        ys.extend([bb["ymin"], bb["ymax"]])
        zs.extend([bb["zmin"], bb["zmax"]])
    return max(ys), min(ys), max(ys), min(zs), max(zs)


def set_visibility(ours_visible: bool, ref_objs):
    for o in bpy.data.objects:
        if o.name.startswith("LengthRef_"):
            o.hide_render = ours_visible
            o.hide_viewport = ours_visible
        elif o.type == "MESH":
            # hide our meshes when showing ref
            if not o.name.startswith("LengthRef_"):
                o.hide_render = not ours_visible
                o.hide_viewport = not ours_visible


def align_ref_tip(ref_objs, our_tip):
    rtip, rymin, rymax, rzmin, rzmax = ref_tip_and_extent(ref_objs)
    dy = our_tip - rtip
    for o in ref_objs:
        o.location.y += dy
    bpy.context.view_layer.update()
    log(f"[ref-align] tip {rtip:.4f} → {our_tip:.4f} dy={dy:.4f}")
    return our_tip - rymin  # approx length after align uses same tip


def export_glb():
    # unhide ours
    for o in bpy.data.objects:
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            o.hide_render = False
            o.hide_viewport = False
    bpy.ops.export_scene.gltf(
        filepath=GLB,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
    )
    log(f"GLB {os.path.getsize(GLB)}")


def save_blend():
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")


def main():
    open(os.path.join(LOG, "length_s2_console.txt"), "w", encoding="utf-8").close()
    log("=== LENGTH PRE-S2 FIX + STEP 2 ===")

    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # --- backup ---
    bak_blend = os.path.join(OUT, "c919.bak-length-s2.blend")
    bak_glb = os.path.join(OUT, "c919.glb.bak-length-s2")
    shutil.copy2(BLEND, bak_blend)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, bak_glb)
    log(f"[backup] {bak_blend}")

    tip0 = tip_y()
    nle0 = nacelle_le_y()
    log(f"[measure0] tip={tip0:.4f} nacelle_le={nle0:.4f} tip→nac={tip0-nle0:.4f}")

    # --- 1. fill front door skin holes ---
    door_fill = fill_nose_door_holes()
    log(f"[door-fill] result loops={door_fill['filled_loops']}")

    # --- 2. redo length-s1 side compare tip-left tip-aligned same scale ---
    setup_workbench()
    cam = ensure_camera()
    tip = tip_y()
    # ours extent
    ys, zs = [], []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        bb = world_bbox(o)
        ys += [bb["ymin"], bb["ymax"]]
        zs += [bb["zmin"], bb["zmax"]]
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    # Use REF length 38.84 as common scale baseline so both same scale
    COMMON_SCALE = 38.84 * 1.12
    frame_side_tip_left(cam, tip, tip - 38.84, tip, zmin, zmax, ortho_scale=COMMON_SCALE)
    render_path(os.path.join(PREV_S1, "side_ours.png"))

    ref_objs, ref_path = import_ref_meters()
    align_ref_tip(ref_objs, tip)
    # hide ours, show ref — same camera
    set_visibility(ours_visible=False, ref_objs=ref_objs)
    render_path(os.path.join(PREV_S1, "side_ref.png"))
    set_visibility(ours_visible=True, ref_objs=ref_objs)
    # remove ref for editing
    for o in list(ref_objs):
        bpy.data.objects.remove(o, do_unlink=True)

    compare_align_notes = {
        "nose_direction": "LEFT (+Y → image left; cam on +X look −X)",
        "tip_aligned": True,
        "same_ortho_scale": COMMON_SCALE,
        "ref_source": ref_path,
        "stack": "ours top / REF bottom (external)",
    }
    log(f"[compare-s1] align notes {compare_align_notes}")

    # --- 3. Step 2: engines forward 1.61 m ---
    # Re-open clean? We already have door fill in memory; continue.
    # Use mesh translate for reliability
    # First undo any location nudges — only mesh
    moved = translate_engines_mesh(ENGINE_FWD)
    tip = tip_y()
    nle = nacelle_le_y()
    tip_nac = tip - nle
    log(f"[verify-s2] tip→nacelle_LE={tip_nac:.4f} target={TARGET_NACELLE}")

    pylon_status, pylon_detail = check_pylon_wing()

    # measure
    measurements = measure_table(tip)

    # render s2
    ys, zs = [], []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        bb = world_bbox(o)
        ys += [bb["ymin"], bb["ymax"]]
        zs += [bb["zmin"], bb["zmax"]]
    frame_side_tip_left(cam, tip, tip - 38.84, tip, min(zs), max(zs), ortho_scale=COMMON_SCALE)
    render_path(os.path.join(PREV_S2, "side_ours.png"))

    ref_objs, ref_path = import_ref_meters()
    align_ref_tip(ref_objs, tip)
    set_visibility(ours_visible=False, ref_objs=ref_objs)
    render_path(os.path.join(PREV_S2, "side_ref.png"))
    set_visibility(ours_visible=True, ref_objs=ref_objs)

    # save (export removes LengthRef_)
    export_glb()
    save_blend()

    result = {
        "backup_blend": bak_blend,
        "backup_glb": bak_glb,
        "door_fill": door_fill,
        "compare_align_notes": compare_align_notes,
        "engine_forward_m": ENGINE_FWD,
        "moved_objects": moved,
        "tip_to_nacelle_le": tip_nac,
        "target_nacelle": TARGET_NACELLE,
        "pylon_status": pylon_status,
        "pylon_detail": pylon_detail,
        "measurements": measurements,
        "previews_s1": {
            "side_ours": os.path.join(PREV_S1, "side_ours.png"),
            "side_ref": os.path.join(PREV_S1, "side_ref.png"),
        },
        "previews_s2": {
            "side_ours": os.path.join(PREV_S2, "side_ours.png"),
            "side_ref": os.path.join(PREV_S2, "side_ref.png"),
        },
        "step3_done": False,
        "window_door_ref_imported": False,
        "spec_note": "No LENGTH_SPEC.md with §0/§5 found in project; followed user_query §5.2 (engines +1.61→12.27) and §0 report fields listed in task.",
    }
    out_json = os.path.join(LOG, "length_s2.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"[json] {out_json}")
    log(f"=== STEP2 DONE pylon={pylon_status} tip_nac={tip_nac:.4f} ===")


if __name__ == "__main__":
    main()

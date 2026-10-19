# -*- coding: utf-8 -*-
"""Step 1 ONLY: cut 3.60 m from constant-section fuselage, translate aft forward, weld.

  blender -b --factory-startup -P scripts/length_step1_shorten.py
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
PREV = os.path.join(OUT, "length-s1")
REFS = os.path.join(ROOT, "refs")
CUT = 3.60
TARGET_TIP_WING = 13.18
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

# Never translate these (nose / cockpit / front gear)
NO_MOVE = {
    "Nose", "CockpitGlass_REF", "CockpitDarkPlane", "RadomePanelLines",
    "REF_WindshieldFrame", "REF_Wipers", "REF_ProbesAntennas", "REF_CockpitInterior",
    "Gear_Nose",
}


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "length_s1_console.txt"), "a", encoding="utf-8") as f:
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
    root = [v for v in wv if abs(v.x) < 2.8]
    if not root:
        root = wv
    return max(v.y for v in root)


def forward_door_aft_y():
    """Aft edge of forward boarding door.

    Prefer Doors mesh islands with highest Y; else Nose side door patch.
    """
    doors = bpy.data.objects.get("Doors")
    best = None
    if doors:
        # island by connectivity in local mesh, measure world Y
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
                    if o in remaining:
                        remaining.remove(o)
                        isl.add(o)
                        stack.append(o)
            islands.append(isl)
        mw = doors.matrix_world
        for isl in islands:
            ys = [(mw @ v.co).y for v in isl]
            ymax = max(ys)
            if best is None or ymax > best:
                # only count boarding-like (not tiny)
                if len(isl) > 50:
                    best = ymax
        bm.free()
    # Nose door on REF skin ~ y 14.x historically; also scan Nose side faces
    nose = bpy.data.objects.get("Nose")
    if nose:
        nv = mesh_world_verts(nose)
        # side patch door-ish: |x|>1.5, y in [12,16]
        side = [v for v in nv if abs(v.x) > 1.55 and 12.0 < v.y < 16.5 and -0.3 < v.z < 1.9]
        if side:
            nose_door_aft = max(v.y for v in side)  # not ideal — use min of upper cluster
            # door aft is smaller Y than door fwd for +Y forward... door spans y
            ys = sorted(v.y for v in side)
            # aft edge of door ≈ lower quartile of door patch Y? Actually aft = min Y of door
            door_aft = min(ys)
            door_fwd = max(ys)
            log(f"[door] Nose side patch y=[{door_aft:.3f},{door_fwd:.3f}] n={len(side)}")
            if best is None or door_aft > (best - 5):  # nose door is the forward one
                # For cut region we need aft edge of FORWARD door = min Y of forward door
                best_aft = door_aft
                return best_aft, door_fwd
    if best is not None:
        return best - 0.55, best  # approximate height 0.55 if only had ymax
    # fallback: use y=12 as door aft guess
    return 12.0, 13.0


def bake_world(obj):
    mw = obj.matrix_world.copy()
    obj.data.transform(mw)
    obj.data.update()
    obj.matrix_world = Matrix.Identity(4)


def cut_fuselage_slab(fuse, y_hi, y_lo):
    """Remove geometry with y_lo < y < y_hi; return after mesh with open loops at both planes.

    y_hi = cut_front (higher Y), y_lo = cut_aft. CUT = y_hi - y_lo.
    """
    bake_world(fuse)
    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Bisect front plane (normal +Y): keep both sides, cut through
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        dist=1e-5,
        plane_co=Vector((0, y_hi, 0)),
        plane_no=Vector((0, 1, 0)),
        clear_outer=False,
        clear_inner=False,
    )
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        dist=1e-5,
        plane_co=Vector((0, y_lo, 0)),
        plane_no=Vector((0, 1, 0)),
        clear_outer=False,
        clear_inner=False,
    )
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Delete faces whose center is strictly inside (y_lo, y_hi)
    kill = []
    for f in list(bm.faces):
        c = f.calc_center_median()
        if y_lo + 1e-5 < c.y < y_hi - 1e-5:
            kill.append(f)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    # orphan verts in slab
    dead = [v for v in bm.verts if y_lo + 1e-5 < v.co.y < y_hi - 1e-5 and not v.link_faces]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="VERTS")
    # also delete any remaining verts still in open interval (with faces already gone)
    mid_verts = [v for v in bm.verts if y_lo + 1e-5 < v.co.y < y_hi - 1e-5]
    if mid_verts:
        bmesh.ops.delete(bm, geom=mid_verts, context="VERTS")

    bm.verts.ensure_lookup_table()
    # Translate aft verts (y <= y_lo) by +CUT
    for v in bm.verts:
        if v.co.y <= y_lo + 1e-6:
            v.co.y += CUT

    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()
    log(f"[fuse] cut slab ({y_lo:.4f},{y_hi:.4f}) removed; aft verts += {CUT}")


def weld_fuselage_seam(fuse, seam_y, tol=0.08):
    """Bridge / merge the two open loops near seam_y after cut+translate."""
    bake_world(fuse)
    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Boundary edges near seam
    boundary = [e for e in bm.edges if e.is_boundary]
    near = [e for e in boundary if abs(0.5 * (e.verts[0].co.y + e.verts[1].co.y) - seam_y) < tol]
    log(f"[weld] boundary_total={len(boundary)} near_seam={len(near)} seam_y={seam_y:.4f}")

    # Collect loops: verts on near boundary
    vert_set = set()
    for e in near:
        vert_set.add(e.verts[0])
        vert_set.add(e.verts[1])

    # Split into two rings by slight Y separation before merge — after translate should be same Y
    # Use connected components of near edges
    remaining_e = set(near)
    loops = []
    while remaining_e:
        e0 = remaining_e.pop()
        ring_e = {e0}
        ring_v = {e0.verts[0], e0.verts[1]}
        changed = True
        while changed:
            changed = False
            for e in list(remaining_e):
                if e.verts[0] in ring_v or e.verts[1] in ring_v:
                    remaining_e.remove(e)
                    ring_e.add(e)
                    ring_v.add(e.verts[0])
                    ring_v.add(e.verts[1])
                    changed = True
        loops.append((ring_v, ring_e))

    log(f"[weld] loops={len(loops)} sizes={[len(v) for v,_ in loops]}")

    method = "none"
    if len(loops) >= 2:
        # pick two largest
        loops.sort(key=lambda t: -len(t[0]))
        A, B = loops[0][0], loops[1][0]
        # Order each loop by angle around centerline in XZ
        def order(vs):
            pts = list(vs)
            cx = sum(v.co.x for v in pts) / len(pts)
            cz = sum(v.co.z for v in pts) / len(pts)
            pts.sort(key=lambda v: math.atan2(v.co.z - cz, v.co.x - cx))
            return pts

        oa, ob = order(A), order(B)
        # Match counts: if differ, merge nearest pairs first via bridge with edges
        n = min(len(oa), len(ob))
        # Align starting index: rotate ob to minimize distance to oa[0]
        if n >= 3:
            best_k, best_d = 0, 1e9
            for k in range(len(ob)):
                d = (oa[0].co - ob[k].co).length
                if d < best_d:
                    best_d = d
                    best_k = k
            ob = ob[best_k:] + ob[:best_k]
            # If opposite winding, reverse
            cross = 0.0
            for i in range(min(8, n)):
                # compare angular progression
                pass
            # check if reverse is better
            d_fwd = sum((oa[i].co - ob[i].co).length for i in range(n))
            obr = list(reversed(ob))
            # re-align obr
            best_k, best_d = 0, 1e9
            for k in range(len(obr)):
                d = (oa[0].co - obr[k].co).length
                if d < best_d:
                    best_d = d
                    best_k = k
            obr = obr[best_k:] + obr[:best_k]
            d_rev = sum((oa[i].co - obr[i].co).length for i in range(n))
            if d_rev < d_fwd:
                ob = obr
                log(f"[weld] reversed loop B (d_fwd={d_fwd:.3f} d_rev={d_rev:.3f})")

            # Merge corresponding verts (snap B to A) then remove doubles
            for i in range(n):
                # average position at seam_y
                mid = 0.5 * (oa[i].co + ob[i].co)
                mid.y = seam_y
                oa[i].co = mid
                ob[i].co = mid
            bmesh.ops.remove_doubles(bm, verts=list(set(oa[:n] + ob[:n])), dist=0.002)
            method = f"merge_n={n}"
            # Fill any remaining boundary holes near seam with grid/edgenet fill
            bm.edges.ensure_lookup_table()
            boundary2 = [e for e in bm.edges if e.is_boundary and abs(0.5*(e.verts[0].co.y+e.verts[1].co.y)-seam_y)<tol]
            if boundary2:
                try:
                    bmesh.ops.holes_fill(bm, edges=boundary2, sides=0)
                    method += "+holes_fill"
                except Exception as e:
                    log(f"[weld] holes_fill failed: {e}")
                    # try edgenet_fill
                    try:
                        bmesh.ops.edgenet_fill(bm, edges=boundary2)
                        method += "+edgenet_fill"
                    except Exception as e2:
                        log(f"[weld] edgenet_fill failed: {e2}")
    elif len(loops) == 1:
        method = "single_loop_remove_doubles"
        bmesh.ops.remove_doubles(bm, verts=list(loops[0][0]), dist=0.005)
    else:
        # fallback: remove doubles globally near seam
        near_v = [v for v in bm.verts if abs(v.co.y - seam_y) < tol]
        bmesh.ops.remove_doubles(bm, verts=near_v, dist=0.01)
        method = f"fallback_doubles n={len(near_v)}"

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()
    for p in fuse.data.polygons:
        p.use_smooth = True
    log(f"[weld] method={method}")
    return method


def process_straddle_mesh(obj, y_hi, y_lo):
    """For meshes spanning the cut: delete slab, translate aft verts."""
    bake_world(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if y_lo < f.calc_center_median().y < y_hi]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    mid = [v for v in bm.verts if y_lo < v.co.y < y_hi]
    if mid:
        bmesh.ops.delete(bm, geom=mid, context="VERTS")
    for v in bm.verts:
        if v.co.y <= y_lo + 1e-6:
            v.co.y += CUT
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    log(f"[straddle] {obj.name} slab cleared + aft +=CUT")


def translate_object_y(obj, dy):
    bake_world(obj)
    for v in obj.data.vertices:
        v.co.y += dy
    obj.data.update()


def classify_and_move(y_hi, y_lo):
    """Move whole objects that are entirely aft of cut; straddle edit; skip NO_MOVE."""
    moved = []
    straddled = []
    skipped = []
    for obj in list(bpy.data.objects):
        if obj.type != "MESH":
            continue
        if obj.name in NO_MOVE:
            skipped.append(obj.name)
            continue
        if obj.name == "Fuselage":
            continue  # handled separately
        bb = world_bbox(obj)
        # entirely forward of cut (nose side): leave
        if bb["ymin"] >= y_hi - 1e-4:
            skipped.append(obj.name + ":fwd")
            continue
        # entirely aft of cut_front before edit — after fuse cut, objects with ymax <= y_lo
        if bb["ymax"] <= y_lo + 1e-4:
            translate_object_y(obj, CUT)
            moved.append(obj.name)
            continue
        # straddles slab
        if bb["ymin"] < y_hi and bb["ymax"] > y_lo:
            process_straddle_mesh(obj, y_hi, y_lo)
            straddled.append(obj.name)
            continue
        # entirely between? shouldn't remain
        if y_lo < bb["ymin"] and bb["ymax"] < y_hi:
            # object fully in deleted slab — delete object
            log(f"[delete-in-slab] {obj.name}")
            me = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)
            continue
        # default: if center aft, move
        cy = 0.5 * (bb["ymin"] + bb["ymax"])
        if cy <= y_lo:
            translate_object_y(obj, CUT)
            moved.append(obj.name)
        else:
            skipped.append(obj.name + ":other")
    return moved, straddled, skipped


def measure_table(tip):
    def dist(feature_y):
        if feature_y is None:
            return None
        return tip - feature_y

    doors = bpy.data.objects.get("Doors")
    door_spans = []
    if doors:
        bm = bmesh.new()
        bm.from_mesh(doors.data)
        remaining = set(bm.verts)
        mw = doors.matrix_world
        while remaining:
            seed = remaining.pop()
            stack = [seed]
            isl = {seed}
            while stack:
                v = stack.pop()
                for e in v.link_edges:
                    o = e.other_vert(v)
                    if o in remaining:
                        remaining.remove(o)
                        isl.add(o)
                        stack.append(o)
            ys = sorted((mw @ v.co).y for v in isl)
            if len(isl) > 50:
                door_spans.append((min(ys), max(ys), 0.5 * (min(ys) + max(ys))))
        bm.free()
        door_spans.sort(key=lambda t: -t[2])

    # Nose door
    nose = bpy.data.objects.get("Nose")
    nose_door = None
    if nose:
        nv = mesh_world_verts(nose)
        side = [v for v in nv if abs(v.x) > 1.55 and 10.0 < v.y < tip and -0.3 < v.z < 1.9]
        if len(side) > 40:
            ys = [v.y for v in side]
            # cluster high-Y door on nose — use verts near typical door height
            nose_door = (min(ys), max(ys))

    wing_le = wing_root_le_y()
    wing = bpy.data.objects.get("Wing_R") or bpy.data.objects.get("Wing_L")
    wing_te = None
    if wing:
        wv = mesh_world_verts(wing)
        root = [v for v in wv if abs(v.x) < 2.8]
        wing_te = min(v.y for v in root) if root else None

    eng = bpy.data.objects.get("Engine_R") or bpy.data.objects.get("Engine_L")
    nac_le = max(v.y for v in mesh_world_verts(eng)) if eng else None

    gear_n = bpy.data.objects.get("Gear_Nose")
    gear_n_y = None
    if gear_n:
        gv = mesh_world_verts(gear_n)
        # wheel center approx bbox center Y
        gear_n_y = 0.5 * (min(v.y for v in gv) + max(v.y for v in gv))

    gear_r = bpy.data.objects.get("Gear_R")
    gear_l = bpy.data.objects.get("Gear_L")
    gear_m_y = None
    gear_track = None
    if gear_r and gear_l:
        gr = mesh_world_verts(gear_r)
        gl = mesh_world_verts(gear_l)
        gear_m_y = 0.5 * (
            0.5 * (min(v.y for v in gr) + max(v.y for v in gr))
            + 0.5 * (min(v.y for v in gl) + max(v.y for v in gl))
        )
        # track width: |mean x|
        xr = sum(v.x for v in gr) / len(gr)
        xl = sum(v.x for v in gl) / len(gl)
        gear_track = abs(xr - xl)

    vt = bpy.data.objects.get("VerticalTail")
    vt_le = max(v.y for v in mesh_world_verts(vt)) if vt else None
    stab = bpy.data.objects.get("Stab_R") or bpy.data.objects.get("Stab_L")
    ht_le = None
    if stab:
        sv = mesh_world_verts(stab)
        root = [v for v in sv if abs(v.x) < 1.5]
        ht_le = max(v.y for v in (root or sv))

    tail = bpy.data.objects.get("TailCone")
    tail_y = min(v.y for v in mesh_world_verts(tail)) if tail else None

    # door distances from tip
    fwd_door = door_spans[0] if door_spans else None
    aft_door = door_spans[-1] if len(door_spans) > 1 else None
    # if nose door exists and is forward-most
    entries = []
    if nose_door:
        entries.append({
            "name": "前登机门(Nose蒙皮)",
            "ours_from_tip": [dist(nose_door[1]), dist(nose_door[0])],  # fwd edge, aft edge as tip-y
            "span_y": nose_door,
            "ref": [4.48, 5.38],
        })
    if fwd_door:
        entries.append({
            "name": "登机门(Doors最高岛)",
            "ours_from_tip": [dist(fwd_door[1]), dist(fwd_door[0])],
            "span_y": [fwd_door[0], fwd_door[1]],
            "ref": [4.48, 5.38],
        })
    if aft_door and aft_door != fwd_door:
        entries.append({
            "name": "后登机门(Doors最低岛)",
            "ours_from_tip": [dist(aft_door[1]), dist(aft_door[0])],
            "span_y": [aft_door[0], aft_door[1]],
            "ref": [30.19, 31.09],
        })

    table = {
        "tip_y": tip,
        "items": [
            {"name": "前起落架轮中心", "ours_m": dist(gear_n_y), "ref_m": 5.18, "y": gear_n_y},
            {"name": "翼根前缘", "ours_m": dist(wing_le), "ref_m": 13.18, "y": wing_le},
            {"name": "翼根后缘", "ours_m": dist(wing_te), "ref_m": 19.98, "y": wing_te},
            {"name": "短舱前缘", "ours_m": dist(nac_le), "ref_m": 12.27, "y": nac_le, "note": "Step2未做，预期约15.88"},
            {"name": "主起落架轮中心", "ours_m": dist(gear_m_y), "ref_m": 17.58, "y": gear_m_y},
            {"name": "左右主轮距", "ours_m": gear_track, "ref_m": 6.83},
            {"name": "垂尾根部前缘", "ours_m": dist(vt_le), "ref_m": 31.46, "y": vt_le},
            {"name": "水平尾翼根部前缘", "ours_m": dist(ht_le), "ref_m": 32.86, "y": ht_le},
            {"name": "尾锥末端", "ours_m": dist(tail_y), "ref_m": 38.84, "y": tail_y},
            {"name": "全长 tip→尾锥", "ours_m": dist(tail_y), "ref_m": 38.84},
        ],
        "doors": entries,
        "tip_to_wing_le": dist(wing_le),
        "target_tip_to_wing_le": TARGET_TIP_WING,
    }
    return table


def inventory_empennage():
    names = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n = o.name.lower()
        if "vertical" in n or "rudder" in n or "stab" in n or "尾" in o.name or o.name in (
            "VerticalTail", "Rudder", "Stab_L", "Stab_R", "TailCone",
        ):
            names.append({"name": o.name, "verts": len(o.data.vertices), "faces": len(o.data.polygons), "bbox": world_bbox(o)})
    # check if fuselage has high-Z aft faces that might include fin (unlikely)
    return names


def render_ortho_side(path, objs_filter=None, y_center=None, extent=45.0):
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except Exception:
        pass
    try:
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
    except Exception:
        pass
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 600
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    # hide non-filtered
    hidden = []
    if objs_filter is not None:
        allow = set(objs_filter)
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            if o.name not in allow and not o.hide_render:
                hidden.append(o)
                o.hide_render = True

    # camera ortho from +X
    for o in list(bpy.data.objects):
        if o.name.startswith("S1Cam"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("S1Cam")
    cam = bpy.data.objects.new("S1Cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cd.type = "ORTHO"
    cd.ortho_scale = extent
    if y_center is None:
        y_center = 0.0
    cam.location = (80.0, y_center, 2.0)
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(90))  # look -X? 
    # Better: track to origin
    cam.location = (60.0, y_center, 1.5)
    direction = Vector((0, y_center, 1.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log(f"[render] {path}")
    bpy.data.objects.remove(cam, do_unlink=True)
    for o in hidden:
        o.hide_render = False


def render_ref_side(path, extent=45.0):
    """Import REF meters FBX into temp empty scene, render ortho side, restore? 

    We run this AFTER saving working blend — open factory, import REF, render, don't save over work.
    Actually we're in working file. Better: save work, factory, import REF, render, reopen work.
    """
    work_blend = BLEND
    bpy.ops.wm.save_as_mainfile(filepath=work_blend)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    if not os.path.isfile(fbx):
        fbx = os.path.join(REFS, "REF_C919.fbx")
    log(f"[ref] import {fbx}")
    if fbx.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=fbx)
    # compute bbox
    ys = []
    zs = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        b = world_bbox(o)
        ys += [b["ymin"], b["ymax"]]
        zs += [b["zmin"], b["zmax"]]
    y_center = 0.5 * (min(ys) + max(ys)) if ys else 0.0
    length = (max(ys) - min(ys)) if ys else 40.0
    extent = max(extent, length * 1.15)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 600
    scene.render.image_settings.file_format = "PNG"
    cd = bpy.data.cameras.new("RefCam")
    cam = bpy.data.objects.new("RefCam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cd.type = "ORTHO"
    cd.ortho_scale = extent
    cam.location = (60.0, y_center, 1.5)
    direction = Vector((0, y_center, 1.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        ld = bpy.data.lights.new("L", "SUN")
        lo = bpy.data.objects.new("L", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(45), 0, math.radians(30))
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log(f"[render-ref] {path} extent={extent:.1f} len={length:.2f}")
    # restore working
    bpy.ops.wm.open_mainfile(filepath=work_blend)


def stack_images(top_path, bot_path, out_path):
    try:
        from PIL import Image
    except ImportError:
        # fallback: use blender or skip
        log("[compare] PIL missing — try copy top only")
        shutil.copy2(top_path, out_path)
        return
    a = Image.open(top_path).convert("RGB")
    b = Image.open(bot_path).convert("RGB")
    w = max(a.width, b.width)
    # scale to same width
    def fit(im):
        if im.width == w:
            return im
        h = int(im.height * w / im.width)
        return im.resize((w, h), Image.Resampling.LANCZOS)
    a, b = fit(a), fit(b)
    out = Image.new("RGB", (w, a.height + b.height), (20, 20, 20))
    out.paste(a, (0, 0))
    out.paste(b, (0, a.height))
    out.save(out_path)
    log(f"[compare] {out_path}")


def main():
    open(os.path.join(LOG, "length_s1_console.txt"), "w").close()
    log("=== LENGTH STEP 1 ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # BACKUP first
    bak = os.path.join(OUT, "c919.bak-length-s1.blend")
    shutil.copy2(BLEND, bak)
    # also glb bak
    if os.path.isfile(GLB):
        shutil.copy2(GLB, GLB + ".bak-length-s1")
    log(f"[backup] {bak}")

    tip0 = tip_y()
    wing0 = wing_root_le_y()
    door_aft, door_fwd = forward_door_aft_y()
    log(f"[measure0] tip={tip0:.4f} wing_le={wing0:.4f} tip→wing={tip0-wing0:.4f}")
    log(f"[measure0] forward_door aft={door_aft:.4f} fwd={door_fwd:.4f}")

    # Constant section between door_aft and wing_le (door_aft > wing_le in +Y forward)
    # Available: y in (wing_le + margin, door_aft - margin)
    margin = 0.35
    avail_hi = door_aft - margin
    avail_lo = wing0 + margin
    span = avail_hi - avail_lo
    log(f"[cut-zone] available y=({avail_lo:.3f},{avail_hi:.3f}) span={span:.3f}")
    if span < CUT + 0.2:
        # expand into window belt: allow closer to door/wing
        avail_hi = door_aft - 0.1
        avail_lo = wing0 + 0.15
        span = avail_hi - avail_lo
        log(f"[cut-zone] relaxed y=({avail_lo:.3f},{avail_hi:.3f}) span={span:.3f}")
    if span < CUT:
        raise RuntimeError(f"Not enough constant-section length ({span:.3f}) for CUT={CUT}")

    # Place slab just forward of wing (aft side of available band)
    y_lo = avail_lo
    y_hi = y_lo + CUT
    if y_hi > avail_hi:
        y_hi = avail_hi
        y_lo = y_hi - CUT
    log(f"[cut] y_lo={y_lo:.4f} y_hi={y_hi:.4f} (remove open interval)")

    fuse = bpy.data.objects.get("Fuselage")
    if not fuse:
        raise RuntimeError("Fuselage missing")

    cut_fuselage_slab(fuse, y_hi, y_lo)
    seam_y = y_hi  # after translate, aft face meets here
    # Actually aft verts at y_lo move to y_lo+CUT = y_hi, so seam at y_hi
    method = weld_fuselage_seam(fuse, seam_y)

    moved, straddled, skipped = classify_and_move(y_hi, y_lo)
    log(f"[move] whole={moved}")
    log(f"[move] straddle={straddled}")

    tip1 = tip_y()
    wing1 = wing_root_le_y()
    tip_wing = tip1 - wing1
    log(f"[verify] tip={tip1:.4f} wing_le={wing1:.4f} tip→wing={tip_wing:.4f} target={TARGET_TIP_WING}")

    table = measure_table(tip1)
    emp = inventory_empennage()

    # Export working glb
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"GLB {os.path.getsize(GLB)}")

    # Side render ours — extent from tip to tail
    tail = bpy.data.objects.get("TailCone")
    tail_y = min(v.y for v in mesh_world_verts(tail)) if tail else -20
    y_center = 0.5 * (tip1 + tail_y)
    extent = (tip1 - tail_y) * 1.12
    ours_path = os.path.join(PREV, "side_ours.png")
    render_ortho_side(ours_path, y_center=y_center, extent=extent)

    # REF side (reopens work after)
    ref_path = os.path.join(PREV, "side_ref.png")
    render_ref_side(ref_path, extent=extent)

    compare_path = os.path.join(PREV, "side_compare.png")
    stack_images(ours_path, ref_path, compare_path)

    result = {
        "backup_blend": bak,
        "backup_glb": GLB + ".bak-length-s1",
        "cut": {"y_lo": y_lo, "y_hi": y_hi, "length": CUT},
        "door_aft_y": door_aft,
        "door_fwd_y": door_fwd,
        "wing_le_before": wing0,
        "wing_le_after": wing1,
        "tip": tip1,
        "tip_to_wing_le": tip_wing,
        "target": TARGET_TIP_WING,
        "seam_method": method,
        "seam_y": seam_y,
        "moved_objects": moved,
        "straddled_objects": straddled,
        "measurements": table,
        "empennage_inventory": emp,
        "previews": {"ours": ours_path, "ref": ref_path, "compare": compare_path},
        "ref_source_note": "Used REF_C919_meters.fbx (C919_REF_整机.obj not found on disk)",
        "glb_bytes": os.path.getsize(GLB),
    }
    with open(os.path.join(LOG, "length_s1.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "LENGTH_S1_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 全长 Step 1（前段缩短 3.60 m）\n\n")
        f.write(f"- 备份：`{bak}`\n")
        f.write(f"- 切除：y ∈ ({y_lo:.3f}, {y_hi:.3f}) 共 {CUT} m\n")
        f.write(f"- 焊接：{method} @ y≈{seam_y:.3f}\n")
        f.write(f"- tip→翼根前缘：{tip_wing:.4f} m（目标 13.18）\n")
        f.write(f"- 预览：`public/models/length-s1/side_compare.png`\n")
        f.write(f"- REF 对比源：REF_C919_meters.fbx（未找到整机.obj）\n\n")
        f.write("## 测量表\n\n")
        for it in table["items"]:
            f.write(f"- {it['name']}: ours={it.get('ours_m')} ref={it.get('ref_m')}\n")
        f.write("\n## 垂尾/平尾物体\n\n")
        for e in emp:
            f.write(f"- `{e['name']}` faces={e['faces']}\n")
    log(f"notes -> {notes}")
    log("=== STEP1 DONE ===")


if __name__ == "__main__":
    main()

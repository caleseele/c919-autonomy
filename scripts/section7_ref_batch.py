# -*- coding: utf-8 -*-
"""§7: batch replace mid-fuselage / wings / engines / gear with REF; reimport cabin.

  blender -b --factory-startup -P scripts/section7_ref_batch.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector, kdtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
REFS = os.path.join(ROOT, "refs")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section7")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK_SRC = os.path.join(OUT, "c919.bak-section6b.blend")
BAK_BEFORE = os.path.join(OUT, "c919.bak-before-s7.blend")

# Exact T_REF from aft_ref_tail.json / parent brief
SX = 1.0475227637527205
SY = 1.0
SZ = 1.0104343689231436
DX = 0.0
DY = 15.463823181152343
DZ = -4.239782612001511
TARGET_CUT_Y = -5.427176818847657
OVERLAP_M = 0.015
REF_CUT_Y_IMPORTED = 20.891
OBJ_FRONT_CUT_Y = 0.5  # nose/mid join in OBJ space

# Keep (aliases included)
KEEP_NAMES = {
    "REF_机头蒙皮", "Nose",
    "CockpitGlass_REF",
    "REF_风挡窗框", "REF_WindshieldFrame",
    "REF_雨刮器", "REF_Wipers",
    "REF_探头天线", "REF_ProbesAntennas",
    "REF_驾驶舱内饰", "REF_CockpitInterior",
    "RadomePanelLines",
    "REF_尾段蒙皮_含垂尾",
    "REF_水平尾翼_含升降舵",
    "REF_方向舵等",
    "REF_APU排气口",
    "REF_尾段天线",
}

# Explicit delete patterns / names (GearBayDoors decided later)
DELETE_EXACT = {
    "Fuselage", "Fuselage_ORIG", "Fuselage.001", "Fuselage_COPY",
    "Wing_L", "Wing_R", "Winglet_L", "Winglet_R",
    "WingLE_L", "WingLE_R", "WingFairing_L", "WingFairing_R",
    "WingBodyFairing_L", "WingBodyFairing_R",
    "Pylon_L", "Pylon_R",
    "Engine_L", "Engine_R", "EngineLip_L", "EngineLip_R",
    "Fan_L", "Fan_R",
    "Gear_L", "Gear_R", "Gear_Nose",
    "REF_舷窗玻璃", "REF_舱门缝线",
    # leftovers that sit on old fuselage / will float
    "Stripe_L", "Stripe_R", "Flag_L", "Flag_R",
    "PanelLines", "AntennasAPU",
}

IMPORT_FILES = [
    ("C919_REF_中机身.obj", ["REF_中机身蒙皮"]),
    ("C919_REF_机翼吊挂.obj", ["REF_机翼_左", "REF_机翼_右", "REF_吊挂_左", "REF_吊挂_右"]),
    ("C919_REF_发动机.obj", ["REF_发动机_左", "REF_发动机_右"]),
    ("C919_REF_起落架.obj", ["REF_前起落架", "REF_主起落架"]),
    ("C919_REF_舱门舷窗.obj", ["REF_舷窗玻璃", "REF_舱门缝线"]),
]

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section7_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs


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


def aabb_overlap(a, b):
    return not (
        a["xmax"] < b["xmin"] or b["xmax"] < a["xmin"]
        or a["ymax"] < b["ymin"] or b["ymax"] < a["ymin"]
        or a["zmax"] < b["zmin"] or b["zmax"] < a["zmin"]
    )


def apply_mw(ob):
    me = ob.data
    me.transform(ob.matrix_world)
    me.update()
    ob.matrix_world = Matrix.Identity(4)


def delete_object(name: str) -> bool:
    ob = bpy.data.objects.get(name)
    if not ob:
        return False
    me = ob.data if ob.type == "MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)
    return True


def t_ref_matrix():
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((SX, SY, SZ, 1.0))
    T = Matrix.Translation(Vector((DX, DY, DZ)))
    return T @ S @ R


def apply_t_ref(ob):
    apply_mw(ob)
    me = ob.data
    me.transform(t_ref_matrix())
    me.update()
    ob.matrix_world = Matrix.Identity(4)


def find_ref(fn_substr: str) -> str:
    """Find OBJ under refs by Chinese filename substring or exact."""
    exact = os.path.join(REFS, fn_substr)
    if os.path.isfile(exact):
        return exact
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and all(ch in fn for ch in fn_substr.replace("C919_REF_", "").replace(".obj", "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff"):
            # fallback: match key chinese parts
            pass
    # keyed lookup
    keys = {
        "中机身": ["中机身"],
        "机翼吊挂": ["机翼"],
        "发动机": ["发动机"],
        "起落架": ["起落架"],
        "舱门舷窗": ["舱门", "舷窗"],
    }
    for label, parts in keys.items():
        if label in fn_substr:
            for fn in os.listdir(REFS):
                if fn.endswith(".obj") and all(p in fn for p in parts):
                    return os.path.join(REFS, fn)
    raise FileNotFoundError(fn_substr)


def tip_y():
    for n in ("REF_机头蒙皮", "Nose"):
        ob = bpy.data.objects.get(n)
        if ob and ob.type == "MESH":
            return max(v.y for v in mwv(ob))
    # fallback any Fuselage_REF
    ob = bpy.data.objects.get("Fuselage_REF")
    if ob:
        return max(v.y for v in mwv(ob))
    raise RuntimeError("no nose tip")


def cut_world_y(obj_y: float) -> float:
    """World Y of an OBJ-space (0, obj_y, 0) after T_REF = T@S@R."""
    p = t_ref_matrix() @ Vector((0.0, obj_y, 0.0))
    return p.y


def band_verts(ob, y_world: float, tol: float = 0.05):
    return [v for v in mwv(ob) if abs(v.y - y_world) <= tol]


def max_cut_deviation(ob_a, ob_b, y_world: float, tol: float = 0.08):
    """Max nearest-neighbor distance between cut-ring verts (Hausdorff-ish)."""
    a = band_verts(ob_a, y_world, tol)
    b = band_verts(ob_b, y_world, tol)
    if len(a) < 4 or len(b) < 4:
        # widen
        a = band_verts(ob_a, y_world, tol * 2)
        b = band_verts(ob_b, y_world, tol * 2)
    if len(a) < 3 or len(b) < 3:
        return {
            "max_mm": None, "n_a": len(a), "n_b": len(b),
            "y_world": y_world, "error": "insufficient_band_verts",
        }
    # KDTree on b
    kd = kdtree.KDTree(len(b))
    for i, p in enumerate(b):
        kd.insert(p, i)
    kd.balance()
    d_ab = []
    for p in a:
        co, _i, dist = kd.find(p)
        d_ab.append(dist)
    kd2 = kdtree.KDTree(len(a))
    for i, p in enumerate(a):
        kd2.insert(p, i)
    kd2.balance()
    d_ba = []
    for p in b:
        co, _i, dist = kd2.find(p)
        d_ba.append(dist)
    mx = max(max(d_ab), max(d_ba))
    return {
        "max_m": mx,
        "max_mm": mx * 1000.0,
        "n_a": len(a),
        "n_b": len(b),
        "y_world": y_world,
        "mean_ab_mm": (sum(d_ab) / len(d_ab)) * 1000.0,
        "mean_ba_mm": (sum(d_ba) / len(d_ba)) * 1000.0,
    }


def ensure_mat(name, color, metallic, roughness, transmission=None, alpha=None, blend=None):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if transmission is not None:
            for key in ("Transmission Weight", "Transmission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = transmission
                    break
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "IOR" in bsdf.inputs and transmission:
            bsdf.inputs["IOR"].default_value = 1.5
    if blend == "BLEND":
        m.blend_method = "BLEND"
        if hasattr(m, "shadow_method"):
            m.shadow_method = "HASHED"
    return m


def find_white_mat():
    for n in ("Nose", "REF_机头蒙皮", "REF_尾段蒙皮_含垂尾", "Fuselage"):
        ob = bpy.data.objects.get(n)
        if ob and ob.type == "MESH" and ob.data.materials:
            return ob.data.materials[0]
    return ensure_mat("FuselageWhite_S7", (0.85, 0.85, 0.87), 0.0, 0.35)


def assign_slot(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def weld_fuselage(nose, mid, aft, front_y, aft_y):
    """Join three skins → Fuselage_REF; merge only cut-ring verts @ 1 mm."""
    # ensure objects selected for join
    bpy.ops.object.select_all(action="DESELECT")
    for ob in (nose, mid, aft):
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = nose
    bpy.ops.object.join()
    fus = bpy.context.view_layer.objects.active
    fus.name = "Fuselage_REF"
    if fus.data:
        fus.data.name = "Fuselage_REF"
    apply_mw(fus)

    bm = bmesh.new()
    bm.from_mesh(fus.data)
    bm.verts.ensure_lookup_table()
    # mark cut-ring verts near the two planes
    ring = []
    for v in bm.verts:
        if abs(v.co.y - front_y) < 0.06 or abs(v.co.y - aft_y) < 0.06:
            ring.append(v)
    # merge by distance only among ring (bmesh.ops.remove_doubles on subset)
    if ring:
        bmesh.ops.remove_doubles(bm, verts=ring, dist=0.001)
    bm.to_mesh(fus.data)
    fus.data.update()
    bm.free()

    # shade smooth + auto smooth 30°
    for p in fus.data.polygons:
        p.use_smooth = True
    if hasattr(fus.data, "use_auto_smooth"):
        fus.data.use_auto_smooth = True
        fus.data.auto_smooth_angle = math.radians(30.0)
    else:
        # Blender 4.1+: Auto Smooth modifier
        mod = fus.modifiers.get("AutoSmooth") or fus.modifiers.new("AutoSmooth", "NODES")
        # fallback: set sharp angle via attribute
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
        # Try Smooth by Angle modifier (Blender 4+)
        if "Smooth by Angle" not in [m.name for m in fus.modifiers]:
            try:
                m = fus.modifiers.new("Smooth by Angle", "NODES")
            except Exception:
                pass
        # Explicitly set custom normals angle if available
        if hasattr(fus.data, "auto_smooth_angle"):
            fus.data.auto_smooth_angle = math.radians(30.0)

    # Blender 5: use shade_auto_smooth operator if present
    bpy.ops.object.select_all(action="DESELECT")
    fus.select_set(True)
    bpy.context.view_layer.objects.active = fus
    if hasattr(bpy.ops.object, "shade_auto_smooth"):
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(30.0))
        except Exception as e:
            log(f"[weld] shade_auto_smooth failed: {e}")
            bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_smooth()

    return fus


def gear_bay_decision(fuse):
    gbd = bpy.data.objects.get("GearBayDoors")
    if not gbd:
        return {"name": "GearBayDoors", "action": "absent", "reason": "not in scene"}
    ga = aabb(gbd)
    gear_names = ["REF_前起落架", "REF_主起落架"]
    overlapped = []
    for n in gear_names:
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        if aabb_overlap(ga, aabb(ob)):
            overlapped.append(n)
    # sit on Fuselage_REF? sample centers of islands / verts and check distance to surface
    imw = fuse.matrix_world.inverted()
    mw = fuse.matrix_world
    dists = []
    vs = mwv(gbd)
    step = max(1, len(vs) // 40)
    for v in vs[::step]:
        ok, loc, norm, _ = fuse.closest_point_on_mesh(imw @ v)
        if ok:
            dists.append((v - (mw @ loc)).length)
    mean_d = sum(dists) / len(dists) if dists else 999.0
    max_d = max(dists) if dists else 999.0
    on_surface = mean_d < 0.05 and max_d < 0.12
    if overlapped or not on_surface:
        delete_object("GearBayDoors")
        return {
            "name": "GearBayDoors",
            "action": "deleted",
            "reason": (
                f"overlap={overlapped}; mean_d={mean_d:.4f} max_d={max_d:.4f} "
                f"on_surface={on_surface}"
            ),
            "overlap": overlapped,
            "mean_d": mean_d,
            "max_d": max_d,
        }
    return {
        "name": "GearBayDoors",
        "action": "kept",
        "reason": f"no gear overlap; mean_d={mean_d:.4f} max_d={max_d:.4f}",
        "mean_d": mean_d,
        "max_d": max_d,
    }


def measure_stations(tip):
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
        return ours

    # length: tip → aftmost mesh
    aft = min(aabb(o)["ymin"] for o in bpy.data.objects if o.type == "MESH" and not o.hide_get())
    add("全长", tip - aft, 38.84, 0.10)

    # wing root LE: REF_机翼 — root = small |x|, max Y
    wing_le = None
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        vs = mwv(ob)
        root = [v for v in vs if abs(v.x) < 2.5]
        if not root:
            root = vs
        le = tip - max(v.y for v in root)
        wing_le = le if wing_le is None else min(wing_le, le)
    add("翼根前缘", wing_le, 13.18, 0.25)

    # nacelle LE: REF_发动机 — max Y (forward-most)
    nac_le = None
    for n in ("REF_发动机_左", "REF_发动机_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        a = aabb(ob)
        le = tip - a["ymax"]
        nac_le = le if nac_le is None else min(nac_le, le)
    add("短舱前缘", nac_le, 12.27, 0.25)

    # main gear center + track
    main = bpy.data.objects.get("REF_主起落架")
    main_st = None
    track = None
    if main:
        vs = mwv(main)
        # wheels = lowest Z cluster
        zmin = min(v.z for v in vs)
        wheels = [v for v in vs if v.z < zmin + 0.35]
        if len(wheels) < 4:
            wheels = [v for v in vs if v.z < zmin + 0.8]
        if wheels:
            cy = sum(v.y for v in wheels) / len(wheels)
            main_st = tip - cy
            xs = [v.x for v in wheels]
            # left/right groups
            left = [v for v in wheels if v.x < -0.5]
            right = [v for v in wheels if v.x > 0.5]
            if left and right:
                track = abs(sum(v.x for v in right) / len(right) - sum(v.x for v in left) / len(left))
            else:
                track = max(xs) - min(xs)
    add("主轮中心", main_st, 17.58, 0.30)
    add("主轮轮距", track, 6.83, 0.30)

    nose_g = bpy.data.objects.get("REF_前起落架")
    nose_st = None
    if nose_g:
        vs = mwv(nose_g)
        zmin = min(v.z for v in vs)
        wheels = [v for v in vs if v.z < zmin + 0.35] or vs
        cy = sum(v.y for v in wheels) / len(wheels)
        nose_st = tip - cy
    add("前轮中心", nose_st, 5.18, 0.30)

    # VT root LE
    skin = bpy.data.objects.get("Fuselage_REF") or bpy.data.objects.get("REF_尾段蒙皮_含垂尾")
    vt_le = None
    if skin:
        vs = mwv(skin)
        fin = [v for v in vs if v.z > 1.5 and abs(v.x) < 0.8]
        if fin:
            zmin_f = min(v.z for v in fin)
            root = [v for v in fin if v.z < zmin_f + 1.2]
            if root:
                vt_le = tip - max(v.y for v in root)
    add("垂尾根部前缘", vt_le, 31.46, 0.20)

    return items, {
        "aft_y": aft,
        "wing_le": wing_le,
        "nac_le": nac_le,
        "main_st": main_st,
        "track": track,
        "nose_st": nose_st,
        "vt_le": vt_le,
    }


def render_collage(tip):
    """Top: side ortho; bottom: 45° front-side; nose left via tip_sx < tail_sx."""
    ys = []
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_get() and not o.hide_render:
            a = aabb(o)
            ys += [a["ymin"], a["ymax"]]
    tail = min(ys)
    ymid = 0.5 * (tip + tail)
    zmid = 0.0
    for o in bpy.data.objects:
        if o.type == "MESH" and ("Fuselage" in o.name or "机头" in o.name or o.name == "Nose"):
            a = aabb(o)
            zmid = 0.5 * (a["zmin"] + a["zmax"])
            break

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    scene.render.film_transparent = False

    cam = bpy.data.objects.get("S7Cam")
    if cam is None:
        data = bpy.data.cameras.new("S7Cam")
        cam = bpy.data.objects.new("S7Cam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.15
    scene.camera = cam

    tip_pt = Vector((0.0, tip, zmid))
    tail_pt = Vector((0.0, tail, zmid))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def pick_side():
        configs = [
            {"loc": Vector((-80.0, ymid, zmid)), "rot": (math.pi / 2, 0.0, -math.pi / 2)},
            {"loc": Vector((80.0, ymid, zmid)), "rot": (math.pi / 2, 0.0, math.pi / 2)},
        ]
        for cfg in configs:
            cam.location = cfg["loc"]
            cam.rotation_euler = cfg["rot"]
            bpy.context.view_layer.update()
            ts = world_to_camera_view(scene, cam, tip_pt).x
            ls = world_to_camera_view(scene, cam, tail_pt).x
            log(f"[cam-side] tip_sx={ts:.4f} tail_sx={ls:.4f}")
            if ts < ls:
                return ts, ls, True
        return ts, ls, False

    def pick_45():
        # 45° front-side: camera in forward-lateral quadrant, looking at mid
        dist = 70.0
        candidates = []
        for sign in (-1.0, 1.0):
            # from nose-front side: toward +Y (nose) and ±X
            loc = Vector((sign * dist * math.sin(math.radians(45)),
                          ymid + dist * math.cos(math.radians(45)) * 0.35,
                          zmid + 8.0))
            # aim at center
            direction = Vector((0.0, ymid, zmid)) - loc
            # build rotation: track to target
            cam.location = loc
            # use track quaternion
            quat = direction.to_track_quat("-Z", "Y")
            cam.rotation_euler = quat.to_euler()
            bpy.context.view_layer.update()
            ts = world_to_camera_view(scene, cam, tip_pt).x
            ls = world_to_camera_view(scene, cam, tail_pt).x
            log(f"[cam-45] sign={sign} tip_sx={ts:.4f} tail_sx={ls:.4f}")
            candidates.append((ts, ls, loc.copy(), cam.rotation_euler.copy(), ts < ls))
        for c in candidates:
            if c[4]:
                cam.location = c[2]
                cam.rotation_euler = c[3]
                bpy.context.view_layer.update()
                return c[0], c[1], True
        # force first with tip left by flipping
        c = candidates[0]
        cam.location = c[2]
        cam.rotation_euler = c[3]
        bpy.context.view_layer.update()
        return c[0], c[1], c[4]

    # Side
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.15
    ts1, ls1, ok1 = pick_side()
    side_path = os.path.join(PREV, f"side_{stamp}.png")
    scene.render.filepath = side_path
    bpy.ops.render.render(write_still=True)

    # 45°
    cam.data.type = "PERSP"
    cam.data.lens = 50
    ts2, ls2, ok2 = pick_45()
    # ensure framing
    ang_path = os.path.join(PREV, f"ang45_{stamp}.png")
    scene.render.filepath = ang_path
    bpy.ops.render.render(write_still=True)

    # stack with bpy images
    coll_name = f"collage_{stamp}.png"
    coll_path = os.path.join(PREV, coll_name)
    stack_images(side_path, ang_path, coll_path)

    return {
        "stamp": stamp,
        "side": side_path,
        "ang45": ang_path,
        "collage": coll_path,
        "collage_name": coll_name,
        "side_tip_sx": ts1,
        "side_tail_sx": ls1,
        "side_ok": ok1,
        "ang_tip_sx": ts2,
        "ang_tail_sx": ls2,
        "ang_ok": ok2,
    }


def stack_images(top_path, bot_path, out_path):
    """Stack two PNGs vertically, width ≤1280."""
    try:
        from PIL import Image
        t = Image.open(top_path).convert("RGB")
        b = Image.open(bot_path).convert("RGB")
        w = min(1280, max(t.width, b.width))
        def resize(im):
            if im.width == w:
                return im
            h = int(im.height * (w / im.width))
            return im.resize((w, h), Image.Resampling.LANCZOS)
        t, b = resize(t), resize(b)
        out = Image.new("RGB", (w, t.height + b.height), (30, 30, 30))
        out.paste(t, (0, 0))
        out.paste(b, (0, t.height))
        out.save(out_path)
        log(f"[collage] PIL {out_path} {out.size}")
        return
    except Exception as e:
        log(f"[collage] PIL failed: {e}; trying bpy")
    # bpy fallback
    img_t = bpy.data.images.load(top_path)
    img_b = bpy.data.images.load(bot_path)
    w = min(1280, max(img_t.size[0], img_b.size[0]))
    # simple: just copy side as collage if can't stack
    shutil.copy2(top_path, out_path)
    log(f"[collage] fallback copy side → {out_path}")


def export_glb():
    bpy.ops.object.select_all(action="DESELECT")
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.hide_get() or o.hide_render:
            o.select_set(False)
            continue
        o.select_set(True)
        n += 1
    bpy.ops.export_scene.gltf(
        filepath=GLB,
        use_selection=True,
        export_apply=True,
        export_extras=False,
    )
    log(f"[glb] exported {n} meshes → {GLB}")
    return n


def verify_keeper_t_ref(tip):
    """Sanity: existing REF_尾段 cut near TARGET_CUT_Y; nose tip plausible."""
    info = {}
    aft = bpy.data.objects.get("REF_尾段蒙皮_含垂尾")
    if aft:
        a = aabb(aft)
        info["aft_ymax"] = a["ymax"]
        info["aft_cut_err"] = abs(a["ymax"] - TARGET_CUT_Y)
    nose = bpy.data.objects.get("REF_机头蒙皮") or bpy.data.objects.get("Nose")
    if nose:
        a = aabb(nose)
        info["nose_ymax"] = a["ymax"]
        info["nose_ymin"] = a["ymin"]
        info["tip"] = tip
    return info


def main():
    open(os.path.join(LOG, "section7_console.txt"), "w", encoding="utf-8").close()
    log("=== §7 REF batch replace ===")

    if not os.path.isfile(BAK_SRC):
        raise FileNotFoundError(BAK_SRC)
    shutil.copy2(BAK_SRC, BAK_BEFORE)
    log(f"[bak] {BAK_SRC} → {BAK_BEFORE}")
    shutil.copy2(BAK_SRC, BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    tip0 = tip_y()
    keeper_info = verify_keeper_t_ref(tip0)
    log(f"[keeper] tip0={tip0:.4f} info={keeper_info}")

    # --- 7.4 delete ---
    deleted = []
    # also catch Fuselage* / Wing* leftovers by prefix
    extra_prefix = (
        "Fuselage", "Wing", "Winglet", "WingLE", "WingFairing", "WingBodyFairing",
        "Pylon", "Engine", "Fan", "Gear_",
    )
    to_del = set(DELETE_EXACT)
    for o in list(bpy.data.objects):
        if o.name in KEEP_NAMES:
            continue
        if o.name in to_del:
            continue
        if o.name == "GearBayDoors":
            continue  # later
        for p in extra_prefix:
            if o.name == p or o.name.startswith(p):
                to_del.add(o.name)
                break
    for name in sorted(to_del):
        if name in KEEP_NAMES:
            continue
        if delete_object(name):
            deleted.append(name)
            log(f"[del] {name}")

    # --- 7.5.2 import + T_REF ---
    imported = []
    for fn, expect in IMPORT_FILES:
        path = find_ref(fn)
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        log(f"[import] {path} → {[o.name for o in new]}")
        for ob in new:
            if ob.type != "MESH":
                continue
            apply_t_ref(ob)
            if not ob.name.startswith("REF_"):
                ob.name = "REF_" + ob.name
            imported.append(ob.name)
        # verify expected present
        for en in expect:
            if not bpy.data.objects.get(en):
                # try fuzzy
                hit = next((o for o in new if en.split("_")[-1] in o.name or en in o.name), None)
                if hit:
                    hit.name = en
                    log(f"[rename] {hit.name} forced to {en}")
                else:
                    log(f"[WARN] missing expected {en} after import {fn}")

    # --- 7.5.3 weld measure ---
    nose = bpy.data.objects.get("REF_机头蒙皮") or bpy.data.objects.get("Nose")
    mid = bpy.data.objects.get("REF_中机身蒙皮")
    aft = bpy.data.objects.get("REF_尾段蒙皮_含垂尾")
    if not nose or not mid or not aft:
        raise RuntimeError(f"missing skins nose={nose} mid={mid} aft={aft}")

    # rename Nose → REF_机头蒙皮 for clarity before join
    if nose.name == "Nose":
        nose.name = "REF_机头蒙皮"
        if nose.data:
            nose.data.name = "REF_机头蒙皮"

    front_y = cut_world_y(OBJ_FRONT_CUT_Y)
    aft_y = cut_world_y(REF_CUT_Y_IMPORTED)
    log(f"[cut] front_y={front_y:.6f} aft_y={aft_y:.6f} (target_aft={TARGET_CUT_Y})")

    dev_front = max_cut_deviation(nose, mid, front_y)
    dev_aft = max_cut_deviation(mid, aft, aft_y)
    log(f"[dev-front] {dev_front}")
    log(f"[dev-aft] {dev_aft}")

    front_mm = dev_front.get("max_mm")
    aft_mm = dev_aft.get("max_mm")
    weld_ok = (
        front_mm is not None and aft_mm is not None
        and front_mm < 5.0 and aft_mm < 5.0
    )

    result = {
        "T_REF": {
            "sx": SX, "sy": SY, "sz": SZ,
            "tx": DX, "ty": DY, "tz": DZ,
            "matrix_order": "T @ S(sx,1,sz) @ R(Z180)",
            "target_cut_y": TARGET_CUT_Y,
            "overlap_m": OVERLAP_M,
            "REF_CUT_Y_IMPORTED": REF_CUT_Y_IMPORTED,
            "front_cut_world_y": front_y,
            "aft_cut_world_y": aft_y,
        },
        "deleted": deleted,
        "imported": imported,
        "dev_front": dev_front,
        "dev_aft": dev_aft,
        "weld_ok": weld_ok,
        "keeper_info": keeper_info,
        "backup": BAK_BEFORE,
        "scripts": ["section7_ref_batch.py"],
    }

    if not weld_ok:
        log("[STOP] cut deviation ≥ 5 mm — no join, no glb")
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        result["stopped"] = True
        json.dump(result, open(os.path.join(LOG, "section7.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        open(PROGRESS, "w", encoding="utf-8").write("\n".join([
            "# PROGRESS — §7 STOPPED (weld gate)",
            f"- backup: c919.bak-before-s7.blend",
            f"- front cut max_mm={front_mm}",
            f"- aft cut max_mm={aft_mm}",
            f"- T_REF sx={SX} sy={SY} sz={SZ} tx={DX} ty={DY} tz={DZ}",
            "- deleted listed in logs/section7.json",
            "- NO Fuselage_REF join; NO glb",
            "- script: section7_ref_batch.py",
        ]) + "\n")
        return result

    # materials before join: white on mid (will inherit)
    white = find_white_mat()
    assign_slot(mid, white)

    fus = weld_fuselage(nose, mid, aft, front_y, aft_y)
    assign_slot(fus, white)
    log(f"[weld] → {fus.name} verts={len(fus.data.vertices)}")

    # --- materials 7.5.6 ---
    eng = ensure_mat("REF_EngineMetal", (0xB8 / 255, 0xBB / 255, 0xBF / 255), 0.6, 0.35)
    gear = ensure_mat("REF_GearDark", (0x3A / 255, 0x3D / 255, 0x42 / 255), 0.5, 0.45)
    door = ensure_mat("REF_舱门缝线", (0x3A / 255, 0x3D / 255, 0x42 / 255), 0.0, 0.5)
    # cabin glass: reuse existing if any
    glass = None
    for m in bpy.data.materials:
        if "窗" in m.name or "Window" in m.name or "Glass" in m.name:
            if m.name != "CockpitGlass_REF":
                glass = m
                break
    if glass is None:
        glass = ensure_mat("REF_舷窗玻璃", (0x2E / 255, 0x3A / 255, 0x3E / 255), 0.0, 0.03,
                           transmission=1.0, alpha=0.45, blend="BLEND")

    for n in ("REF_机翼_左", "REF_机翼_右", "REF_吊挂_左", "REF_吊挂_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            assign_slot(ob, white)
    for n in ("REF_发动机_左", "REF_发动机_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            assign_slot(ob, eng)
    for n in ("REF_前起落架", "REF_主起落架"):
        ob = bpy.data.objects.get(n)
        if ob:
            assign_slot(ob, gear)
    g = bpy.data.objects.get("REF_舷窗玻璃")
    if g:
        assign_slot(g, glass)
    s = bpy.data.objects.get("REF_舱门缝线")
    if s:
        assign_slot(s, door)

    # --- GearBayDoors ---
    gbd = gear_bay_decision(fus)
    result["GearBayDoors"] = gbd
    log(f"[GearBayDoors] {gbd}")

    tip = tip_y()
    measures, raw = measure_stations(tip)
    result["measurements"] = measures
    result["raw"] = raw
    result["tip"] = tip
    for m in measures:
        log(f"[meas] {m}")

    visible = sorted(
        o.name for o in bpy.data.objects
        if o.type == "MESH" and not o.hide_get()
    )
    result["visible_meshes"] = visible
    log(f"[visible] {visible}")

    rend = render_collage(tip)
    result["render"] = rend

    n_glb = export_glb()
    result["glb"] = GLB
    result["glb_mesh_count"] = n_glb

    # final backup after success
    bak_done = os.path.join(OUT, "c919.bak-section7.blend")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, bak_done)
    result["backup_done"] = bak_done
    result["stopped"] = False

    json.dump(result, open(os.path.join(LOG, "section7.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # also write under logs/
    logs_dir = os.path.join(ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    json.dump(result, open(os.path.join(logs_dir, "section7.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = [
        "# PROGRESS — §7 REF batch",
        f"- backup: c919.bak-before-s7.blend → c919.bak-section7.blend",
        f"- T_REF sx={SX:.6f} sy={SY} sz={SZ:.6f} tx={DX} ty={DY:.6f} tz={DZ:.6f}",
        f"- cuts front_mm={front_mm:.3f} aft_mm={aft_mm:.3f} weld=OK → Fuselage_REF",
        f"- deleted {len(deleted)} objs; GearBayDoors={gbd.get('action')}",
        f"- glb meshes={n_glb}; collage={rend.get('collage_name')}",
        f"- cam side tip_sx={rend.get('side_tip_sx'):.4f} tail_sx={rend.get('side_tail_sx'):.4f}",
        f"- script: section7_ref_batch.py",
    ]
    for m in measures:
        lines.append(f"- {m['项目']}: {m['实测']} (ref {m['参考']}) {m['是否通过']}")
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== §7 DONE ===")
    return result


if __name__ == "__main__":
    main()

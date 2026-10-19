# -*- coding: utf-8 -*-
"""SPEC §5 第2步补充: restore bak-s2, place nacelles/gear, rebuild pylons.

  blender -b --factory-startup -P scripts/length_step2b_pylon.py
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
BAK_S2 = os.path.join(OUT, "c919.bak-length-s2.blend")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "length-s2b")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

TARGET_SPAN = 6.07
TARGET_NAC_LE = 12.27
TARGET_NAC_CLEAR = 0.74
TARGET_GEAR_SPAN = 3.42
TARGET_MAIN_TIP = 17.58
TARGET_NOSE_TIP = 5.18
TARGET_WING_LE = 13.18
# STOP if collision or vertical gap at span too large
GAP_MAX_STOP = 2.50  # m between nacelle top and wing underside

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

NACELLE_PARTS = ["Engine_{s}", "EngineLip_{s}", "Fan_{s}"]


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "length_s2b_console.txt"), "a", encoding="utf-8") as f:
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
        "cx": 0.5 * (min(xs) + max(xs)),
        "cy": 0.5 * (min(ys) + max(ys)),
        "cz": 0.5 * (min(zs) + max(zs)),
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def translate_mesh_world(ob, dvec: Vector):
    """Translate mesh verts by world-space delta; keep object matrix."""
    if ob.type != "MESH":
        ob.location += dvec
        return
    mw = ob.matrix_world
    imw = mw.inverted()
    # world delta → local
    w0 = mw @ Vector((0, 0, 0))
    local = imw @ (w0 + dvec) - imw @ w0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for v in bm.verts:
        v.co += local
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()


def wing_le_at_x(x_abs: float, side: str = "R"):
    wing = bpy.data.objects.get(f"Wing_{side}")
    wv = mwv(wing)
    sign = 1.0 if side == "R" else -1.0
    band = [v for v in wv if abs(v.x - sign * x_abs) < 0.40]
    if not band:
        band = [v for v in wv if abs(abs(v.x) - x_abs) < 0.50]
    if not band:
        return None
    return max(v.y for v in band)


def wing_z_band_at(x_tgt: float, y0: float, y1: float, side: str):
    wing = bpy.data.objects.get(f"Wing_{side}")
    wv = mwv(wing)
    sign = 1.0 if side == "R" else -1.0
    band = [
        v for v in wv
        if abs(v.x - sign * abs(x_tgt)) < 0.45 and min(y0, y1) - 0.2 <= v.y <= max(y0, y1) + 0.2
    ]
    if not band:
        return None
    return min(v.z for v in band), max(v.z for v in band)


def sample_wing_underside(x_tgt: float, y: float, side: str, half=0.5):
    """Return approximate underside Z at (x,y), or None if no wing."""
    wing = bpy.data.objects.get(f"Wing_{side}")
    wv = mwv(wing)
    sign = 1.0 if side == "R" else -1.0
    col = [v for v in wv if abs(v.x - sign * abs(x_tgt)) < half and abs(v.y - y) < half]
    if not col:
        col = [v for v in wv if abs(v.x - sign * abs(x_tgt)) < half * 1.5 and abs(v.y - y) < half * 1.5]
    if not col:
        return None
    return min(v.z for v in col), max(v.z for v in col)


def place_nacelle_group(side: str, tip: float, ground_z: float):
    """Move Engine/Lip/Fan so cx=±6.07, LE tip-dist=12.27, zmin=ground+0.74."""
    eng = bpy.data.objects[f"Engine_{side}"]
    b = bb(eng)
    target_cx = TARGET_SPAN if side == "R" else -TARGET_SPAN
    target_le_y = tip - TARGET_NAC_LE
    target_zmin = ground_z + TARGET_NAC_CLEAR
    dx = target_cx - b["cx"]
    dy = target_le_y - b["ymax"]
    dz = target_zmin - b["zmin"]
    d = Vector((dx, dy, dz))
    names = []
    for tmpl in NACELLE_PARTS:
        n = tmpl.format(s=side)
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        translate_mesh_world(ob, d)
        names.append(n)
    bpy.context.view_layer.update()
    b2 = bb(bpy.data.objects[f"Engine_{side}"])
    log(f"[nacelle-{side}] d=({dx:.4f},{dy:.4f},{dz:.4f}) → cx={b2['cx']:.3f} LE_tip={tip-b2['ymax']:.3f} zmin={b2['zmin']:.3f} clear={b2['zmin']-ground_z:.3f}")
    return names, d, b2


def place_main_gear(side: str, tip: float):
    g = bpy.data.objects.get(f"Gear_{side}")
    if not g:
        return None
    b = bb(g)
    target_cx = TARGET_GEAR_SPAN if side == "R" else -TARGET_GEAR_SPAN
    target_cy = tip - TARGET_MAIN_TIP
    dx = target_cx - b["cx"]
    dy = target_cy - b["cy"]
    # keep Z (wheels stay on same ground)
    translate_mesh_world(g, Vector((dx, dy, 0.0)))
    bpy.context.view_layer.update()
    b2 = bb(g)
    log(f"[gear-{side}] d=({dx:.4f},{dy:.4f},0) → cx={b2['cx']:.3f} tipC={tip-b2['cy']:.3f} z=[{b2['zmin']:.3f},{b2['zmax']:.3f}]")
    return b2


def place_nose_gear(tip: float):
    g = bpy.data.objects.get("Gear_Nose")
    if not g:
        return None
    b = bb(g)
    target_cy = tip - TARGET_NOSE_TIP
    dy = target_cy - b["cy"]
    translate_mesh_world(g, Vector((0.0, dy, 0.0)))
    bpy.context.view_layer.update()
    b2 = bb(g)
    log(f"[gear-nose] dy={dy:.4f} → tipC={tip-b2['cy']:.3f}")
    return b2


def delete_object(name: str):
    ob = bpy.data.objects.get(name)
    if not ob:
        return
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)


def rebuild_pylon(side: str, tip: float):
    """Simple pylon: lower = nacelle top (aft half + forward support), upper = wing underside."""
    eng = bpy.data.objects[f"Engine_{side}"]
    eb = bb(eng)
    sign = 1.0 if side == "R" else -1.0
    x_c = eb["cx"]
    y_le, y_te = eb["ymax"], eb["ymin"]
    y_mid = 0.5 * (y_le + y_te)
    # aft half of nacelle: y_te .. y_mid; extend forward to y_le for support
    # sample stations along nacelle Y
    n_sta = 8
    ys = [y_te + (y_le - y_te) * i / (n_sta - 1) for i in range(n_sta)]

    # nacelle top Z at each Y (max Z of engine verts near x_c, y)
    ev = mwv(eng)
    nac_top = []
    for y in ys:
        col = [v for v in ev if abs(v.y - y) < 0.35 and abs(v.x - x_c) < 0.9]
        if not col:
            col = [v for v in ev if abs(v.y - y) < 0.55]
        ztop = max(v.z for v in col) if col else eb["zmax"]
        nac_top.append(ztop)

    # wing underside / upper at stations
    wing_bot, wing_top, has_wing = [], [], []
    for y in ys:
        wz = sample_wing_underside(x_c, y, side, half=0.55)
        if wz is None:
            has_wing.append(False)
            wing_bot.append(None)
            wing_top.append(None)
        else:
            has_wing.append(True)
            wing_bot.append(wz[0])
            wing_top.append(wz[1])

    # For stations without wing, extrapolate upper from nearest wing station (cantilever)
    # Upper attachment: slightly below wing underside (2 cm)
    gap_skin = 0.02
    upper_z = []
    last_bot = None
    for i in range(n_sta):
        if has_wing[i]:
            last_bot = wing_bot[i]
            upper_z.append(wing_bot[i] - gap_skin)
        else:
            upper_z.append(None)
    # fill forward cantilever: use last known wing bot, but never above nacelle-to-wing linear
    # Find aft-most wing station
    wing_idxs = [i for i, h in enumerate(has_wing) if h]
    if not wing_idxs:
        log(f"[pylon-{side}] STOP-build: no wing above nacelle span")
        return None, "NO_WING_OVERLAP"

    # For stations forward of wing, keep upper at interpolated height from nacelle top + strut rise
    # Use wing underside at the forward-most wing station for the attach line, and
    # forward of that: linear from nac_top up to a height that stays below wing LE underside
    i_wing0 = wing_idxs[-1]  # highest Y with wing (near LE)
    i_wing_aft = wing_idxs[0]
    z_attach_fwd = wing_bot[i_wing0] - gap_skin

    for i in range(n_sta):
        if upper_z[i] is not None:
            continue
        # forward of wing: horizontal beam at z_attach_fwd, but clamp below if we'd pierce
        # actually forward of wing LE there is no wing — beam at z between nac top and z_attach_fwd
        t = 0.65  # keep most of rise near wing
        upper_z[i] = nac_top[i] + t * (z_attach_fwd - nac_top[i])
        # ensure still above nacelle top
        if upper_z[i] < nac_top[i] + 0.05:
            upper_z[i] = nac_top[i] + 0.05

    # Safety: where wing exists, never exceed wing_top
    for i in wing_idxs:
        if upper_z[i] > wing_top[i] - 0.02:
            upper_z[i] = wing_top[i] - 0.02
        if upper_z[i] < wing_bot[i] - 0.15:
            # too far below — pull up to near underside
            upper_z[i] = wing_bot[i] - gap_skin

    # Build mesh: two rails (inboard/outboard) × lower/upper
    half_w = 0.12  # pylon half-width in X
    # Also taper: wider near wing
    verts = []
    # order: for each station: lower_in, lower_out, upper_in, upper_out
    for i, y in enumerate(ys):
        xl = x_c - sign * half_w  # toward fuselage slightly? keep centered
        xr = x_c + sign * half_w
        # actually both sides of pylon in X
        x0 = x_c - half_w
        x1 = x_c + half_w
        zl = nac_top[i]
        zu = upper_z[i]
        verts.extend([
            (x0, y, zl),
            (x1, y, zl),
            (x0, y, zu),
            (x1, y, zu),
        ])

    faces = []
    for i in range(n_sta - 1):
        a = i * 4
        b = (i + 1) * 4
        # lower
        faces.append((a + 0, a + 1, b + 1, b + 0))
        # upper
        faces.append((a + 2, b + 2, b + 3, a + 3))
        # -X side
        faces.append((a + 0, b + 0, b + 2, a + 2))
        # +X side
        faces.append((a + 1, a + 3, b + 3, b + 1))
    # end caps
    faces.append((0, 2, 3, 1))
    last = (n_sta - 1) * 4
    faces.append((last + 0, last + 1, last + 3, last + 2))

    delete_object(f"Pylon_{side}")
    mesh = bpy.data.meshes.new(f"Pylon_{side}")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(f"Pylon_{side}", mesh)
    bpy.context.collection.objects.link(ob)
    # material: copy from Engine if possible
    eng_ob = bpy.data.objects.get(f"Engine_{side}")
    if eng_ob and eng_ob.data.materials:
        ob.data.materials.append(eng_ob.data.materials[0])

    # pierce check
    pierced = False
    for i in wing_idxs:
        if upper_z[i] > wing_top[i] - 0.01:
            pierced = True
    status = "OK"
    detail = {
        "ys": ys,
        "nac_top": nac_top,
        "upper_z": upper_z,
        "has_wing": has_wing,
        "wing_idxs": wing_idxs,
        "pierced_upper": pierced,
    }
    if pierced:
        status = "PIERCED_UPPER"
    log(f"[pylon-{side}] rebuilt stations={n_sta} wing_hits={len(wing_idxs)} pierced={pierced}")
    return status, detail


def collision_check(side: str, tip: float):
    """At span ±6.07, check nacelle vs wing vertical relationship."""
    eng = bpy.data.objects[f"Engine_{side}"]
    eb = bb(eng)
    x_c = eb["cx"]
    # overlap Y of nacelle with wing band
    wz = wing_z_band_at(x_c, eb["ymin"], eb["ymax"], side)
    nac_zmax = eb["zmax"]
    nac_zmin = eb["zmin"]
    wle = wing_le_at_x(TARGET_SPAN, side)
    result = {
        "span_cx": x_c,
        "nac_y": [eb["ymin"], eb["ymax"]],
        "nac_z": [nac_zmin, nac_zmax],
        "wing_le_y": wle,
        "wing_le_tip": (tip - wle) if wle is not None else None,
        "nac_le_tip": tip - eb["ymax"],
        "nac_te_tip": tip - eb["ymin"],
    }
    stop = False
    reason = ""
    if wz is None:
        # nacelle fully forward of wing — measure gap in Y to wing LE
        if wle is not None:
            y_gap = eb["ymin"] - wle  # >0 means nacelle TE forward of wing LE (separated in Y)
            result["y_gap_te_to_wing_le"] = y_gap
            # vertical: no overlap in Y → not colliding
            # "差距过大" if nacelle TE far from wing LE
            if y_gap > 3.0:
                stop = True
                reason = f"Y_GAP_LARGE te_to_wing_le={y_gap:.3f}"
            elif y_gap < -0.5:
                # nacelle overlaps wing in Y but no wing verts sampled — odd
                stop = True
                reason = f"Y_OVERLAP_NO_WING_SAMPLE y_gap={y_gap:.3f}"
            else:
                reason = f"nacelle_ahead_or_near wing y_gap={y_gap:.3f}"
        else:
            stop = True
            reason = "NO_WING_AT_SPAN"
        result["wing_z"] = None
    else:
        wbot, wtop = wz
        result["wing_z"] = [wbot, wtop]
        # collision: nacelle top above wing bottom
        clear = wbot - nac_zmax
        result["vertical_clearance"] = clear
        if clear < -0.05:
            stop = True
            reason = f"COLLISION clear={clear:.3f}"
        elif clear > GAP_MAX_STOP:
            stop = True
            reason = f"GAP_TOO_LARGE clear={clear:.3f}"
        else:
            reason = f"OK clear={clear:.3f}"
    result["stop"] = stop
    result["reason"] = reason
    log(f"[collide-{side}] stop={stop} {reason} {result}")
    return result


def setup_workbench():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("WB_World") if "WB_World" not in bpy.data.worlds else bpy.data.worlds["WB_World"]
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.12, 0.14, 1.0)


def ensure_camera():
    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    bpy.context.scene.camera = cam
    return cam


def frame_side(cam, tip, ortho_scale):
    # nose LEFT: cam +X look -X
    zmid = -1.0
    ymid = tip - 38.84 * 0.5
    cam.data.ortho_scale = ortho_scale
    cam.location = (80.0, ymid, zmid)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)


def flip_png_horizontal(path):
    """Flip image in-place if nose ended up pointing right (safety)."""
    try:
        from PIL import Image
        im = Image.open(path)
        # detect: bright content centroid — skip auto; SPEC says flip if needed
        # We oriented cam for nose-left already; no flip.
        im.close()
    except Exception:
        pass


def import_ref():
    # prefer 整机.obj
    candidates = []
    for root, dirs, files in os.walk(REFS):
        for fn in files:
            low = fn.lower()
            if "整机" in fn or "zhengji" in low or (low.endswith(".obj") and "ref" in low and "nose" not in low and "detail" not in low and "cabin" not in low and "door" not in low):
                candidates.append(os.path.join(root, fn))
    # also search project
    for root, dirs, files in os.walk(ROOT):
        if "node_modules" in root or ".git" in root:
            continue
        for fn in files:
            if "整机" in fn and fn.lower().endswith(".obj"):
                candidates.append(os.path.join(root, fn))
    obj_path = candidates[0] if candidates else None
    before = set(bpy.data.objects)
    ref_note = ""
    if obj_path:
        bpy.ops.wm.obj_import(filepath=obj_path)
        ref_note = obj_path
        log(f"[ref] OBJ {obj_path}")
    else:
        fbx = os.path.join(REFS, "REF_C919_meters.fbx")
        bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
        ref_note = fbx + " (no C919_REF_整机.obj)"
        log(f"[ref] FBX fallback {fbx}")
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.name = "LengthRef_" + o.name[:50]
    return new, ref_note


def align_ref_tip(ref_objs, our_tip):
    ys = []
    for o in ref_objs:
        if o.type != "MESH":
            continue
        b = bb(o)
        ys += [b["ymin"], b["ymax"]]
    rtip = max(ys)
    dy = our_tip - rtip
    for o in ref_objs:
        o.location.y += dy
    bpy.context.view_layer.update()
    return dy


def set_vis(ours: bool):
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name.startswith("LengthRef_"):
            o.hide_render = ours
            o.hide_viewport = ours
        else:
            o.hide_render = not ours
            o.hide_viewport = not ours


def measure(tip, ground_z):
    items = []

    def add(name, ours, ref, tol_pass):
        d = ours - ref if ours is not None and ref is not None else None
        ok = abs(d) <= tol_pass if d is not None else False
        items.append({
            "项目": name,
            "实测": None if ours is None else round(ours, 3),
            "参考": ref,
            "差值": None if d is None else round(d, 3),
            "是否通过": "是" if ok else "否",
        })
        return ok

    # nose gear
    gn = bpy.data.objects.get("Gear_Nose")
    if gn:
        add("前起落架轮中心", tip - bb(gn)["cy"], TARGET_NOSE_TIP, 0.08)

    er = bpy.data.objects["Engine_R"]
    eb = bb(er)
    add("短舱前缘", tip - eb["ymax"], TARGET_NAC_LE, 0.05)
    add("短舱后缘", tip - eb["ymin"], None, 99)  # ref approx local wing LE ~15.8
    items[-1]["参考"] = 15.8
    items[-1]["差值"] = round(items[-1]["实测"] - 15.8, 3)
    items[-1]["是否通过"] = "—"  # informational vs REF description

    add("发动机展向中心", abs(eb["cx"]), TARGET_SPAN, 0.05)
    add("短舱最低点离地", eb["zmin"] - ground_z, TARGET_NAC_CLEAR, 0.05)

    gr = bpy.data.objects.get("Gear_R")
    if gr:
        gb = bb(gr)
        add("主起落架展向", abs(gb["cx"]), TARGET_GEAR_SPAN, 0.08)
        add("主起落架轮中心", tip - gb["cy"], TARGET_MAIN_TIP, 0.08)

    wing = bpy.data.objects["Wing_R"]
    wv = mwv(wing)
    root = [v for v in wv if abs(v.x) < 2.8] or wv
    wle = max(v.y for v in root)
    add("翼根前缘", tip - wle, TARGET_WING_LE, 0.05)

    return items


def write_progress(lines):
    text = "\n".join(lines[:30]) + "\n"
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"[progress] {PROGRESS} lines={min(30,len(lines))}")


def export_and_save():
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            o.hide_render = False
            o.hide_viewport = False
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    log(f"GLB {os.path.getsize(GLB)}")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")


def main():
    open(os.path.join(LOG, "length_s2b_console.txt"), "w", encoding="utf-8").close()
    log("=== LENGTH S2b §5 第2步补充 ===")

    if not os.path.isfile(BAK_S2):
        raise SystemExit(f"missing {BAK_S2}")

    # restore working from bak-s2
    shutil.copy2(BAK_S2, BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak_s2b = os.path.join(OUT, "c919.bak-length-s2b.blend")
    shutil.copy2(BLEND, bak_s2b)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, os.path.join(OUT, "c919.glb.bak-length-s2b"))
    log(f"[backup] {bak_s2b}")

    tip = tip_y()
    # ground from main gear BEFORE move (wheels stay Z)
    ground_z = bb(bpy.data.objects["Gear_R"])["zmin"]
    log(f"[ground] z={ground_z:.4f} tip={tip:.4f}")

    # 1 nacelles
    place_nacelle_group("R", tip, ground_z)
    place_nacelle_group("L", tip, ground_z)

    # 3 main gear / 4 nose gear
    place_main_gear("R", tip)
    place_main_gear("L", tip)
    place_nose_gear(tip)

    # re-read ground after gear XY move (Z unchanged)
    ground_z = bb(bpy.data.objects["Gear_R"])["zmin"]

    # 2 rebuild pylons (NOT translate)
    pyl_r, det_r = rebuild_pylon("R", tip)
    pyl_l, det_l = rebuild_pylon("L", tip)

    # 5 collision check
    col_r = collision_check("R", tip)
    col_l = collision_check("L", tip)
    stop = bool(col_r.get("stop") or col_l.get("stop") or pyl_r == "PIERCED_UPPER" or pyl_l == "PIERCED_UPPER" or pyl_r == "NO_WING_OVERLAP")

    # measures
    items = measure(tip, ground_z)
    # pylon status row
    pyl_ok = (pyl_r == "OK" and pyl_l == "OK" and not stop)
    items.append({
        "项目": "吊挂连接状态",
        "实测": f"R={pyl_r}; L={pyl_l}; collideR={col_r.get('reason')}; collideL={col_l.get('reason')}",
        "参考": "下连短舱顶后半/上连翼下/不穿上翼面",
        "差值": "—",
        "是否通过": "否" if stop or not pyl_ok else "是",
    })

    # renders
    setup_workbench()
    cam = ensure_camera()
    COMMON = 38.84 * 1.12
    frame_side(cam, tip, COMMON)
    bpy.context.scene.render.filepath = os.path.join(PREV, "side_ours.png")
    bpy.ops.render.render(write_still=True)
    log(f"[render] side_ours")

    ref_objs, ref_note = import_ref()
    align_ref_tip(ref_objs, tip)
    set_vis(ours=False)
    bpy.context.scene.render.filepath = os.path.join(PREV, "side_ref.png")
    bpy.ops.render.render(write_still=True)
    log(f"[render] side_ref")
    set_vis(ours=True)

    export_and_save()

    result = {
        "backup": bak_s2b,
        "restored_from": BAK_S2,
        "stop": stop,
        "pylon_R": pyl_r,
        "pylon_L": pyl_l,
        "collision_R": col_r,
        "collision_L": col_l,
        "measurements": items,
        "ref_source": ref_note,
        "scripts": ["length_step2b_pylon.py"],
        "ground_z": ground_z,
        "tip": tip,
    }
    with open(os.path.join(LOG, "length_s2b.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # PROGRESS ≤30 lines
    prog = [
        "# PROGRESS — LENGTH s2b (§5 第2步补充)",
        f"- restored: c919.bak-length-s2.blend → backup c919.bak-length-s2b.blend",
        f"- nacelle: span ±{TARGET_SPAN}, LE tip={TARGET_NAC_LE}, clear={TARGET_NAC_CLEAR}",
        f"- pylons: rebuilt (not translated) R={pyl_r} L={pyl_l}",
        f"- gear: main span ±{TARGET_GEAR_SPAN} tipC={TARGET_MAIN_TIP}; nose tipC={TARGET_NOSE_TIP}",
        f"- STOP={stop} R:{col_r.get('reason')} | L:{col_l.get('reason')}",
        f"- ref compare: {ref_note}",
        f"- previews: public/models/length-s2b/",
        f"- script: scripts/length_step2b_pylon.py",
        f"- no Step3; no cabin REF; Nose/CockpitGlass_REF untouched",
    ]
    for it in items:
        prog.append(f"- {it['项目']}: {it['实测']} (ref {it['参考']}) Δ={it['差值']} pass={it['是否通过']}")
    write_progress(prog)

    log(f"=== S2b DONE STOP={stop} ===")


if __name__ == "__main__":
    main()

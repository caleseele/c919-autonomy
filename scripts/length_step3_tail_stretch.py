# -*- coding: utf-8 -*-
"""SPEC §5 Step 3: stretch aft fuselage by 7.38/5.00; keep VT/HT unstretched.

  blender -b --factory-startup -P scripts/length_step3_tail_stretch.py
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
PREV = os.path.join(OUT, "length-s3")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

FACTOR = 7.38 / 5.00  # 1.476
TARGET_VT = 31.46
TARGET_HT = 32.86  # VT + 1.40
TARGET_VT_TO_TC = 7.38
TARGET_LEN = 38.84
HT_OFFSET = 1.40

# Never stretch these (translate only if needed)
NO_STRETCH = {
    "VerticalTail", "Rudder", "Stab_L", "Stab_R",
    "Nose", "CockpitGlass_REF", "CockpitDarkPlane", "RadomePanelLines",
    "REF_WindshieldFrame", "REF_Wipers", "REF_ProbesAntennas", "REF_CockpitInterior",
    "Gear_Nose", "Gear_L", "Gear_R",
    "Engine_L", "Engine_R", "EngineLip_L", "EngineLip_R", "Fan_L", "Fan_R",
    "Pylon_L", "Pylon_R",
    "Wing_L", "Wing_R", "WingLE_L", "WingLE_R", "Winglet_L", "Winglet_R",
    "WingFairing_L", "WingFairing_R", "WingBodyFairing_L", "WingBodyFairing_R",
}

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "length_s3_console.txt"), "a", encoding="utf-8") as f:
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
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def vt_root_le_y():
    vt = mwv(bpy.data.objects["VerticalTail"])
    zmin = min(v.z for v in vt)
    low = [v for v in vt if v.z < zmin + 1.8] or vt
    return max(v.y for v in low)


def ht_root_le_y():
    st = mwv(bpy.data.objects.get("Stab_R") or bpy.data.objects["Stab_L"])
    # root = inboard
    root = [v for v in st if abs(v.x) < 1.5] or st
    return max(v.y for v in root)


def tailcone_end_y():
    tc = bpy.data.objects.get("TailCone")
    return min(v.y for v in mwv(tc))


def wing_root_le_y():
    wing = bpy.data.objects.get("Wing_R")
    wv = mwv(wing)
    root = [v for v in wv if abs(v.x) < 2.8] or wv
    return max(v.y for v in root)


def nacelle_le_y():
    return max(v.y for v in mwv(bpy.data.objects["Engine_R"]))


def nacelle_te_y():
    return min(v.y for v in mwv(bpy.data.objects["Engine_R"]))


def translate_mesh_world(ob, dvec: Vector):
    if ob.type != "MESH":
        ob.location += dvec
        return
    mw = ob.matrix_world
    imw = mw.inverted()
    w0 = mw @ Vector((0, 0, 0))
    local = imw @ (w0 + dvec) - imw @ w0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for v in bm.verts:
        v.co += local
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()


def stretch_mesh_aft(ob, y_pivot: float, factor: float):
    """Stretch world-Y of verts with y < y_pivot about y_pivot by factor. Returns n moved."""
    if ob.type != "MESH" or ob.name in NO_STRETCH:
        return 0
    mw = ob.matrix_world
    imw = mw.inverted()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = 0
    for v in bm.verts:
        w = mw @ v.co
        if w.y < y_pivot - 1e-6:
            y_new = y_pivot + factor * (w.y - y_pivot)
            w2 = Vector((w.x, y_new, w.z))
            v.co = imw @ w2
            n += 1
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    return n


def stretch_scene(y_pivot: float, factor: float):
    """Stretch fuselage skin + tailcone + aft decorations; skip NO_STRETCH."""
    # Always stretch these if present
    prefer = [
        "Fuselage", "Fuselage_ORIG", "TailCone",
        "TailMark", "TailMark_L",
        "Stripe_L", "Stripe_R", "Title", "Title_L",
        "Windows", "WindowFrames", "AntennasAPU",
        "DoorFrames", "Doors", "DoorWindows",
        "GearBayDoors", "Flag_L", "Flag_R",
    ]
    report = {}
    done = set()
    for name in prefer:
        ob = bpy.data.objects.get(name)
        if not ob or name in NO_STRETCH:
            continue
        n = stretch_mesh_aft(ob, y_pivot, factor)
        report[name] = n
        done.add(name)
        if n:
            log(f"[stretch] {name} verts={n}")
    # any other mesh with significant geometry aft of pivot (not in NO_STRETCH)
    for ob in list(bpy.data.objects):
        if ob.type != "MESH" or ob.name in NO_STRETCH or ob.name in done:
            continue
        if ob.name.startswith("LengthRef_"):
            continue
        b = bb(ob)
        if b["ymin"] >= y_pivot - 0.05:
            continue
        # skip if mostly forward
        if b["ymax"] > y_pivot + 5 and b["ymin"] > y_pivot - 1:
            continue
        n = stretch_mesh_aft(ob, y_pivot, factor)
        report[ob.name] = n
        if n:
            log(f"[stretch-extra] {ob.name} verts={n}")
    bpy.context.view_layer.update()
    return report


def adjust_stabs(tip: float, y_vt: float):
    """Ensure HT root LE is +1.40 m aft of VT root LE (tip-dist)."""
    y_ht = ht_root_le_y()
    # tip distances
    vt_tip = tip - y_vt
    ht_tip = tip - y_ht
    delta = ht_tip - vt_tip  # should be +1.40 (HT more aft = larger tip-dist)
    log(f"[stab] before VT_tip={vt_tip:.3f} HT_tip={ht_tip:.3f} delta={delta:.3f} want={HT_OFFSET}")
    err = delta - HT_OFFSET
    if abs(err) > 0.20:
        # HT tip too small → need move aft → decrease Y by (HT_OFFSET - delta)
        # tip_ht_new = tip_ht - dy_world? tip = tip_y - y_ht; increase tip_ht means decrease y_ht
        # want tip_ht = vt_tip + 1.40 → y_ht_target = tip - (vt_tip + 1.40)
        y_target = tip - (vt_tip + HT_OFFSET)
        dy = y_target - y_ht
        for n in ("Stab_L", "Stab_R"):
            ob = bpy.data.objects.get(n)
            if ob:
                translate_mesh_world(ob, Vector((0.0, dy, 0.0)))
                log(f"[stab] move {n} dy={dy:.4f}")
        bpy.context.view_layer.update()
        return dy, True
    return 0.0, False


def keep_vt_at_target(tip: float, y_pivot_used: float):
    """Optionally nudge VT/Rudder so VT root LE tip-dist ≈ 31.46 (should already be)."""
    y_vt = vt_root_le_y()
    target_y = tip - TARGET_VT
    dy = target_y - y_vt
    if abs(dy) > 0.05:
        for n in ("VerticalTail", "Rudder"):
            ob = bpy.data.objects.get(n)
            if ob:
                translate_mesh_world(ob, Vector((0.0, dy, 0.0)))
                log(f"[vt] nudge {n} dy={dy:.4f}")
        bpy.context.view_layer.update()
        return dy
    return 0.0


def measure(tip):
    items = []

    def add(name, ours, ref, tol):
        d = None if ours is None or ref is None else ours - ref
        ok = d is not None and abs(d) <= tol
        items.append({
            "项目": name,
            "实测": None if ours is None else round(ours, 3),
            "参考": ref,
            "差值": None if d is None else round(d, 3),
            "是否通过": "是" if ok else "否",
        })

    y_vt = vt_root_le_y()
    y_ht = ht_root_le_y()
    y_tc = tailcone_end_y()
    overall = tip - y_tc
    vt_to_tc = (tip - y_tc) - (tip - y_vt)

    add("全长 tip→尾锥", overall, TARGET_LEN, 0.08)
    # also accept 38.90
    if items[-1]["是否通过"] == "否" and abs(overall - 38.90) <= 0.08:
        items[-1]["参考"] = 38.90
        items[-1]["差值"] = round(overall - 38.90, 3)
        items[-1]["是否通过"] = "是"

    add("垂尾根部前缘", tip - y_vt, TARGET_VT, 0.08)
    add("水平尾翼根部前缘", tip - y_ht, TARGET_HT, 0.15)
    add("垂尾根前缘→尾锥末端", vt_to_tc, TARGET_VT_TO_TC, 0.08)
    add("翼根前缘", tip - wing_root_le_y(), 13.18, 0.05)
    add("短舱前缘", tip - nacelle_le_y(), 12.27, 0.05)
    add("短舱后缘", tip - nacelle_te_y(), 15.8, 99)
    items[-1]["是否通过"] = "—"

    gn = bpy.data.objects.get("Gear_Nose")
    if gn:
        add("前起落架轮中心", tip - bb(gn)["cy"], 5.18, 0.08)
    gr = bpy.data.objects.get("Gear_R")
    if gr:
        add("主起落架轮中心", tip - bb(gr)["cy"], 17.58, 0.08)

    # HT-VT offset check
    ht_vt = (tip - y_ht) - (tip - y_vt)
    add("平尾相对垂尾(应+1.40)", ht_vt, HT_OFFSET, 0.20)

    return items, {
        "y_vt": y_vt, "y_ht": y_ht, "y_tc": y_tc,
        "overall": overall, "vt_to_tc": vt_to_tc,
    }


def setup_cam(tip):
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
    cam.location = (80.0, tip - 38.84 * 0.5, -1.0)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)  # nose LEFT
    scene.camera = cam
    return cam


def render_pair(tip):
    setup_cam(tip)
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
    open(os.path.join(LOG, "length_s3_console.txt"), "w", encoding="utf-8").close()
    log("=== LENGTH S3 Step3 tail stretch ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak = os.path.join(OUT, "c919.bak-length-s3.blend")
    shutil.copy2(BLEND, bak)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, os.path.join(OUT, "c919.glb.bak-length-s3"))
    log(f"[backup] {bak}")

    tip = tip_y()
    y_vt0 = vt_root_le_y()
    y_tc0 = tailcone_end_y()
    vt_to_tc0 = (tip - y_tc0) - (tip - y_vt0)
    log(f"[before] tip={tip:.4f} VT_LE_tip={tip-y_vt0:.4f} TC_tip={tip-y_tc0:.4f} VT→TC={vt_to_tc0:.4f} factor={FACTOR:.4f}")

    # Confirm separate empennage objects
    emp = [n for n in ("VerticalTail", "Rudder", "Stab_L", "Stab_R", "TailCone") if bpy.data.objects.get(n)]
    log(f"[empennage] separate={emp}")

    # Pivot at current VT root LE (fixed cross-section)
    y_pivot = y_vt0
    report = stretch_scene(y_pivot, FACTOR)

    # Keep VT unstretched at ~31.46
    keep_vt_at_target(tip, y_pivot)
    # Adjust HT offset
    stab_dy, stab_moved = adjust_stabs(tip, vt_root_le_y())

    items, raw = measure(tip)
    ref_note = render_pair(tip)
    export_save()

    result = {
        "backup": bak,
        "factor": FACTOR,
        "y_pivot": y_pivot,
        "stretch_report": report,
        "empennage_separate": emp,
        "stab_dy": stab_dy,
        "stab_moved": stab_moved,
        "measurements": items,
        "raw": raw,
        "ref_source": ref_note,
        "scripts": ["length_step3_tail_stretch.py"],
    }
    with open(os.path.join(LOG, "length_s3.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — LENGTH s3 (§5 Step 3)",
        f"- backup: c919.bak-length-s3.blend",
        f"- empennage separate: {', '.join(emp)}",
        f"- pivot VT root LE y={y_pivot:.3f} (tip {tip-y_pivot:.3f}); factor={FACTOR:.4f}",
        f"- stretched Fuselage/TailCone/aft skin; VT/Rudder/Stab NOT stretched",
        f"- stab adjust dy={stab_dy:.4f} moved={stab_moved}",
        f"- after: len={raw['overall']:.3f} VT→TC={raw['vt_to_tc']:.3f} VT={tip-raw['y_vt']:.3f} HT={tip-raw['y_ht']:.3f}",
        f"- compare: length-s3/ (tip-left tip-aligned); REF={ref_note}",
        f"- script: length_step3_tail_stretch.py",
        f"- no cabin REF import; Nose untouched",
    ]
    for it in items:
        prog.append(f"- {it['项目']}: {it['实测']} ref={it['参考']} d={it['差值']} pass={it['是否通过']}")
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log(f"=== S3 DONE len={raw['overall']:.3f} VT→TC={raw['vt_to_tc']:.3f} ===")


if __name__ == "__main__":
    main()

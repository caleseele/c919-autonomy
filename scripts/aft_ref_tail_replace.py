# -*- coding: utf-8 -*-
"""§5b REF tail wholesale replace + §6 LIST ONLY.

  blender -b --factory-startup -P scripts/aft_ref_tail_replace.py
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
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BAK_SRC = os.path.join(OUT, "c919.bak-aft-s5b2.blend")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-ref-tail")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
REF_TAIL = os.path.join(REFS, "C919_REF_尾段.obj")

# REF cut (after Blender default obj_import: forward -Z → Blender Y)
REF_CUT_Y_IMPORTED = 20.891  # before Z-180
REF_HALF_W = 1.978
REF_BELLY_Z = 2.135
REF_BACK_Z = 6.256
REF_CENTER_Z = 4.196
OVERLAP = 0.015  # 1.5 cm forward overlap

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "aft_ref_tail_console.txt"), "a", encoding="utf-8") as f:
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


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def apply_mw(ob):
    me = ob.data
    me.transform(ob.matrix_world)
    me.update()
    ob.matrix_world = Matrix.Identity(4)


def delete_object(name: str):
    ob = bpy.data.objects.get(name)
    if not ob:
        return False
    me = ob.data if ob.type == "MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)
    return True


def get_nose_sx_sz(tip: float):
    """X/Z scale matching REF_机头蒙皮 if present, else from Fuselage @26 vs REF section."""
    skin = None
    for n in ("REF_机头蒙皮", "Nose"):
        if bpy.data.objects.get(n):
            skin = bpy.data.objects[n]
            break
    # Prefer stored scale from measuring Nose width/height vs known REF nose dims —
    # SPEC: same sx,sz as REF_机头蒙皮. Measure fuselage at station 26 for target.
    fu = bpy.data.objects["Fuselage"]
    y26 = tip - 26.0
    band = [v for v in mwv(fu) if abs(v.y - y26) < 0.25]
    if len(band) < 8:
        band = [v for v in mwv(fu) if abs(v.y - y26) < 0.5]
    our_hw = max(abs(v.x) for v in band)
    our_zmin = min(v.z for v in band)
    our_zmax = max(v.z for v in band)
    our_h = our_zmax - our_zmin
    our_cz = 0.5 * (our_zmin + our_zmax)
    # REF section after import (before rot): half_w 1.978, H = 6.256-2.135 = 4.121
    ref_hw = REF_HALF_W
    ref_h = REF_BACK_Z - REF_BELLY_Z
    sx = our_hw / ref_hw
    sz = our_h / ref_h
    # If Nose exists, try to recover sx/sz from Nose vs typical REF nose —
    # use fuselage-matched as authoritative for seam fit
    return {
        "sx": sx, "sz": sz,
        "our_hw": our_hw, "our_h": our_h, "our_cz": our_cz, "our_zmin": our_zmin, "our_zmax": our_zmax,
        "y26": y26,
        "skin_name": skin.name if skin else None,
    }


def trim_antennas_aft(tip: float):
    """Delete AntennasAPU verts with tip_dist > 26; keep forward."""
    ob = bpy.data.objects.get("AntennasAPU")
    if not ob:
        return {"deleted_object": False, "verts_removed": 0}
    mw = ob.matrix_world
    imw = mw.inverted()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    kill = [v for v in bm.verts if (tip - (mw @ v.co).y) > 26.0 - 1e-4]
    n = len(kill)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    # if empty, delete object
    if len(ob.data.vertices) == 0:
        delete_object("AntennasAPU")
        return {"deleted_object": True, "verts_removed": n}
    log(f"[antennas] removed aft verts={n} remaining={len(ob.data.vertices)}")
    return {"deleted_object": False, "verts_removed": n, "remaining": len(ob.data.vertices)}


def bisect_fuselage_aft(tip: float):
    """Bisect Fuselage at tip_dist=26, delete aft."""
    ob = bpy.data.objects["Fuselage"]
    apply_mw(ob)
    y_cut = tip - 26.0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    # plane: keep forward (y >= y_cut - eps). clear_inner clears side opposite to normal.
    # normal +Y means clear_inner clears -Y side (aft if aft is smaller Y)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    ret = bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        dist=1e-4,
        plane_co=Vector((0.0, y_cut, 0.0)),
        plane_no=Vector((0.0, 1.0, 0.0)),
        clear_inner=True,   # delete aft (y < y_cut)
        clear_outer=False,
    )
    # fill cut
    bmesh.ops.edgeloop_fill(bm, edges=[e for e in ret.get("geom_cut", []) if isinstance(e, bmesh.types.BMEdge)])
    # fallback holes_fill
    be = [e for e in bm.edges if e.is_boundary]
    if be:
        try:
            bmesh.ops.holes_fill(bm, edges=be, sides=0)
        except Exception:
            pass
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    a = aabb(ob)
    log(f"[bisect] Fuselage at y={y_cut:.4f} tip26; AABB y=[{a['ymin']:.3f},{a['ymax']:.3f}]")
    return y_cut, a


def import_ref_tail():
    before = set(bpy.data.objects)
    if not os.path.isfile(REF_TAIL):
        # try alternate encodings / box-copied names
        for fn in os.listdir(REFS):
            if "尾段" in fn and fn.endswith(".obj"):
                path = os.path.join(REFS, fn)
                break
        else:
            raise FileNotFoundError(REF_TAIL)
    else:
        path = REF_TAIL
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    log(f"[import] {path} n={len(new)} names={[o.name for o in new]}")
    return new, path


def transform_ref_tail(objs, sx, sz, tip, our_cz, y26):
    """Z-180, scale X/Z, translate cut→y26+overlap, center Z align. Y no scale."""
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((sx, 1.0, sz, 1.0))
    # After import: cut at y=+20.891. After Z-180: y'=-20.891
    cut_y_after_rot_scale = -REF_CUT_Y_IMPORTED  # sy=1
    target_cut_y = y26 + OVERLAP  # slightly forward of seam
    dy = target_cut_y - cut_y_after_rot_scale
    # center Z: after rot Z unchanged; after scale z*=sz; REF center 4.196
    cz_after = REF_CENTER_Z * sz
    dz = our_cz - cz_after
    dx = 0.0
    T = Matrix.Translation(Vector((dx, dy, dz)))
    M = T @ S @ R

    for ob in objs:
        if ob.type != "MESH":
            continue
        apply_mw(ob)
        me = ob.data
        me.transform(M)
        me.update()
        ob.matrix_world = Matrix.Identity(4)
        # rename with prefix if needed
        if not ob.name.startswith("REF_"):
            ob.name = "REF_" + ob.name
    info = {
        "sx": sx, "sz": sz, "sy": 1.0,
        "dx": dx, "dy": dy, "dz": dz,
        "target_cut_y": target_cut_y,
        "overlap_m": OVERLAP,
        "matrix_order": "T @ S(sx,1,sz) @ R(Z180)",
    }
    log(f"[xform] sx={sx:.4f} sz={sz:.4f} dy={dy:.4f} dz={dz:.4f} target_cut_y={target_cut_y:.4f}")
    return info


def assign_materials(objs):
    """Skin/HT/rudder = fuselage white; APU dark metal; antennas = probe metal."""
    # find fuselage white material
    white = None
    fuse = bpy.data.objects.get("Fuselage")
    if fuse and fuse.data.materials:
        white = fuse.data.materials[0]
    if white is None:
        white = bpy.data.materials.new("FuselageWhite_Tail")
        white.use_nodes = True
        bsdf = white.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.85, 0.85, 0.87, 1)
            bsdf.inputs["Roughness"].default_value = 0.35

    def ensure_mat(name, color, metallic, roughness):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = (*color, 1)
                if "Metallic" in bsdf.inputs:
                    bsdf.inputs["Metallic"].default_value = metallic
                bsdf.inputs["Roughness"].default_value = roughness
        return m

    apu_mat = ensure_mat("REF_APU_Metal", (0.15, 0.16, 0.18), 0.85, 0.35)
    ant_mat = bpy.data.materials.get("REF_探头天线") or ensure_mat("REF_探头天线", (0.557, 0.569, 0.588), 0.8, 0.3)

    for ob in objs:
        if ob.type != "MESH":
            continue
        n = ob.name
        ob.data.materials.clear()
        if "APU" in n:
            ob.data.materials.append(apu_mat)
        elif "天线" in n:
            ob.data.materials.append(ant_mat)
        else:
            ob.data.materials.append(white)
        log(f"[mat] {n} -> {ob.data.materials[0].name}")


def measure_all(tip, y26, ref_objs):
    items = []

    def add(name, ours, ref, tol):
        d = None if ours is None or ref is None else ours - ref
        ok = d is not None and abs(d) <= tol
        items.append({
            "项目": name, "实测": None if ours is None else round(ours, 3),
            "参考": ref, "差值": None if d is None else round(d, 3),
            "是否通过": "是" if ok else "否",
        })

    # length: tip to aftmost among REF objs
    aft = min(aabb(o)["ymin"] for o in ref_objs if o.type == "MESH")
    add("全长 tip→尾端", tip - aft, 38.84, 0.05)

    # VT root LE: from skin+VT object — low Z verts near fin, max Y of lower root
    skin = next((o for o in ref_objs if "蒙皮" in o.name or "垂尾" in o.name), None)
    vt_le = None
    if skin:
        vs = mwv(skin)
        # vertical fin: high Z, near center X
        fin = [v for v in vs if v.z > 1.5 and abs(v.x) < 0.8]
        if fin:
            zmin_f = min(v.z for v in fin)
            root = [v for v in fin if v.z < zmin_f + 1.2]
            # root LE = max Y of root
            if root:
                vt_le = tip - max(v.y for v in root)
    add("垂尾根部前缘", vt_le, 31.46, 0.15)

    ht = next((o for o in ref_objs if "水平" in o.name), None)
    ht_le = None
    if ht:
        vs = mwv(ht)
        root = [v for v in vs if abs(v.x) < 1.5] or vs
        ht_le = tip - max(v.y for v in root)
    add("水平尾翼根部前缘", ht_le, 32.86, 0.20)

    # seam section delta
    fu = bpy.data.objects["Fuselage"]
    band_f = [v for v in mwv(fu) if abs(v.y - y26) < 0.2]
    band_r = []
    if skin:
        band_r = [v for v in mwv(skin) if abs(v.y - (y26 + OVERLAP)) < 0.25]
        if len(band_r) < 8:
            band_r = [v for v in mwv(skin) if abs((tip - v.y) - 26.0) < 0.3]
    seam = {"ok": False}
    if band_f and band_r:
        df = (min(v.z for v in band_f), max(v.z for v in band_f), max(abs(v.x) for v in band_f))
        dr = (min(v.z for v in band_r), max(v.z for v in band_r), max(abs(v.x) for v in band_r))
        dhw = abs(df[2] - dr[2])
        dz0 = abs(df[0] - dr[0])
        dz1 = abs(df[1] - dr[1])
        seam = {"d_half_w": dhw, "d_belly": dz0, "d_back": dz1, "ok": max(dhw, dz0, dz1) < 0.01}
        add("接缝半宽差", dhw, 0.0, 0.01)
        add("接缝机腹差", dz0, 0.0, 0.01)
        add("接缝机背差", dz1, 0.0, 0.01)

    # meshes aft of 26 besides REF five
    extras = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o in ref_objs or o.name.startswith("LengthRef_"):
            continue
        a = aabb(o)
        if tip - a["ymin"] > 26.0 + 0.05:
            # has geometry aft of 26
            extras.append(o.name)
    add("26m后非REF网格数", len(extras), 0, 0)
    if extras:
        items[-1]["是否通过"] = "否"
        items[-1]["实测"] = f"{len(extras)}:{extras}"

    return items, {"aft_y": aft, "vt_le": vt_le, "ht_le": ht_le, "seam": seam, "extras": extras}


def cam_and_render(tip, tail_y):
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
    ymid = 0.5 * (tip + tail_y)
    configs = [
        {"loc": (-80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, -math.pi / 2), "tag": "-X_look_+X"},
        {"loc": (80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, math.pi / 2), "tag": "+X_look_-X"},
    ]
    scene.camera = cam
    tip_pt = Vector((0.0, tip, 0.0))
    tail_pt = Vector((0.0, tail_y, 0.0))
    chosen = None
    for cfg in configs:
        cam.location = cfg["loc"]
        cam.rotation_euler = cfg["rot"]
        bpy.context.view_layer.update()
        ts = world_to_camera_view(scene, cam, tip_pt).x
        ls = world_to_camera_view(scene, cam, tail_pt).x
        log(f"[cam-try] {cfg['tag']} tip_sx={ts:.4f} tail_sx={ls:.4f}")
        if ts < ls:
            chosen = {"tag": cfg["tag"], "tip_screen_x": ts, "tail_screen_x": ls, "orient_ok": True}
            break
    if not chosen:
        chosen = {"tag": "FAIL", "tip_screen_x": ts, "tail_screen_x": ls, "orient_ok": False}

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ours = os.path.join(PREV, f"side_ours_{stamp}.png")
    refp = os.path.join(PREV, f"side_ref_{stamp}.png")
    cmpn = f"side_compare_{stamp}.png"
    cmp = os.path.join(PREV, cmpn)

    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    scene.render.filepath = ours
    bpy.ops.render.render(write_still=True)

    # REF meters for compare
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
    refs = [o for o in bpy.data.objects if o not in before]
    for o in refs:
        o.name = "LengthRef_" + o.name[:40]
    ys = []
    for o in refs:
        if o.type == "MESH":
            a = aabb(o)
            ys += [a["ymin"], a["ymax"]]
    dy = tip - max(ys)
    for o in refs:
        o.location.y += dy
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not o.name.startswith("LengthRef_")
    scene.render.filepath = refp
    bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False

    # stack note: do in PowerShell after; write paths
    return {
        "cam": chosen,
        "ours": ours,
        "ref": refp,
        "compare_name": cmpn,
        "compare_path": cmp,
        "stamp": stamp,
    }


def list_cabin_windows_doors():
    """§6 LIST ONLY — names to delete before REF cabin import."""
    keys = ("window", "door", "窗", "门", "Window", "Door", "舷窗", "舱门")
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n = o.name
        # skip REF tail / nose / glass cockpit
        if n.startswith("REF_尾") or n.startswith("REF_水平") or n.startswith("REF_方向") or n.startswith("REF_APU"):
            continue
        if n.startswith("REF_机头") or "CockpitGlass" in n or n == "Nose":
            continue
        low = n.lower()
        hit = any(k.lower() in low or k in n for k in keys)
        # also exact known set
        known = {
            "Windows", "WindowFrames", "Doors", "DoorFrames", "DoorWindows",
            "Windows.001", "Doors.001",
        }
        if hit or n in known or n.split(".")[0] in known:
            a = aabb(o)
            rows.append({
                "name": n,
                "verts": len(o.data.vertices),
                "aabb": a,
                "hide_get": bool(o.hide_get()),
            })
    rows.sort(key=lambda r: r["name"])
    return rows


def export_save():
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    # ensure REF tail visible
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    log(f"GLB {os.path.getsize(GLB)}")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")


def main():
    open(os.path.join(LOG, "aft_ref_tail_console.txt"), "w", encoding="utf-8").close()
    log("=== REF TAIL REPLACE §5b ===")
    if not os.path.isfile(BAK_SRC):
        raise SystemExit(f"missing {BAK_SRC}")
    shutil.copy2(BAK_SRC, BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak = os.path.join(OUT, "c919.bak-aft-ref-tail.blend")
    shutil.copy2(BLEND, bak)
    if os.path.isfile(GLB):
        shutil.copy2(GLB, os.path.join(OUT, "c919.glb.bak-aft-ref-tail"))
    log(f"[backup] {bak}")

    tip = tip_y()
    scales = get_nose_sx_sz(tip)
    log(f"[scales] {scales}")

    # 1 deletes
    deleted = []
    for n in ("Fuselage_ORIG", "VerticalTail", "Rudder", "Stab_L", "Stab_R"):
        if delete_object(n):
            deleted.append(n)
            log(f"[del] {n}")
    ant = trim_antennas_aft(tip)
    log(f"[del-ant] {ant}")

    # 2 bisect
    y26, fuse_a = bisect_fuselage_aft(tip)

    # 3 import + transform
    ref_objs, ref_path = import_ref_tail()
    xinfo = transform_ref_tail(
        ref_objs, scales["sx"], scales["sz"], tip, scales["our_cz"], y26
    )
    assign_materials(ref_objs)

    bpy.context.view_layer.update()
    items, raw = measure_all(tip, y26, [o for o in bpy.data.objects if o.name.startswith("REF_") and o.type == "MESH"])
    # refresh ref_objs list after rename
    ref_objs = [o for o in bpy.data.objects if o.name.startswith("REF_") and (
        "尾" in o.name or "水平" in o.name or "方向" in o.name or "APU" in o.name or "天线" in o.name
    )]
    if not ref_objs:
        ref_objs = [o for o in bpy.data.objects if o.name.startswith("REF_") and o.type == "MESH"
                    and o.name not in ("REF_机头蒙皮", "REF_WindshieldFrame", "REF_Wipers",
                                       "REF_ProbesAntennas", "REF_CockpitInterior")]
        # filter by aft
        ref_objs = [o for o in ref_objs if tip - aabb(o)["ymin"] > 20]

    tail_y = min(aabb(o)["ymin"] for o in ref_objs) if ref_objs else tip - 38.84
    rend = cam_and_render(tip, tail_y)

    # §6 list only
    cabin_list = list_cabin_windows_doors()
    log(f"[§6 list] n={len(cabin_list)} (NO delete, NO import)")

    export_save()

    result = {
        "backup": bak,
        "restored_from": BAK_SRC,
        "deleted": deleted,
        "antennas": ant,
        "scales": scales,
        "xform": xinfo,
        "ref_path": ref_path,
        "ref_objects": [o.name for o in ref_objs],
        "measurements": items,
        "raw": raw,
        "camera": rend["cam"],
        "render": {k: rend[k] for k in ("ours", "ref", "compare_name", "compare_path", "stamp")},
        "section6_delete_list": cabin_list,
        "section6_imported": False,
        "scripts": ["aft_ref_tail_replace.py"],
    }
    with open(os.path.join(LOG, "aft_ref_tail.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open(os.path.join(LOG, "section6_delete_list.json"), "w", encoding="utf-8") as f:
        json.dump({"confirm_before_delete": True, "objects": cabin_list,
                   "next": "import C919_REF_舱门舷窗.obj after user confirm"},
                  f, ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — REF tail replace (§5b) + §6 list",
        f"- restore bak-aft-s5b2 → backup bak-aft-ref-tail.blend",
        f"- deleted: {deleted}; antennas aft trimmed: {ant}",
        f"- Fuselage bisect @ tip26 y={y26:.3f}; REF tail imported+xform sx={scales['sx']:.4f} sz={scales['sz']:.4f}",
        f"- REF objs: {[o.name for o in ref_objs]}",
        f"- cam tip_sx={rend['cam']['tip_screen_x']:.4f} tail_sx={rend['cam']['tail_screen_x']:.4f} ok={rend['cam']['orient_ok']}",
        f"- render stamp {rend['stamp']} (stack externally)",
        f"- §6 LIST ONLY n={len(cabin_list)} — await confirm before delete/import",
        f"- script: aft_ref_tail_replace.py",
    ]
    for it in items:
        prog.append(f"- {it['项目']}: {it['实测']} ref={it['参考']} d={it['差值']} pass={it['是否通过']}")
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log("=== REF TAIL DONE (§6 list only) ===")


if __name__ == "__main__":
    main()

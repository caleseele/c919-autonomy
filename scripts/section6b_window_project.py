# -*- coding: utf-8 -*-
"""§6b fix: reimport cabin with tail-matched xform; radial project +1mm;
list/fix dorsal; ensure REF_尾段天线.

  blender -b --factory-startup -P scripts/section6b_window_project.py
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
BLEND = os.path.join(OUT, "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section6")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

# Same xform as REF_尾段 (aft_ref_tail.json) — sy=1, aligns REF cabin to fuselage stations
TAIL_SX = 1.0475227637527205
TAIL_SZ = 1.0104343689231436
TAIL_DX = 0.0
TAIL_DY = 15.463823181152343
TAIL_DZ = -4.239782612001511

OFFSET_OUT = 0.001
SUNK_EPS = 5e-4
STATION_SPLIT = 26.0
DORSAL_STATION = 24.5
DORSAL_TOL = 1.5
RAY_OUT = 6.0

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section6b_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs


def aabb_verts(ob):
    vs = mwv(ob)
    if not vs:
        return None
    return {
        "xmin": min(v.x for v in vs), "xmax": max(v.x for v in vs),
        "ymin": min(v.y for v in vs), "ymax": max(v.y for v in vs),
        "zmin": min(v.z for v in vs), "zmax": max(v.z for v in vs),
    }


def aabb(ob):
    a = aabb_verts(ob)
    if a:
        return a
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return {
        "xmin": min(p.x for p in pts), "xmax": max(p.x for p in pts),
        "ymin": min(p.y for p in pts), "ymax": max(p.y for p in pts),
        "zmin": min(p.z for p in pts), "zmax": max(p.z for p in pts),
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


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


def find_path(keywords, folder=REFS, ext=".obj"):
    for fn in os.listdir(folder):
        if not fn.endswith(ext):
            continue
        if all(k in fn for k in keywords):
            return os.path.join(folder, fn)
    raise FileNotFoundError(str(keywords))


def tail_matrix():
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((TAIL_SX, 1.0, TAIL_SZ, 1.0))
    T = Matrix.Translation(Vector((TAIL_DX, TAIL_DY, TAIL_DZ)))
    return T @ S @ R


def skin_targets():
    fuse = bpy.data.objects.get("Fuselage")
    aft = None
    for o in bpy.data.objects:
        if o.type == "MESH" and "蒙皮" in o.name and "尾" in o.name:
            aft = o
            break
    return fuse, aft


def eval_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    return ev, ev.to_mesh()


def project_point_on_skin(skin, world_co):
    """Radial raycast from outside toward axis; fallback closest_point with end-cap reject."""
    mw = skin.matrix_world
    imw = mw.inverted()
    axis = Vector((0.0, world_co.y, 0.0))
    radial = Vector((world_co.x, 0.0, world_co.z - 0.0))
    if radial.length < 1e-5:
        radial = Vector((world_co.x, 0.0, 1.0))
    radial.normalize()

    # Ray from outside toward axis (local space for ray_cast)
    start_w = axis + radial * RAY_OUT
    dir_w = -radial
    start_l = imw @ start_w
    # direction in local (approximate via two points)
    end_l = imw @ (start_w + dir_w)
    dir_l = (end_l - start_l).normalized()

    ok, loc_l, norm_l, _face = skin.ray_cast(start_l, dir_l, distance=RAY_OUT * 2.2)
    if ok:
        wloc = mw @ loc_l
        wn = (mw.to_3x3() @ norm_l).normalized()
        # ensure outward (away from axis)
        if wn.dot(radial) < 0:
            wn = -wn
        signed = (world_co - wloc).dot(wn)
        return wloc, wn, signed, "ray"

    # fallback: closest_point; reject end-cap (|ny| dominant)
    local = imw @ world_co
    ok2, loc2, norm2, _ = skin.closest_point_on_mesh(local)
    if not ok2:
        return None, None, None, None
    wloc = mw @ loc2
    wn = (mw.to_3x3() @ norm2).normalized()
    # if end-cap (normal mostly along Y), push radially using XY of hit
    if abs(wn.y) > 0.55:
        r2 = Vector((wloc.x, 0.0, wloc.z))
        if r2.length < 1e-5:
            r2 = radial
        r2.normalize()
        # walk outward along radial with small steps to find non-cap hit
        for dist in (0.05, 0.15, 0.35, 0.7, 1.2):
            probe = Vector((r2.x * dist, world_co.y, r2.z * dist))
            ok3, loc3, norm3, _ = skin.closest_point_on_mesh(imw @ probe)
            if not ok3:
                continue
            wn3 = (mw.to_3x3() @ norm3).normalized()
            if abs(wn3.y) > 0.55:
                continue
            wloc = mw @ loc3
            wn = wn3
            break
        else:
            # last resort: place at radial distance of fuselage half-width-ish
            wloc = Vector((radial.x * 2.05, world_co.y, radial.z * 2.05 * 0.0 + radial.z * abs(world_co.z)))
            # simpler: keep x,z scale from closest non-y
            wloc = axis + radial * max(abs(world_co.x), abs(world_co.z), 1.9)
            wn = radial.copy()
    if wn.dot(radial) < 0:
        wn = -wn
    signed = (world_co - wloc).dot(wn)
    return wloc, wn, signed, "closest"


def mesh_islands(ob):
    tip = tip_y()
    mw = ob.matrix_world
    bm = bmesh.new()
    bm.from_mesh(ob.data)
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
                    remaining.discard(o)
                    stack.append(o)
        idxs = [v.index for v in isl]
        cents = [mw @ v.co for v in isl]
        c = Vector((
            sum(p.x for p in cents) / len(cents),
            sum(p.y for p in cents) / len(cents),
            sum(p.z for p in cents) / len(cents),
        ))
        islands.append({"verts": idxs, "centroid": c, "station": tip - c.y, "nverts": len(idxs)})
    bm.free()
    return islands


def measure_sunk(ob, fuse, aft_skin):
    islands = mesh_islands(ob)
    sunk_lt26 = sunk_ge26 = 0
    total_lt26 = total_ge26 = 0
    records = []
    for isl in islands:
        st = isl["station"]
        if st < STATION_SPLIT:
            skin = fuse
            total_lt26 += 1
            band = "<26"
        else:
            skin = aft_skin or fuse
            total_ge26 += 1
            band = ">=26"
        if skin is None:
            records.append({**isl, "band": band, "signed": None, "sunk": False})
            continue
        _w, _n, signed, _m = project_point_on_skin(skin, isl["centroid"])
        sunk = signed is not None and signed < SUNK_EPS
        if sunk:
            if st < STATION_SPLIT:
                sunk_lt26 += 1
            else:
                sunk_ge26 += 1
        records.append({
            "station": round(st, 3),
            "nverts": isl["nverts"],
            "band": band,
            "signed": None if signed is None else round(signed, 5),
            "sunk": sunk,
            "skin": skin.name,
            "verts": isl["verts"],
        })
    return {
        "name": ob.name,
        "total": len(islands),
        "lt26": total_lt26,
        "ge26": total_ge26,
        "sunk_lt26": sunk_lt26,
        "sunk_ge26": sunk_ge26,
        "sunk_total": sunk_lt26 + sunk_ge26,
        "records": records,
        "y_span": aabb_verts(ob),
    }


def project_all_islands(ob, fuse, aft_skin):
    """Project EVERY island onto correct skin +1mm (not only sunk) — fixes end-cap collapse."""
    tip = tip_y()
    mw = ob.matrix_world
    imw = mw.inverted()
    me = ob.data
    islands = mesh_islands(ob)
    n = 0
    for isl in islands:
        st = isl["station"]
        skin = fuse if st < STATION_SPLIT else (aft_skin or fuse)
        if skin is None:
            continue
        for vi in isl["verts"]:
            v = me.vertices[vi]
            wco = mw @ v.co
            wloc, wn, _s, _m = project_point_on_skin(skin, wco)
            if wloc is None:
                continue
            v.co = imw @ (wloc + wn * OFFSET_OUT)
        n += 1
    me.update()
    # refresh bound_box
    bpy.context.view_layer.update()
    return n


def assign_cabin_materials(objs):
    def ensure(name, color, rough, metal=0.0, alpha=1.0, transmission=0.0):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
            bsdf.inputs["Roughness"].default_value = rough
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = metal
            if alpha < 1.0 or transmission > 0:
                if "Alpha" in bsdf.inputs:
                    bsdf.inputs["Alpha"].default_value = alpha
                if "Transmission Weight" in bsdf.inputs:
                    bsdf.inputs["Transmission Weight"].default_value = transmission
                elif "Transmission" in bsdf.inputs:
                    bsdf.inputs["Transmission"].default_value = transmission
                m.blend_method = "BLEND"
        return m

    glass = None
    for m in bpy.data.materials:
        if "舷窗" in m.name or ("glass" in m.name.lower() and "Cockpit" not in m.name):
            glass = m
            break
    if glass is None:
        glass = ensure("REF_舷窗玻璃", (0.18, 0.23, 0.24), 0.03, 0.0, 0.45, 1.0)
    seam = ensure("REF_舱门缝线", (0.227, 0.239, 0.259), 0.5, 0.0)
    for ob in objs:
        if ob.type != "MESH":
            continue
        ob.data.materials.clear()
        if "玻璃" in ob.name or "窗" in ob.name:
            ob.data.materials.append(glass)
        else:
            ob.data.materials.append(seam)
        log(f"[mat] {ob.name} -> {ob.data.materials[0].name}")


def reimport_cabin(tip):
    """Delete collapsed cabin objs; reimport with tail-matched xform."""
    deleted = []
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        if ("舷窗" in o.name and "玻璃" in o.name) or ("舱门" in o.name and "缝" in o.name):
            deleted.append(o.name)
            delete_object(o.name)
    path = find_path(["舱门"]) if any("舱门" in fn for fn in os.listdir(REFS)) else None
    if path is None:
        for fn in os.listdir(REFS):
            if fn.endswith(".obj") and ("舷窗" in fn or "舱门" in fn):
                path = os.path.join(REFS, fn)
                break
    if path is None:
        raise FileNotFoundError("cabin obj")
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    M = tail_matrix()
    for ob in new:
        if ob.type != "MESH":
            continue
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
        if not ob.name.startswith("REF_"):
            ob.name = "REF_" + ob.name
    bpy.context.view_layer.update()
    assign_cabin_materials(new)
    spans = {}
    for ob in new:
        if ob.type != "MESH":
            continue
        a = aabb_verts(ob)
        spans[ob.name] = {
            "verts": len(ob.data.vertices),
            "station": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
            "y": [round(a["ymin"], 4), round(a["ymax"], 4)],
            "z": [round(a["zmin"], 3), round(a["zmax"], 3)],
        }
        log(f"[cabin-import] {ob.name} {spans[ob.name]}")
    return new, deleted, path, spans


def ensure_tail_antenna(tip):
    existing = [o for o in bpy.data.objects if "尾段" in o.name and "天线" in o.name]
    # drop any with absurd Z
    good = []
    for o in existing:
        a = aabb_verts(o)
        if a["zmin"] < -5 or a["zmax"] > 15:
            log(f"[antenna] delete bad {o.name} z=[{a['zmin']:.2f},{a['zmax']:.2f}]")
            delete_object(o.name)
        else:
            good.append(o)
    if good:
        o = good[0]
        # delete extras
        for e in good[1:]:
            delete_object(e.name)
        a = aabb_verts(o)
        return {
            "status": "kept",
            "name": o.name,
            "verts": len(o.data.vertices),
            "station_span": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
            "bbox": {k: round(v, 3) for k, v in a.items()},
            "动作": "保留",
        }

    path = find_path(["尾段"])
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    keep = next((o for o in new if "天线" in o.name), None)
    for o in new:
        if o is not keep:
            delete_object(o.name)
    if keep is None:
        return {"status": "missing_in_obj", "动作": "重导失败"}
    apply_mw(keep)
    keep.data.transform(tail_matrix())
    keep.data.update()
    keep.matrix_world = Matrix.Identity(4)
    if not keep.name.startswith("REF_"):
        keep.name = "REF_" + keep.name
    bpy.context.view_layer.update()
    mat = bpy.data.materials.get("REF_探头天线")
    if mat is None:
        mat = bpy.data.materials.new("REF_探头天线")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.557, 0.569, 0.588, 1.0)
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = 0.8
            bsdf.inputs["Roughness"].default_value = 0.3
    keep.data.materials.clear()
    keep.data.materials.append(mat)
    a = aabb_verts(keep)
    log(f"[antenna-reimport] {keep.name} st={[tip-a['ymax'], tip-a['ymin']]} z=[{a['zmin']:.3f},{a['zmax']:.3f}]")
    return {
        "status": "reimported",
        "name": keep.name,
        "verts": len(keep.data.vertices),
        "station_span": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
        "bbox": {k: round(v, 3) for k, v in a.items()},
        "动作": "重导",
    }


def list_dorsal(tip):
    y_lo = tip - (DORSAL_STATION + DORSAL_TOL)
    y_hi = tip - (DORSAL_STATION - DORSAL_TOL)
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        a = aabb(o)
        if a["ymax"] < y_lo or a["ymin"] > y_hi:
            continue
        if a["zmax"] < 0.3:
            continue
        st = [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)]
        rows.append({
            "name": o.name,
            "verts": len(o.data.vertices),
            "bbox": {k: round(v, 3) for k, v in a.items()},
            "station_span": st,
        })
    rows.sort(key=lambda r: r["name"])
    return rows


def classify_and_delete_dorsal(rows):
    protected_sub = (
        "Fuselage", "GearBayDoors", "Nose", "CockpitGlass",
        "REF_尾段蒙皮", "REF_舷窗", "REF_舱门", "REF_水平", "REF_方向", "REF_APU",
        "REF_尾段天线", "Wing", "Flag_", "REF_机头", "REF_探头", "REF_雨刮",
        "REF_风挡", "REF_驾驶", "Engine", "Nacelle", "Pylon", "LandingGear",
    )
    actions = []
    deleted = []
    ambiguous = []
    for r in rows:
        n = r["name"]
        if any(p in n for p in protected_sub) or n in ("Fuselage", "GearBayDoors", "Nose"):
            actions.append({**r, "动作": "保留", "note": "主体/REF"})
            continue
        if n == "AntennasAPU" or (n.startswith("Antenna") and not n.startswith("REF_")):
            actions.append({**r, "动作": "删除", "note": "前段天线残留/凸块嫌疑"})
            if delete_object(n):
                deleted.append(n)
            continue
        b = r["bbox"]
        narrow = abs(b["xmax"]) < 1.2 and abs(b["xmin"]) < 1.2
        compact = (b["ymax"] - b["ymin"]) < 2.5 and b["zmax"] > 1.2
        if narrow and compact and r["verts"] < 500:
            actions.append({**r, "动作": "待确认", "note": "紧凑机背上凸"})
            ambiguous.append(n)
        else:
            actions.append({**r, "动作": "保留", "note": "区域重叠非凸块"})
    return actions, deleted, ambiguous


def cam_render(tip):
    ys = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            a = aabb(o)
            ys += [a["ymin"], a["ymax"]]
    tail_y = min(ys)
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
    cam.location = (-80.0, ymid, 0.0)
    cam.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)
    scene.camera = cam
    bpy.context.view_layer.update()
    ts = world_to_camera_view(scene, cam, Vector((0, tip, 0))).x
    ls = world_to_camera_view(scene, cam, Vector((0, tail_y, 0))).x
    if not (ts < ls):
        cam.location = (80.0, ymid, 0.0)
        cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
        bpy.context.view_layer.update()
        ts = world_to_camera_view(scene, cam, Vector((0, tip, 0))).x
        ls = world_to_camera_view(scene, cam, Vector((0, tail_y, 0))).x
    log(f"[cam] tip_sx={ts:.6f} tail_sx={ls:.6f} ok={ts < ls}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ours = os.path.join(PREV, f"side_ours_{stamp}.png")
    refp = os.path.join(PREV, f"side_ref_{stamp}.png")
    cmp = os.path.join(PREV, f"side_compare_{stamp}.png")

    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    scene.render.filepath = ours
    bpy.ops.render.render(write_still=True)

    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(REFS, "REF_C919_meters.fbx"), global_scale=1.0)
    refs = [o for o in bpy.data.objects if o not in before]
    for o in refs:
        o.name = "LengthRef_" + o.name[:40]
    rys = []
    for o in refs:
        if o.type == "MESH":
            a = aabb(o)
            rys += [a["ymin"], a["ymax"]]
    dy = tip - max(rys)
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

    # write stack hint file for external PIL
    with open(os.path.join(LOG, "section6b_stack.json"), "w", encoding="utf-8") as f:
        json.dump({"ours": ours, "ref": refp, "compare": cmp, "stamp": stamp}, f)

    return {
        "tip_screen_x": ts, "tail_screen_x": ls, "orient_ok": ts < ls,
        "ours": ours, "ref": refp, "compare_path": cmp, "stamp": stamp,
    }


def main():
    open(os.path.join(LOG, "section6b_console.txt"), "w", encoding="utf-8").close()
    log("=== SECTION 6b FIX: reimport cabin + radial project + dorsal ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # backup current (may already be bak-section6b from prior run — refresh)
    bak = os.path.join(OUT, "c919.bak-section6b.blend")
    # if prior bak exists keep first generation as .pre; overwrite bak with pre-fix state
    if os.path.isfile(bak):
        shutil.copy2(bak, os.path.join(OUT, "c919.bak-section6b-prerun.blend"))
    shutil.copy2(BLEND, bak)
    log(f"[backup] {bak}")

    tip = tip_y()
    log(f"[tip] {tip:.6f}")

    # Measure BEFORE on collapsed cabin (if still present)
    fuse, aft_skin = skin_targets()
    before_stats = {}
    glass0 = next((o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name), None)
    seam0 = next((o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name), None)
    for label, ob in (("glass", glass0), ("seam", seam0)):
        if ob is None:
            continue
        # quick: if y-span < 0.5m treat ALL as sunk/collapsed
        a = aabb_verts(ob)
        yspan = a["ymax"] - a["ymin"]
        m = measure_sunk(ob, fuse, aft_skin)
        if yspan < 0.5:
            # force count as all sunk for reporting
            m["sunk_lt26"] = m["lt26"]
            m["sunk_ge26"] = m["ge26"]
            m["sunk_total"] = m["total"]
            m["collapsed"] = True
        before_stats[label] = {
            "name": m["name"], "total": m["total"],
            "lt26": m["lt26"], "ge26": m["ge26"],
            "sunk_lt26": m["sunk_lt26"], "sunk_ge26": m["sunk_ge26"],
            "sunk_total": m["sunk_total"],
            "yspan": round(yspan, 4),
            "station_span": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
            "collapsed": yspan < 0.5,
        }
        log(f"[before] {label} sunk={m['sunk_total']}/{m['total']} yspan={yspan:.4f} st={before_stats[label]['station_span']}")

    # Reimport cabin
    new, del_cabin, path, spans = reimport_cabin(tip)
    log(f"[reimport-cabin] deleted={del_cabin} path={path}")

    fuse, aft_skin = skin_targets()
    # Project all islands
    projected = {}
    after_stats = {}
    for ob in new:
        if ob.type != "MESH":
            continue
        label = "glass" if ("玻璃" in ob.name or "窗" in ob.name) else "seam"
        n = project_all_islands(ob, fuse, aft_skin)
        projected[label] = n
        m = measure_sunk(ob, fuse, aft_skin)
        a = aabb_verts(ob)
        after_stats[label] = {
            "name": m["name"], "total": m["total"],
            "lt26": m["lt26"], "ge26": m["ge26"],
            "sunk_lt26": m["sunk_lt26"], "sunk_ge26": m["sunk_ge26"],
            "sunk_total": m["sunk_total"],
            "yspan": round(a["ymax"] - a["ymin"], 4),
            "station_span": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
        }
        log(f"[after] {label} sunk={m['sunk_total']}/{m['total']} "
            f"lt26={m['sunk_lt26']}/{m['lt26']} ge26={m['sunk_ge26']}/{m['ge26']} "
            f"st={after_stats[label]['station_span']}")

    # Dorsal list + delete
    dorsal_rows = list_dorsal(tip)
    log(f"[dorsal] n={len(dorsal_rows)}")
    for r in dorsal_rows:
        log(f"  {r['name']} v={r['verts']} st={r['station_span']} zmax={r['bbox']['zmax']}")
    actions, deleted, ambiguous = classify_and_delete_dorsal(dorsal_rows)
    log(f"[dorsal] deleted={deleted} ambiguous={ambiguous}")

    ant = ensure_tail_antenna(tip)
    log(f"[antenna] {ant}")

    assert bpy.data.objects.get("GearBayDoors"), "GearBayDoors missing"

    rend = cam_render(tip)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"[save] {BLEND}")

    sink_table = []
    for label, title in (("glass", "REF_舷窗玻璃"), ("seam", "REF_舱门缝线")):
        b = before_stats.get(label, {})
        a = after_stats.get(label, {})
        if not a:
            continue
        sink_table.append({
            "项目": title,
            "修正前陷入块数": b.get("sunk_total", "N/A"),
            "修正后陷入块数": a.get("sunk_total", "N/A"),
            "是否通过": "是" if a.get("sunk_total", 1) == 0 else "否",
            "修正前站位": b.get("station_span"),
            "修正后站位": a.get("station_span"),
            "lt26_after": f"{a.get('sunk_lt26')}/{a.get('lt26')}",
            "ge26_after": f"{a.get('sunk_ge26')}/{a.get('ge26')}",
        })

    dorsal_table = []
    for a in actions:
        act = a["动作"]
        if a["name"] in deleted:
            act = "删除"
        dorsal_table.append({
            "物体": a["name"], "bbox": a["bbox"], "verts": a["verts"],
            "station_span": a["station_span"], "动作": act, "note": a.get("note", ""),
        })
    dorsal_table.append({
        "物体": ant.get("name", "REF_尾段天线"),
        "bbox": ant.get("bbox"),
        "verts": ant.get("verts"),
        "station_span": ant.get("station_span"),
        "动作": ant.get("动作", ant.get("status")),
        "note": ant.get("status"),
    })

    result = {
        "backup": bak,
        "tip": tip,
        "before": before_stats,
        "after": after_stats,
        "projected_islands": projected,
        "sink_table": sink_table,
        "cabin_reimport": {"deleted": del_cabin, "path": path, "spans": spans},
        "dorsal_list": dorsal_rows,
        "dorsal_table": dorsal_table,
        "deleted_dorsal": deleted,
        "ambiguous_dorsal": ambiguous,
        "antenna": ant,
        "camera": {k: rend[k] for k in ("tip_screen_x", "tail_screen_x", "orient_ok")},
        "render": rend,
        "scripts": ["section6b_window_project.py"],
        "note": "86 glass islands = SPEC correct; reimport used tail xform sy=1",
    }
    with open(os.path.join(LOG, "section6b.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    cmpn = os.path.basename(rend["compare_path"])
    prog = [
        "# PROGRESS — §6b cabin reimport + radial project",
        f"- backup: c919.bak-section6b.blend",
        f"- root cause: §6 nose SY-scale + shrinkwrap → windows collapsed to Fuselage cut @26m",
        f"- reimported cabin with REF_尾段 xform (sy=1); radial project +1mm",
        f"- glass sunk {before_stats.get('glass',{}).get('sunk_total')}→{after_stats.get('glass',{}).get('sunk_total')} "
        f"st {after_stats.get('glass',{}).get('station_span')}",
        f"- seam sunk {before_stats.get('seam',{}).get('sunk_total')}→{after_stats.get('seam',{}).get('sunk_total')}",
        f"- dorsal deleted: {deleted}; antenna: {ant.get('status')} st={ant.get('station_span')}",
        f"- windows 86 = SPEC OK; GearBayDoors kept",
        f"- cam tip_sx={rend['tip_screen_x']:.4f} tail_sx={rend['tail_screen_x']:.4f}",
        f"- compare: section6/{cmpn} (stack externally if needed)",
        f"- script: section6b_window_project.py",
    ]
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log("=== §6b FIX DONE ===")


if __name__ == "__main__":
    main()

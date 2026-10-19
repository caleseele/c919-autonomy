# -*- coding: utf-8 -*-
"""§9: gear bay doors + wing-root fairing crease. Once; report 9.3.

  blender -b --factory-startup -P scripts/section9_gear_fairing.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
REFS = os.path.join(ROOT, "refs")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section9")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK = os.path.join(OUT, "c919.bak-before-s9.blend")
BAK_DONE = os.path.join(OUT, "c919.bak-section9.blend")

SX = 1.0475227637527205
SZ = 1.0104343689231436
INV_SX = 1.0 / SX
INV_SZ = 1.0 / SZ
TX, TY, TZ = 0.0, 15.463823181152343, -4.239782612001511

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section9_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]


def aabb(ob):
    vs = mwv(ob)
    if not vs:
        vs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in vs]
    ys = [p.y for p in vs]
    zs = [p.z for p in vs]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def combine_aabb(obs):
    boxes = [aabb(o) for o in obs]
    return {
        "xmin": min(b["xmin"] for b in boxes),
        "xmax": max(b["xmax"] for b in boxes),
        "ymin": min(b["ymin"] for b in boxes),
        "ymax": max(b["ymax"] for b in boxes),
        "zmin": min(b["zmin"] for b in boxes),
        "zmax": max(b["zmax"] for b in boxes),
    }


def center_bb(b):
    return Vector((
        0.5 * (b["xmin"] + b["xmax"]),
        0.5 * (b["ymin"] + b["ymax"]),
        0.5 * (b["zmin"] + b["zmax"]),
    ))


def size_bb(b):
    return Vector((
        b["xmax"] - b["xmin"],
        b["ymax"] - b["ymin"],
        b["zmax"] - b["zmin"],
    ))


def aabb_deltas(a, b):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    d = {k: abs(a[k] - b[k]) * 1000.0 for k in keys}
    d["max_mm"] = max(d.values())
    return d


def apply_mw(ob):
    ob.data.transform(ob.matrix_world)
    ob.data.update()
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


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Fuselage_REF"]))


def T_REF_matrix():
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((SX, 1.0, SZ, 1.0))
    T = Matrix.Translation(Vector((TX, TY, TZ)))
    return T @ S @ R


def unscale_matrix(z0):
    T1 = Matrix.Translation(Vector((0.0, 0.0, -z0)))
    S = Matrix.Diagonal((INV_SX, 1.0, INV_SZ, 1.0))
    T2 = Matrix.Translation(Vector((0.0, 0.0, z0)))
    return T2 @ S @ T1


def find_gear_parts_obj():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "起落架" in fn and "分件" in fn:
            return os.path.join(REFS, fn)
    raise FileNotFoundError("C919_REF_起落架分件.obj")


def align_group_to_target(obs, target_bb):
    raw_bb = combine_aabb(obs)
    rc = center_bb(raw_bb)
    tc = center_bb(target_bb)
    rs = size_bb(raw_bb)
    ts = size_bb(target_bb)
    sx = ts.x / rs.x if rs.x > 1e-9 else 1.0
    sy = ts.y / rs.y if rs.y > 1e-9 else 1.0
    sz = ts.z / rs.z if rs.z > 1e-9 else 1.0
    S = Matrix.Diagonal((sx, sy, sz, 1.0))
    M = Matrix.Translation(tc) @ S @ Matrix.Translation(-rc)
    for ob in obs:
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return {"sx": sx, "sy": sy, "sz": sz, "scale": [sx, sy, sz], "rc": list(rc), "tc": list(tc)}


def hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def ensure_mat(name, hex_color, metallic, roughness):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    if nt is None:
        return m
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    rgb = hex_rgb(hex_color)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    for key in ("Base Color", "Metallic", "Roughness"):
        if key in bsdf.inputs:
            for link in list(bsdf.inputs[key].links):
                nt.links.remove(link)
    return m


def assign_mat(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def export_glb():
    bpy.ops.object.select_all(action="DESELECT")
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.hide_get() or o.hide_render:
            continue
        o.select_set(True)
        n += 1
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
    log(f"[glb] {n} -> {GLB}")
    return n


def fuselage_auto_smooth_60(fus):
    me = fus.data
    if hasattr(me, "edges"):
        for e in me.edges:
            e.use_edge_sharp = False
    if hasattr(me, "attributes"):
        for attr_name in list(me.attributes.keys()):
            if "sharp" in attr_name.lower():
                try:
                    me.attributes.remove(me.attributes[attr_name])
                    log(f"[smooth] removed attr {attr_name}")
                except Exception as e:
                    log(f"[smooth] attr remove fail {attr_name}: {e}")

    bpy.ops.object.select_all(action="DESELECT")
    fus.select_set(True)
    bpy.context.view_layer.objects.active = fus
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        try:
            bpy.ops.mesh.mark_sharp(clear=True)
        except Exception as e:
            log(f"[smooth] mark_sharp clear: {e}")
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as e:
        log(f"[smooth] edit clear: {e}")
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    angle_rad = math.radians(60.0)
    info = {"method": None, "old": None, "new": 60.0}

    for mod in fus.modifiers:
        if mod.type == "EDGE_SPLIT":
            info["method"] = "EDGE_SPLIT"
            info["old"] = math.degrees(mod.split_angle) if hasattr(mod, "split_angle") else None
            if hasattr(mod, "split_angle"):
                mod.split_angle = angle_rad
            log(f"[smooth] EDGE_SPLIT {info['old']}->60")
            return info

    if hasattr(me, "use_auto_smooth"):
        info["method"] = "use_auto_smooth"
        info["old"] = math.degrees(me.auto_smooth_angle) if hasattr(me, "auto_smooth_angle") else None
        me.use_auto_smooth = True
        if hasattr(me, "auto_smooth_angle"):
            me.auto_smooth_angle = angle_rad
        log(f"[smooth] use_auto_smooth {info['old']}->60")
        return info

    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass

    try:
        bpy.ops.object.shade_smooth_by_angle(angle=angle_rad)
        info["method"] = "shade_smooth_by_angle_op"
        log("[smooth] shade_smooth_by_angle 60")
        # try update existing modifier angle if created
        for mod in fus.modifiers:
            for attr in ("angle", "smooth_angle", "split_angle"):
                if hasattr(mod, attr):
                    old = getattr(mod, attr)
                    try:
                        old_deg = math.degrees(old) if isinstance(old, float) and old < 10 else old
                    except Exception:
                        old_deg = old
                    setattr(mod, attr, angle_rad)
                    info["method"] = f"shade_smooth_by_angle+{mod.name}.{attr}"
                    info["old"] = old_deg
                    log(f"[smooth] set {mod.name}.{attr} {old_deg}->60")
                    return info
        return info
    except TypeError:
        try:
            bpy.ops.object.shade_smooth_by_angle()
            for mod in fus.modifiers:
                for attr in ("angle", "smooth_angle", "split_angle"):
                    if hasattr(mod, attr):
                        old = getattr(mod, attr)
                        try:
                            old_deg = math.degrees(old) if isinstance(old, float) and old < 10 else old
                        except Exception:
                            old_deg = old
                        setattr(mod, attr, angle_rad)
                        info["method"] = f"{mod.name}.{attr}"
                        info["old"] = old_deg
                        log(f"[smooth] {mod.name}.{attr} {old_deg}->60")
                        return info
        except Exception as e:
            log(f"[smooth] shade_smooth_by_angle fail: {e}")
    except Exception as e:
        log(f"[smooth] shade_smooth_by_angle fail2: {e}")

    for mod in fus.modifiers:
        for attr in ("angle", "smooth_angle", "split_angle"):
            if hasattr(mod, attr):
                old = getattr(mod, attr)
                try:
                    old_deg = math.degrees(old) if isinstance(old, float) and old < 10 else old
                except Exception:
                    old_deg = old
                setattr(mod, attr, angle_rad)
                info["method"] = f"{mod.type}.{attr}"
                info["old"] = old_deg
                log(f"[smooth] {mod.name}.{attr} {old_deg}->60")
                return info

    info["method"] = "cleared_sharp_only"
    log("[smooth] only cleared sharp; no angle param found")
    return info


def region_objects(tip):
    st_lo, st_hi = 10.0, 23.0
    y_hi = tip - st_lo
    y_lo = tip - st_hi
    wing_zmins = []
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            vs = [v for v in mwv(ob) if abs(v.x) <= 3.5 and y_lo <= v.y <= y_hi]
            if vs:
                wing_zmins.append(min(v.z for v in vs))
            else:
                wing_zmins.append(aabb(ob)["zmin"])
    wing_under = min(wing_zmins) if wing_zmins else 0.0
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_get():
            continue
        a = aabb(o)
        oy0 = max(a["ymin"], y_lo)
        oy1 = min(a["ymax"], y_hi)
        if oy1 - oy0 < 0.02:
            continue
        ox0 = max(a["xmin"], -3.5)
        ox1 = min(a["xmax"], 3.5)
        if ox1 - ox0 < 0.02:
            continue
        if a["zmin"] > wing_under + 0.15:
            continue
        rows.append({
            "name": o.name,
            "aabb": {k: round(v, 4) for k, v in a.items()},
            "zmin": round(a["zmin"], 4),
        })
    return rows, wing_under, y_lo, y_hi


def check_coplanar_wing_faces(tip):
    fus = bpy.data.objects["Fuselage_REF"]
    st_lo, st_hi = 10.0, 23.0
    y_hi = tip - st_lo
    y_lo = tip - st_hi
    fus_pts = [v for v in mwv(fus) if abs(v.x) <= 3.5 and y_lo <= v.y <= y_hi]
    if len(fus_pts) > 8000:
        step = max(1, len(fus_pts) // 8000)
        fus_pts = fus_pts[::step]
    notes = []
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            notes.append({"wing": n, "error": "missing"})
            continue
        me = ob.data
        close_faces = 0
        sample_pos = []
        mw = ob.matrix_world
        for poly in me.polygons:
            c = mw @ poly.center
            if abs(c.x) > 3.5 or c.y < y_lo or c.y > y_hi:
                continue
            dmin = min((c - p).length for p in fus_pts) if fus_pts else 999.0
            if dmin < 0.002:
                close_faces += 1
                if len(sample_pos) < 5:
                    sample_pos.append({
                        "x": round(c.x, 4), "y": round(c.y, 4), "z": round(c.z, 4),
                        "st": round(tip - c.y, 3), "dist_mm": round(dmin * 1000, 3),
                    })
        notes.append({
            "wing": n,
            "faces_dist_lt_2mm": close_faces,
            "samples": sample_pos,
        })
        log(f"[coplanar] {n}: {close_faces} faces dist-lt-2mm")
    return notes


def render_wing_root(tip):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.film_transparent = False

    cam = bpy.data.objects.get("S9Cam")
    if cam is None:
        data = bpy.data.cameras.new("S9Cam")
        cam = bpy.data.objects.new("S9Cam", data)
        bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "PERSP"
    cam.data.lens = 45

    focus_st = 15.5
    focus_y = tip - focus_st
    focus = Vector((-1.2, focus_y, -0.3))
    loc = Vector((-18.0, focus_y + 12.0, 4.5))
    cam.location = loc
    cam.rotation_euler = (focus - loc).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(PREV, f"wing_root_gear_{stamp}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log(f"[render] {path}")
    return {"path": path, "name": os.path.basename(path), "stamp": stamp}


def main():
    open(os.path.join(LOG, "section9_console.txt"), "w", encoding="utf-8").close()
    log("=== section9 gear + fairing ===")
    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    shutil.copy2(BLEND, BAK)
    log(f"[bak] -> {BAK}")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    old_nose = bpy.data.objects.get("REF_前起落架")
    old_main = bpy.data.objects.get("REF_主起落架")
    if not old_nose or not old_main:
        raise RuntimeError("missing REF_前起落架 / REF_主起落架")
    old_nose_bb = aabb(old_nose)
    old_main_bb = aabb(old_main)
    tip = tip_y()
    z0 = min(v.z for v in mwv(old_main))
    log(f"[old nose] {old_nose_bb}")
    log(f"[old main] {old_main_bb}")
    log(f"[tip]={tip:.4f} ground_z={z0:.4f}")

    path = find_gear_parts_obj()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    log(f"[import] {len(new)} from {path}: {[o.name for o in new]}")
    if len(new) != 4:
        raise RuntimeError(f"expected 4 gear parts, got {len(new)}")

    M_ref = T_REF_matrix()
    M_un = unscale_matrix(z0)
    M = M_un @ M_ref
    for ob in new:
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    log("[xform] T_REF then unscale applied")

    nose_parts = [o for o in new if "前起落架" in o.name]
    main_parts = [o for o in new if "主起落架" in o.name]
    if len(nose_parts) != 2 or len(main_parts) != 2:
        raise RuntimeError(f"nose/main parts {len(nose_parts)}/{len(main_parts)}")

    align_n = align_group_to_target(nose_parts, old_nose_bb)
    align_m = align_group_to_target(main_parts, old_main_bb)
    log(f"[align nose] {align_n['scale']}")
    log(f"[align main] {align_m['scale']}")

    new_nose_bb = combine_aabb(nose_parts)
    new_main_bb = combine_aabb(main_parts)
    dN = aabb_deltas(new_nose_bb, old_nose_bb)
    dM = aabb_deltas(new_main_bb, old_main_bb)
    log(f"[delta nose] {dN}")
    log(f"[delta main] {dM}")

    result = {
        "backup": BAK,
        "T_REF": {
            "sx": SX, "sy": 1.0, "sz": SZ, "tx": TX, "ty": TY, "tz": TZ,
            "matrix_order": "T @ S(sx,1,sz) @ R(Z180)",
        },
        "unscale": {"inv_sx": INV_SX, "inv_sz": INV_SZ, "z0": z0},
        "align_nose": align_n,
        "align_main": align_m,
        "old_nose": old_nose_bb,
        "old_main": old_main_bb,
        "new_nose": new_nose_bb,
        "new_main": new_main_bb,
        "delta_nose_mm": dN,
        "delta_main_mm": dM,
        "imported": [o.name for o in new],
        "scripts": ["section9_gear_fairing.py"],
    }

    if dN["max_mm"] >= 5.0 or dM["max_mm"] >= 5.0:
        log("[STOP] gear AABB delta >= 5 mm")
        result["stopped"] = True
        result["pass"] = False
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        json.dump(result, open(os.path.join(LOG, "section9.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump(result, open(os.path.join(ROOT, "logs", "section9.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return result

    deleted_old = []
    for n in ("REF_前起落架", "REF_主起落架"):
        if delete_object(n):
            deleted_old.append(n)
    result["deleted_old_gear"] = deleted_old
    log(f"[del old] {deleted_old}")

    mat_door = ensure_mat("S9_GearDoor", "#F2F3F5", 0.0, 0.35)
    mat_strut = ensure_mat("S9_GearStrut", "#3A3D42", 0.5, 0.45)
    for ob in new:
        if "舱门" in ob.name:
            assign_mat(ob, mat_door)
        elif "支柱轮" in ob.name:
            assign_mat(ob, mat_strut)
    log("[mats] doors #F2F3F5 / struts #3A3D42")

    tip = tip_y()
    keep = {
        "Fuselage_REF", "REF_机翼_左", "REF_机翼_右",
        "REF_吊挂_左", "REF_吊挂_右",
        "REF_舷窗玻璃", "REF_舱门缝线",
        "REF_前起落架_舱门", "REF_前起落架_支柱轮",
        "REF_主起落架_舱门", "REF_主起落架_支柱轮",
    }
    rows, wing_under, y_lo, y_hi = region_objects(tip)
    result["region"] = {
        "tip": tip, "wing_under": wing_under,
        "y_band": [y_lo, y_hi], "list": rows,
    }
    deleted_92 = []
    kept_92 = []
    for row in rows:
        name = row["name"]
        if name in keep:
            kept_92.append(name)
        else:
            if delete_object(name):
                deleted_92.append(name)
                log(f"[9.2.1 del] {name}")
            else:
                kept_92.append(name)
    result["deleted_9_2_1"] = deleted_92
    result["kept_9_2_1"] = kept_92
    log(f"[9.2.1] listed={len(rows)} deleted={deleted_92} kept={kept_92}")

    coplanar = check_coplanar_wing_faces(tip)
    result["coplanar_wing_faces"] = coplanar

    fus = bpy.data.objects["Fuselage_REF"]
    smooth_info = fuselage_auto_smooth_60(fus)
    result["fuselage_smooth"] = smooth_info

    n_glb = export_glb()
    result["glb"] = GLB
    result["glb_mesh_count"] = n_glb
    result["visible_meshes"] = sorted(
        o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_get()
    )

    rend = render_wing_root(tip)
    result["render"] = rend
    result["pass"] = True
    result["stopped"] = False

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, BAK_DONE)

    json.dump(result, open(os.path.join(LOG, "section9.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(result, open(os.path.join(ROOT, "logs", "section9.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = [
        "# PROGRESS — section9 gear doors + fairing crease",
        "- backup: c919.bak-before-s9.blend -> c919.bak-section9.blend",
        f"- gear AABB nose max_mm={dN['max_mm']:.4f} main max_mm={dM['max_mm']:.4f}",
        f"- deleted old {deleted_old}; 9.2.1 deleted {deleted_92}",
        f"- Fuselage_REF smooth: {smooth_info}",
        f"- glb meshes={n_glb}; render={rend.get('name')}",
        "- script: section9_gear_fairing.py",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== section9 DONE ===")
    return result


if __name__ == "__main__":
    main()

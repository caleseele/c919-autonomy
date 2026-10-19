# -*- coding: utf-8 -*-
"""§8: engine parts replace (AABB-align to existing), materials, nose block, glb.

  blender -b --factory-startup -P scripts/section8_finish.py
"""
from __future__ import annotations

import json
import math
import os
import shutil

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
REFS = os.path.join(ROOT, "refs")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK = os.path.join(OUT, "c919.bak-before-s8.blend")
BAK_SRC = os.path.join(OUT, "c919.bak-before-s8.blend")

os.makedirs(LOG, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section8_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]


def aabb(ob):
    """World AABB from actual vertices (bound_box can be stale after mesh.transform)."""
    vs = mwv(ob)
    if not vs:
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        vs = pts
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


def find_engine_parts_obj():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "发动机" in fn and "分件" in fn:
            return os.path.join(REFS, fn)
    p = os.path.join(REFS, "C919_REF_engine_parts.obj")
    if os.path.isfile(p):
        return p
    raise FileNotFoundError("C919_REF_发动机分件.obj")


def align_group_to_target(obs, target_bb):
    """Per-axis scale about raw center + translate so combined AABB matches target."""
    raw_bb = combine_aabb(obs)
    rc = center_bb(raw_bb)
    tc = center_bb(target_bb)
    rs = size_bb(raw_bb)
    ts = size_bb(target_bb)
    sx = ts.x / rs.x if rs.x > 1e-9 else 1.0
    sy = ts.y / rs.y if rs.y > 1e-9 else 1.0
    sz = ts.z / rs.z if rs.z > 1e-9 else 1.0
    # p' = tc + S*(p - rc)
    S = Matrix.Diagonal((sx, sy, sz, 1.0))
    T = Matrix.Translation(tc - S.to_3x3() @ rc)
    # Actually: tc + S*(p-rc) = S*p + (tc - S*rc)
    M = Matrix.Translation(tc) @ S @ Matrix.Translation(-rc)
    # verify: Translation(tc) @ S @ Translation(-rc) @ p = tc + S*(p-rc) yes
    for ob in obs:
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return {
        "sx": sx, "sy": sy, "sz": sz,
        "raw_bb": raw_bb, "target_bb": target_bb,
        "scale": [sx, sy, sz],
        "rc": list(rc), "tc": list(tc),
    }


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Fuselage_REF"]))


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


def apply_materials_8_2(new_engines):
    mat_fuse = ensure_mat("S8_FuselagePaint", "#F2F3F5", 0.0, 0.35)
    mat_wing = ensure_mat("S8_WingPaint", "#E3E5E8", 0.0, 0.40)
    mat_nacelle = ensure_mat("S8_Nacelle", "#F2F3F5", 0.0, 0.35)
    mat_fan = ensure_mat("S8_FanBlade", "#C8CCD2", 1.0, 0.22)
    mat_lip = ensure_mat("S8_InletLip", "#D9DCE0", 1.0, 0.12)
    mat_spinner = ensure_mat("S8_Spinner", "#2A2C30", 0.8, 0.30)
    mat_fan_case = ensure_mat("S8_FanCase", "#3A3D42", 0.7, 0.45)
    mat_core = ensure_mat("S8_CoreNozzle", "#9EA2A8", 0.9, 0.35)
    mat_plug = ensure_mat("S8_TailCone", "#4A4D52", 0.9, 0.40)

    fus = bpy.data.objects.get("Fuselage_REF")
    if fus:
        assign_mat(fus, mat_fuse)
    for n in ("REF_机翼_左", "REF_机翼_右", "REF_吊挂_左", "REF_吊挂_右", "REF_水平尾翼_含升降舵"):
        ob = bpy.data.objects.get(n)
        if ob:
            assign_mat(ob, mat_wing)

    part_mat = {
        "短舱外罩": mat_nacelle,
        "其他": mat_nacelle,
        "风扇叶片": mat_fan,
        "进气唇口": mat_lip,
        "整流锥": mat_spinner,
        "风扇机匣": mat_fan_case,
        "核心机喷口": mat_core,
        "尾喷锥": mat_plug,
    }
    for ob in new_engines:
        for key, mat in part_mat.items():
            if key in ob.name:
                assign_mat(ob, mat)
                break


def list_nose_belly_candidates(tip):
    fus = bpy.data.objects["Fuselage_REF"]
    st_lo, st_hi = 2.0, 7.0
    y_hi = tip - st_lo
    y_lo = tip - st_hi
    fus_band = [v for v in mwv(fus) if y_lo <= v.y <= y_hi]
    belly_z = min(v.z for v in fus_band) if fus_band else aabb(fus)["zmin"]
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_get():
            continue
        a = aabb(o)
        overlap_y0 = max(a["ymin"], y_lo)
        overlap_y1 = min(a["ymax"], y_hi)
        if overlap_y1 - overlap_y0 < 0.05:
            continue
        cy = 0.5 * (a["ymin"] + a["ymax"])
        st = tip - cy
        near_belly = a["zmax"] <= belly_z + 0.20
        if not near_belly:
            continue
        rows.append({
            "name": o.name,
            "aabb": {k: round(v, 4) for k, v in a.items()},
            "station_center": round(st, 3),
            "belly_z": round(belly_z, 4),
            "zmax": round(a["zmax"], 4),
            "keep_if_gear": "前起落架" in o.name,
        })
    return rows, belly_z, y_lo, y_hi


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
    log(f"[glb] {n} → {GLB}")
    return n


def purge_failed_imports():
    """Remove any leftover §8 engine part objects from prior failed run."""
    kill = []
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        n = o.name
        if n.startswith("REF_发动机_左_") or n.startswith("REF_发动机_右_"):
            kill.append(n)
        if n.startswith("REF_发动机_左.") or n.startswith("REF_发动机_右."):
            # .001 duplicates of whole engines from diag — remove if not exact 左/右
            if n not in ("REF_发动机_左", "REF_发动机_右"):
                kill.append(n)
    for n in kill:
        delete_object(n)
        log(f"[purge] {n}")
    return kill


def main():
    open(os.path.join(LOG, "section8_console.txt"), "w", encoding="utf-8").close()
    log("=== §8 finish (AABB-align) ===")

    # Always start from clean pre-s8 backup if it exists; else current blend
    if os.path.isfile(BAK_SRC):
        # Ensure bak exists as first copy from current if this is first successful path
        # Prefer restoring from bak so failed imports are gone
        src = BAK_SRC
        log(f"[restore] from {src}")
        shutil.copy2(src, BLEND)
    else:
        shutil.copy2(BLEND, BAK)
        log(f"[bak] created {BAK}")

    # If bak was just created this run from already-dirty blend, also purge
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # If bak-before-s8 was from first run (clean), good. If dirty, purge.
    if not os.path.isfile(BAK) or os.path.getmtime(BAK) > os.path.getmtime(BAK_SRC) - 1:
        pass
    # Ensure bak-before-s8 is the clean one: if current open has failed parts, we restored from BAK_SRC
    purged = purge_failed_imports()

    # Re-backup clean state if needed
    if not os.path.isfile(BAK):
        shutil.copy2(BLEND, BAK)

    old_L = bpy.data.objects.get("REF_发动机_左")
    old_R = bpy.data.objects.get("REF_发动机_右")
    if not old_L or not old_R:
        raise RuntimeError("missing REF_发动机_左/右 — restore bak-before-s8")
    old_L_bb = aabb(old_L)
    old_R_bb = aabb(old_R)
    log(f"[old L] {old_L_bb}")
    log(f"[old R] {old_R_bb}")

    path = find_engine_parts_obj()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    log(f"[import] {len(new)} from {path}")
    # Keep import world matrices; aabb() uses mwv so object xforms are included.
    # Group by OBJ name 左/右, then match to scene engines by X-center sign
    named_L = [o for o in new if "_左_" in o.name]
    named_R = [o for o in new if "_右_" in o.name]
    if len(named_L) != 8 or len(named_R) != 8:
        raise RuntimeError(f"parts L/R count {len(named_L)}/{len(named_R)}")

    cL = center_bb(combine_aabb(named_L)).x
    cR = center_bb(combine_aabb(named_R)).x
    oldLc = center_bb(old_L_bb).x
    oldRc = center_bb(old_R_bb).x
    log(f"[centers] namedL={cL:.3f} namedR={cR:.3f} oldL={oldLc:.3f} oldR={oldRc:.3f}")

    # Assign groups so X centers match (OBJ 左 may be scene 右)
    if (cL > 0) == (oldLc > 0):
        grp_for_old_L, grp_for_old_R = named_L, named_R
        mapping = "OBJ左→场景左, OBJ右→场景右"
    else:
        grp_for_old_L, grp_for_old_R = named_R, named_L
        mapping = "OBJ左→场景右, OBJ右→场景左 (sign flip)"
    log(f"[map] {mapping}")

    log(f"[pre-align L size] {size_bb(combine_aabb(grp_for_old_L))[:]}")
    log(f"[pre-align R size] {size_bb(combine_aabb(grp_for_old_R))[:]}")
    log(f"[target L size] {size_bb(old_L_bb)[:]}")
    log(f"[target R size] {size_bb(old_R_bb)[:]}")
    align_L = align_group_to_target(grp_for_old_L, old_L_bb)
    align_R = align_group_to_target(grp_for_old_R, old_R_bb)
    log(f"[align L] scale={align_L['scale']}")
    log(f"[align R] scale={align_R['scale']}")

    # Rename parts to keep 左/右 consistent with SCENE side (old engine names)
    def rename_side(obs, side_char):
        for o in obs:
            # replace _左_ or _右_ with target side
            name = o.name
            if "_左_" in name:
                name = name.replace("_左_", f"_{side_char}_")
            elif "_右_" in name:
                name = name.replace("_右_", f"_{side_char}_")
            if o.name != name:
                o.name = name

    rename_side(grp_for_old_L, "左")
    rename_side(grp_for_old_R, "右")

    new_L = [o for o in new if "_左_" in o.name]
    new_R = [o for o in new if "_右_" in o.name]
    new_L_bb = combine_aabb(new_L)
    new_R_bb = combine_aabb(new_R)
    dL = aabb_deltas(new_L_bb, old_L_bb)
    dR = aabb_deltas(new_R_bb, old_R_bb)
    log(f"[delta L] {dL}")
    log(f"[delta R] {dR}")

    result = {
        "backup": BAK,
        "method": "AABB per-axis align to existing REF_发动机_左/右",
        "mapping": mapping,
        "align_L": {k: align_L[k] for k in ("sx", "sy", "sz", "scale")},
        "align_R": {k: align_R[k] for k in ("sx", "sy", "sz", "scale")},
        "old_L": old_L_bb,
        "old_R": old_R_bb,
        "new_L": new_L_bb,
        "new_R": new_R_bb,
        "delta_L_mm": dL,
        "delta_R_mm": dR,
        "imported": [o.name for o in new],
        "purged_before": purged,
        "scripts": ["section8_finish.py"],
        "viewer_files": ["src/three/viewer.ts"],
    }

    if dL["max_mm"] >= 5.0 or dR["max_mm"] >= 5.0:
        log("[STOP] AABB delta >= 5 mm after align")
        result["stopped"] = True
        result["pass"] = False
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        json.dump(result, open(os.path.join(LOG, "section8.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump(result, open(os.path.join(ROOT, "logs", "section8.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return result

    deleted_engines = []
    for n in ("REF_发动机_左", "REF_发动机_右"):
        if delete_object(n):
            deleted_engines.append(n)
    result["deleted_engines"] = deleted_engines
    result["pass"] = True
    result["stopped"] = False
    log(f"[del] {deleted_engines}")

    apply_materials_8_2(new)
    log("[mats] done")

    tip = tip_y()
    cands, belly_z, y_lo, y_hi = list_nose_belly_candidates(tip)
    result["nose_belly"] = {
        "tip": tip, "belly_z": belly_z,
        "y_band": [y_lo, y_hi], "candidates": cands,
    }
    deleted_8_3 = []
    kept_8_3 = []
    for row in cands:
        name = row["name"]
        if row["keep_if_gear"] or "前起落架" in name:
            kept_8_3.append(name)
            continue
        a = row["aabb"]
        flat = (a["zmax"] - a["zmin"]) < 0.05 and (a["xmax"] - a["xmin"]) > 0.5
        is_junk = ("Dark" in name or "dark" in name.lower() or "Bulkhead" in name
                   or "挡板" in name or name.startswith("CockpitDark"))
        if is_junk or flat:
            if delete_object(name):
                deleted_8_3.append(name)
                log(f"[8.3 del] {name}")
        else:
            kept_8_3.append(name)
            log(f"[8.3 keep] {name}")

    for n in ("CockpitDarkPlane", "CockpitDarkPlane.001"):
        if bpy.data.objects.get(n) and n not in deleted_8_3:
            delete_object(n)
            deleted_8_3.append(n)
            log(f"[8.3 del explicit] {n}")

    result["deleted_8_3"] = deleted_8_3
    result["kept_8_3"] = kept_8_3

    n_glb = export_glb()
    result["glb"] = GLB
    result["glb_mesh_count"] = n_glb
    result["visible_meshes"] = sorted(
        o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_get()
    )
    result["web"] = {
        "changed": ["src/three/viewer.ts"],
        "changes": [
            "added RoomEnvironment PMREM → scene.environment",
            "DirectionalLight key 0xfff4e5 → 0xffffff (intensity 1.55 kept)",
        ],
    }

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, os.path.join(OUT, "c919.bak-section8.blend"))

    json.dump(result, open(os.path.join(LOG, "section8.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(result, open(os.path.join(ROOT, "logs", "section8.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    open(PROGRESS, "w", encoding="utf-8").write("\n".join([
        "# PROGRESS — §8 finish",
        "- backup: c919.bak-before-s8.blend → c919.bak-section8.blend",
        f"- engine parts AABB-aligned; L max_mm={dL['max_mm']:.4f} R max_mm={dR['max_mm']:.4f}",
        f"- deleted {deleted_engines}; 8.3 deleted {deleted_8_3}",
        "- viewer.ts: RoomEnvironment + key light #FFFFFF",
        f"- glb meshes={n_glb}",
        "- script: section8_finish.py",
    ]) + "\n")
    log("=== §8 DONE ===")
    return result


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""§11.2–11.4: fuselage UV transfer + wing/pylon/engine UV replace + materials + export.
§11.5 viewer already done — do not touch.

  blender -b --factory-startup -P scripts/section11_livery_uv.py
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
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK = os.path.join(OUT, "c919.bak-before-s11.blend")
BAK_DONE = os.path.join(OUT, "c919.bak-section11.blend")

SX = 1.0475227637527205
SZ = 1.0104343689231436
INV_SX = 1.0 / SX
INV_SZ = 1.0 / SZ
TX, TY, TZ = 0.0, 15.463823181152343, -4.239782612001511

TOL = 0.01  # m

FUSE_UV_TARGET = (16.784, 0.000, 4.218)  # 站位, |x|, 离地

WING_NAMES = ["REF_机翼_左", "REF_机翼_右", "REF_吊挂_左", "REF_吊挂_右"]
ENGINE_SUFFIXES = [
    "短舱外罩", "进气唇口", "风扇叶片", "风扇机匣",
    "整流锥", "核心机喷口", "尾喷锥", "其他",
]
ENGINE_NAMES = [
    f"REF_发动机_{side}_{s}" for side in ("左", "右") for s in ENGINE_SUFFIXES
]
REPLACE_NAMES = WING_NAMES + ENGINE_NAMES

# §11.4 material params: name -> (hex or None if keep map color, metallic, roughness, keep_map)
MAT_PARAMS = {
    "skin_fuselage": (None, 0.0, 0.35, True),
    "skin_wing_lower": (None, 0.0, 0.40, True),
    "skin_wing_upper": (None, 0.0, 0.40, True),
    "skin_wing": ("#E3E5E8", 0.0, 0.40, False),
    "pylon": ("#E3E5E8", 0.0, 0.40, False),
    "engine_nacelle": (None, 0.0, 0.35, True),
    "engine_nacelle_plain": ("#F2F3F5", 0.0, 0.35, False),
    "engineLip": ("#D9DCE0", 1.0, 0.12, False),
    "fan_metal": ("#C8CCD2", 1.0, 0.22, False),
    "fancase_metal": ("#3A3D42", 0.7, 0.45, False),
    "spinner_metal": (None, 0.8, 0.30, True),
    "core_metal": ("#9EA2A8", 0.9, 0.35, False),
    "plug_metal": ("#4A4D52", 0.9, 0.40, False),
}

os.makedirs(LOG, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section11_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]


def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Fuselage_REF"]))


def mean_center(ob):
    vs = mwv(ob)
    if not vs:
        raise RuntimeError(f"no verts: {ob.name}")
    n = float(len(vs))
    return Vector((
        sum(p.x for p in vs) / n,
        sum(p.y for p in vs) / n,
        sum(p.z for p in vs) / n,
    ))


def metrics(ob, tip, z0):
    c = mean_center(ob)
    return {
        "station": abs(tip - c.y),
        "abs_x": abs(c.x),
        "agl": c.z - z0,
        "mean": [c.x, c.y, c.z],
    }


def apply_mw(ob):
    ob.data.transform(ob.matrix_world)
    ob.data.update()
    ob.matrix_world = Matrix.Identity(4)


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


def delete_object(name: str) -> bool:
    ob = bpy.data.objects.get(name)
    if not ob:
        return False
    me = ob.data if ob.type == "MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)
    return True


def base_name(n: str) -> str:
    if "." in n and n.rsplit(".", 1)[-1].isdigit():
        return n.rsplit(".", 1)[0]
    return n


def hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def find_ref(keywords):
    for fn in os.listdir(REFS):
        if not fn.endswith(".obj"):
            continue
        if all(k in fn for k in keywords):
            return os.path.join(REFS, fn)
    raise FileNotFoundError(f"OBJ with {keywords} in {REFS}")


def xform_objects(objs, z0):
    M = unscale_matrix(z0) @ T_REF_matrix()
    for ob in objs:
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()


def import_obj(path):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    log(f"[import] {len(new)} from {os.path.basename(path)}: {[o.name for o in new]}")
    return new


def center_row(name, tip, z0, ref_st=None, ref_ax=None, ref_ag=None, vs_old=None):
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        return {"name": name, "missing": True, "pass": False}
    m = metrics(ob, tip, z0)
    if vs_old is not None:
        old = bpy.data.objects.get(vs_old)
        if old is None:
            return {"name": name, "missing": False, "pass": False, "error": f"old missing {vs_old}",
                    "station": m["station"], "abs_x": m["abs_x"], "agl": m["agl"]}
        om = metrics(old, tip, z0)
        ds = abs(m["station"] - om["station"])
        dx = abs(m["abs_x"] - om["abs_x"])
        dg = abs(m["agl"] - om["agl"])
        ok = ds < TOL and dx < TOL and dg < TOL
        return {
            "name": name, "vs": vs_old, "missing": False, "pass": ok,
            "station": round(m["station"], 4), "abs_x": round(m["abs_x"], 4),
            "agl": round(m["agl"], 4),
            "old_station": round(om["station"], 4), "old_abs_x": round(om["abs_x"], 4),
            "old_agl": round(om["agl"], 4),
            "d_station": round(ds, 4), "d_abs_x": round(dx, 4), "d_agl": round(dg, 4),
        }
    assert ref_st is not None
    ds = abs(m["station"] - ref_st)
    dx = abs(m["abs_x"] - ref_ax)
    dg = abs(m["agl"] - ref_ag)
    ok = ds < TOL and dx < TOL and dg < TOL
    return {
        "name": name, "missing": False, "pass": ok,
        "station": round(m["station"], 4), "abs_x": round(m["abs_x"], 4),
        "agl": round(m["agl"], 4),
        "ref_station": ref_st, "ref_abs_x": ref_ax, "ref_agl": ref_ag,
        "d_station": round(ds, 4), "d_abs_x": round(dx, 4), "d_agl": round(dg, 4),
    }


def ensure_uv_layer(me, name="UVMap"):
    if name in me.uv_layers:
        me.uv_layers[name].active = True
        return me.uv_layers[name]
    # rename active empty if only one unnamed, else create
    if len(me.uv_layers) == 0:
        ul = me.uv_layers.new(name=name)
    else:
        # keep existing but ensure UVMap exists as target
        if name not in me.uv_layers:
            ul = me.uv_layers.new(name=name)
        else:
            ul = me.uv_layers[name]
    ul.active = True
    return ul


def data_transfer_uv(target, source):
    """Apply Data Transfer: Face Corner UV, Nearest Face Interpolated, UVMap->UVMap."""
    ensure_uv_layer(target.data, "UVMap")
    # Ensure source has UVMap
    src_uv = None
    if source.data.uv_layers:
        if "UVMap" in source.data.uv_layers:
            src_uv = source.data.uv_layers["UVMap"]
        else:
            src_uv = source.data.uv_layers[0]
            if src_uv.name != "UVMap":
                src_uv.name = "UVMap"
        src_uv.active = True
    else:
        raise RuntimeError(f"source {source.name} has no UV layers")

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    mod = target.modifiers.new(name="S11_DataTransfer_UV", type="DATA_TRANSFER")
    mod.object = source
    mod.use_loop_data = True
    mod.data_types_loops = {"UV"}
    mod.loop_mapping = "POLYINTERP_NEAREST"  # UI: Nearest Face Interpolated (Blender 5.x)
    # Prefer named UV layers
    try:
        mod.layers_uv_select_src = "NAME"
        mod.layers_uv_select_dst = "NAME"
    except Exception:
        pass
    try:
        # Blender 4+/5 may expose mix / max distance
        mod.mix_mode = "REPLACE"
    except Exception:
        pass

    bpy.ops.object.modifier_apply(modifier=mod.name)
    log(f"[uv] Data Transfer applied: {source.name} -> {target.name}")


def get_bsdf(mat):
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    if nt is None:
        return None, None
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    return nt, bsdf


def find_image_node_linked_to_base(nt, bsdf):
    if "Base Color" not in bsdf.inputs:
        return None
    for link in bsdf.inputs["Base Color"].links:
        n = link.from_node
        if n.type == "TEX_IMAGE":
            return n
        # follow through optional ColorRamp / etc one hop
        if hasattr(n, "inputs"):
            for inp in n.inputs:
                for l2 in inp.links:
                    if l2.from_node.type == "TEX_IMAGE":
                        return l2.from_node
    return None


def tune_material(mat):
    """Apply §11.4 params by material name (exact or prefix match of known keys)."""
    key = None
    for k in MAT_PARAMS:
        if mat.name == k or mat.name.startswith(k):
            key = k
            break
    if key is None:
        return False
    hex_c, metallic, roughness, keep_map = MAT_PARAMS[key]
    # Rename to exact key if imported with .001
    if mat.name != key and mat.name.startswith(key):
        # only rename if free
        if bpy.data.materials.get(key) is None or bpy.data.materials.get(key) == mat:
            mat.name = key
    nt, bsdf = get_bsdf(mat)
    if bsdf is None:
        return False
    img_node = find_image_node_linked_to_base(nt, bsdf)
    if keep_map:
        # ensure white tint so map shows as-is; keep image link
        if "Base Color" in bsdf.inputs:
            # if no image linked, try to find Image Texture in tree and link
            if img_node is None:
                for n in nt.nodes:
                    if n.type == "TEX_IMAGE" and n.image:
                        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
                        img_node = n
                        break
            # set default to white so map isn't tinted
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    else:
        # solid color: disconnect map if any
        if "Base Color" in bsdf.inputs:
            for link in list(bsdf.inputs["Base Color"].links):
                nt.links.remove(link)
            rgb = hex_rgb(hex_c)
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    if "Metallic" in bsdf.inputs:
        for link in list(bsdf.inputs["Metallic"].links):
            nt.links.remove(link)
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        for link in list(bsdf.inputs["Roughness"].links):
            nt.links.remove(link)
        bsdf.inputs["Roughness"].default_value = roughness
    return True


def assign_all_faces_material(ob, mat):
    me = ob.data
    me.materials.clear()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.material_index = 0


def rename_or_create_mat(ob, new_name, hex_color, metallic, roughness):
    """Rename object's first material to new_name (or create), set params."""
    me = ob.data
    if me.materials and me.materials[0]:
        mat = me.materials[0]
        existing = bpy.data.materials.get(new_name)
        if existing is not None and existing != mat:
            # reassign to existing
            me.materials[0] = existing
            mat = existing
        else:
            mat.name = new_name
    else:
        mat = bpy.data.materials.get(new_name)
        if mat is None:
            mat = bpy.data.materials.new(new_name)
        me.materials.clear()
        me.materials.append(mat)
    nt, bsdf = get_bsdf(mat)
    if bsdf:
        for link in list(bsdf.inputs["Base Color"].links):
            nt.links.remove(link)
        rgb = hex_rgb(hex_color)
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        if "Metallic" in bsdf.inputs:
            for link in list(bsdf.inputs["Metallic"].links):
                nt.links.remove(link)
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            for link in list(bsdf.inputs["Roughness"].links):
                nt.links.remove(link)
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


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


def stop_result(reason, **extra):
    result = {"stopped": True, "pass": False, "reason": reason, **extra}
    for p in (os.path.join(LOG, "section11.json"), os.path.join(ROOT, "logs", "section11.json")):
        json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    lines = [
        "# PROGRESS — section11 livery UV (STOPPED)",
        f"- reason: {reason}",
        f"- stamp: {datetime.now().isoformat(timespec='seconds')}",
        "- script: section11_livery_uv.py",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log(f"[STOP] {reason}")
    return result


def main():
    open(os.path.join(LOG, "section11_console.txt"), "w", encoding="utf-8").close()
    log("=== section11 livery UV ===")
    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    shutil.copy2(BLEND, BAK)
    log(f"[bak] -> {BAK}")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    tip = tip_y()
    main_strut = bpy.data.objects.get("REF_主起落架_支柱轮")
    if main_strut is None:
        raise RuntimeError("missing REF_主起落架_支柱轮 for z0")
    z0 = min(v.z for v in mwv(main_strut))
    log(f"[tip]={tip:.6f} z0={z0:.6f}")

    fuse = bpy.data.objects.get("Fuselage_REF")
    if fuse is None:
        raise RuntimeError("missing Fuselage_REF")

    # --- 11.2 fuselage UV source ---
    fuse_uv_path = find_ref(["机身", "UV"])
    # avoid matching 机翼
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "机身UV" in fn:
            fuse_uv_path = os.path.join(REFS, fn)
            break
    log(f"[path] fuse UV = {fuse_uv_path}")
    new_fuse = import_obj(fuse_uv_path)
    xform_objects(new_fuse, z0)
    # find REF_机身UV源
    uv_src = None
    for ob in new_fuse:
        bn = base_name(ob.name)
        if "机身UV源" in bn or bn == "REF_机身UV源":
            uv_src = ob
            if ob.name != "REF_机身UV源" and bpy.data.objects.get("REF_机身UV源") is None:
                ob.name = "REF_机身UV源"
            break
    if uv_src is None and len(new_fuse) == 1:
        uv_src = new_fuse[0]
        uv_src.name = "REF_机身UV源"
    if uv_src is None:
        return stop_result("REF_机身UV源 not found after import", imported=[o.name for o in new_fuse])

    # delete extras from this import
    for ob in list(new_fuse):
        if ob != uv_src:
            delete_object(ob.name)

    fuse_check = center_row("REF_机身UV源", tip, z0, *FUSE_UV_TARGET)
    log(f"[11.2 check] {fuse_check}")
    if not fuse_check["pass"]:
        return stop_result("REF_机身UV源 center fail", fuse_check=fuse_check, tip=tip, z0=z0)

    # Data Transfer UV
    data_transfer_uv(fuse, uv_src)

    # Assign skin_fuselage from UV source materials (with map)
    skin = bpy.data.materials.get("skin_fuselage")
    if skin is None:
        # take from uv_src
        for slot in uv_src.data.materials:
            if slot and "skin_fuselage" in slot.name:
                skin = slot
                skin.name = "skin_fuselage"
                break
    if skin is None:
        # create and try load image
        skin = bpy.data.materials.new("skin_fuselage")
        nt, bsdf = get_bsdf(skin)
        img_path = os.path.join(REFS, "tex", "c919_livery_fuselage.jpg")
        if os.path.isfile(img_path) and bsdf:
            img = bpy.data.images.load(img_path)
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    tune_material(skin)
    assign_all_faces_material(fuse, skin)
    log(f"[11.2] Fuselage_REF -> skin_fuselage (map={bool(find_image_node_linked_to_base(*get_bsdf(skin)))})")

    delete_object(uv_src.name)
    log("[11.2] deleted REF_机身UV源")

    # --- 11.3 wing/pylon + engine UV replace ---
    wing_path = None
    eng_path = None
    for fn in os.listdir(REFS):
        if not fn.endswith(".obj"):
            continue
        if "机翼" in fn and "吊挂" in fn and "UV" in fn:
            wing_path = os.path.join(REFS, fn)
        if "发动机" in fn and "分件" in fn and "UV" in fn:
            eng_path = os.path.join(REFS, fn)
    if not wing_path:
        raise FileNotFoundError("C919_REF_机翼吊挂UV.obj")
    if not eng_path:
        raise FileNotFoundError("C919_REF_发动机分件UV.obj")
    log(f"[path] wing={wing_path}")
    log(f"[path] eng={eng_path}")

    # verify olds exist
    missing_old = [n for n in REPLACE_NAMES if bpy.data.objects.get(n) is None]
    if missing_old:
        return stop_result("old objects missing before replace", missing_old=missing_old)

    new_wing = import_obj(wing_path)
    xform_objects(new_wing, z0)
    new_eng = import_obj(eng_path)
    xform_objects(new_eng, z0)
    new_all = new_wing + new_eng

    # map base -> new object
    new_by_base = {}
    for ob in new_all:
        bn = base_name(ob.name)
        new_by_base[bn] = ob

    checks = []
    failers = []
    for name in REPLACE_NAMES:
        nob = new_by_base.get(name)
        if nob is None:
            row = {"name": name, "missing": True, "pass": False, "error": "not in import"}
            checks.append(row)
            failers.append(name)
            continue
        row = center_row(nob.name, tip, z0, vs_old=name)
        row["canonical"] = name
        checks.append(row)
        if not row["pass"]:
            failers.append(name)
        log(f"[11.3] {name}: pass={row['pass']} d=({row.get('d_station')},{row.get('d_abs_x')},{row.get('d_agl')})")

    if failers:
        # leave scene as-is for debug; still save json
        result = stop_result(
            "center check fail vs old",
            checks=checks,
            failers=failers,
            tip=tip,
            z0=z0,
        )
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        return result

    # delete olds, rename news
    for name in REPLACE_NAMES:
        delete_object(name)
        log(f"[del old] {name}")
    for name in REPLACE_NAMES:
        nob = new_by_base[name]
        if nob.name != name:
            # ensure free
            if bpy.data.objects.get(name) is not None:
                delete_object(name)
            nob.name = name
        log(f"[rename] -> {nob.name}")

    # --- 11.4 materials ---
    # Tune all known mats present
    for mat in list(bpy.data.materials):
        tune_material(mat)

    # Explicit rename for hstab / rudder
    hstab = bpy.data.objects.get("REF_水平尾翼_含升降舵")
    if hstab:
        rename_or_create_mat(hstab, "skin_hstab", "#E3E5E8", 0.0, 0.40)
        log("[mat] REF_水平尾翼_含升降舵 -> skin_hstab")
    rudder_ob = bpy.data.objects.get("REF_方向舵等")
    if rudder_ob:
        rename_or_create_mat(rudder_ob, "rudder", "#56A73C", 0.0, 0.40)
        log("[mat] REF_方向舵等 -> rudder")

    # Ensure fuselage still skin_fuselage
    if fuse.data.materials and fuse.data.materials[0]:
        if fuse.data.materials[0].name != "skin_fuselage":
            skin2 = bpy.data.materials.get("skin_fuselage")
            if skin2:
                assign_all_faces_material(fuse, skin2)

    # Log material map status
    mat_report = []
    for mname in MAT_PARAMS:
        m = bpy.data.materials.get(mname)
        if m is None:
            mat_report.append({"name": mname, "present": False})
            continue
        nt, bsdf = get_bsdf(m)
        img_n = find_image_node_linked_to_base(nt, bsdf) if bsdf else None
        mat_report.append({
            "name": mname,
            "present": True,
            "has_map": bool(img_n and getattr(img_n, "image", None)),
            "image": img_n.image.filepath if img_n and img_n.image else None,
        })
    log(f"[mats] {mat_report}")

    n_glb = export_glb()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, BAK_DONE)

    # pass table: fuse + replaces (all pass)
    pass_table = [{"name": "REF_机身UV源", "pass": True}] + [
        {"name": c.get("canonical", c["name"]), "pass": True} for c in checks
    ]

    result = {
        "stopped": False,
        "pass": True,
        "backup": BAK,
        "backup_done": BAK_DONE,
        "fuse_check": fuse_check,
        "replace_checks": checks,
        "pass_table": pass_table,
        "materials": mat_report,
        "tip": tip,
        "z0": z0,
        "glb": GLB,
        "glb_mesh_count": n_glb,
        "visible_meshes": sorted(
            o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_get()
        ),
        "scripts": ["section11_livery_uv.py"],
        "files_modified": [
            "public/models/c919.blend",
            "public/models/c919.glb",
            "public/models/c919.bak-before-s11.blend",
            "public/models/c919.bak-section11.blend",
            "PROGRESS.md",
            "scripts/section11_livery_uv.py",
        ],
        "stamp": datetime.now().isoformat(timespec="seconds"),
    }
    for p in (os.path.join(LOG, "section11.json"), os.path.join(ROOT, "logs", "section11.json")):
        json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    lines = [
        "# PROGRESS — section11 livery UV + materials",
        "- backup: c919.bak-before-s11.blend -> c919.bak-section11.blend",
        "- 11.2 Fuselage_REF UV via DataTransfer from REF_机身UV源; skin_fuselage map kept",
        f"- 11.3 replaced {len(REPLACE_NAMES)} wing/pylon/engine UV objs; all center pass tol 0.01m",
        "- 11.4 mats tuned; skin_hstab + rudder renamed",
        "- 11.5 viewer skipped (already done)",
        f"- tip={tip:.4f} z0={z0:.4f}",
        f"- T_REF = T @ S(sx,1,sz) @ R(Z180); then unscale; NO AABB",
        f"- glb meshes={n_glb}",
        "- script: section11_livery_uv.py",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== section11 DONE ===")
    return result


if __name__ == "__main__":
    main()

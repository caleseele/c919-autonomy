# -*- coding: utf-8 -*-
"""§10: engine orientation fix + gear orientation check. Once; report 10.3.

  blender -b --factory-startup -P scripts/section10_engine_orient.py
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
BAK = os.path.join(OUT, "c919.bak-before-s10.blend")
BAK_DONE = os.path.join(OUT, "c919.bak-section10.blend")

SX = 1.0475227637527205
SZ = 1.0104343689231436
INV_SX = 1.0 / SX
INV_SZ = 1.0 / SZ
TX, TY, TZ = 0.0, 15.463823181152343, -4.239782612001511

TOL = 0.01  # m

# (suffix_or_full_key, 站位, |x|, 离地)
# Engine rows: match REF_发动机_{左|右}_<suffix>
ENGINE_SUFFIXES = [
    ("短舱外罩", 14.180, 6.076, 2.130),
    ("进气唇口", 12.136, 6.076, 2.125),
    ("风扇叶片", 12.848, 6.076, 2.140),
    ("风扇机匣", 12.564, 6.076, 2.125),
    ("整流锥", 12.716, 6.076, 2.132),
    ("核心机喷口", 15.858, 6.076, 2.125),
    ("尾喷锥", 17.061, 6.076, 2.125),
    ("其他", 12.586, 6.076, 1.229),
]
GEAR_TARGETS = {
    "REF_前起落架_舱门": (4.222, 0.000, 2.111),
    "REF_前起落架_支柱轮": (5.242, 0.003, 0.793),
    "REF_主起落架_舱门": (17.189, 0.000, 1.676),
    "REF_主起落架_支柱轮": (17.545, 0.001, 1.005),
}

os.makedirs(LOG, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section10_console.txt"), "a", encoding="utf-8") as f:
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
    station = abs(tip - c.y)
    abs_x = abs(c.x)
    agl = c.z - z0
    return {
        "station": station,
        "abs_x": abs_x,
        "agl": agl,
        "mean": [c.x, c.y, c.z],
    }


def target_for(name: str):
    if name in GEAR_TARGETS:
        return GEAR_TARGETS[name]
    for side in ("左", "右"):
        prefix = f"REF_发动机_{side}_"
        if name.startswith(prefix):
            suffix = name[len(prefix):]
            # strip blender .001 etc
            if "." in suffix and suffix.rsplit(".", 1)[-1].isdigit():
                suffix = suffix.rsplit(".", 1)[0]
            for s, st, ax, ag in ENGINE_SUFFIXES:
                if suffix == s:
                    return (st, ax, ag)
    return None


def expected_names():
    names = []
    for side in ("左", "右"):
        for s, *_ in ENGINE_SUFFIXES:
            names.append(f"REF_发动机_{side}_{s}")
    names.extend(GEAR_TARGETS.keys())
    return names


def check_row(name, tip, z0):
    ob = bpy.data.objects.get(name)
    tgt = target_for(name)
    if ob is None or ob.type != "MESH":
        return {
            "name": name,
            "missing": True,
            "pass": False,
            "station": None, "abs_x": None, "agl": None,
            "ref_station": tgt[0] if tgt else None,
            "ref_abs_x": tgt[1] if tgt else None,
            "ref_agl": tgt[2] if tgt else None,
            "d_station": None, "d_abs_x": None, "d_agl": None,
        }
    m = metrics(ob, tip, z0)
    if tgt is None:
        return {
            "name": name, "missing": False, "pass": False,
            "station": m["station"], "abs_x": m["abs_x"], "agl": m["agl"],
            "ref_station": None, "ref_abs_x": None, "ref_agl": None,
            "d_station": None, "d_abs_x": None, "d_agl": None,
            "error": "no target",
        }
    rst, rax, rag = tgt
    ds = abs(m["station"] - rst)
    dx = abs(m["abs_x"] - rax)
    dg = abs(m["agl"] - rag)
    ok = ds < TOL and dx < TOL and dg < TOL
    return {
        "name": name,
        "missing": False,
        "pass": ok,
        "station": round(m["station"], 4),
        "abs_x": round(m["abs_x"], 4),
        "agl": round(m["agl"], 4),
        "ref_station": rst,
        "ref_abs_x": rax,
        "ref_agl": rag,
        "d_station": round(ds, 4),
        "d_abs_x": round(dx, 4),
        "d_agl": round(dg, 4),
        "mean": [round(v, 4) for v in m["mean"]],
    }


def measure_all(tip, z0):
    return [check_row(n, tip, z0) for n in expected_names()]


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


def find_engine_parts_obj():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "发动机" in fn and "分件" in fn:
            return os.path.join(REFS, fn)
    p = os.path.join(REFS, "C919_REF_engine_parts.obj")
    if os.path.isfile(p):
        return p
    raise FileNotFoundError("C919_REF_发动机分件.obj")


def find_gear_parts_obj():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "起落架" in fn and "分件" in fn:
            return os.path.join(REFS, fn)
    raise FileNotFoundError("C919_REF_起落架分件.obj")


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


def engine_mats():
    return {
        "短舱外罩": ensure_mat("S8_Nacelle", "#F2F3F5", 0.0, 0.35),
        "其他": ensure_mat("S8_Nacelle", "#F2F3F5", 0.0, 0.35),
        "风扇叶片": ensure_mat("S8_FanBlade", "#C8CCD2", 1.0, 0.22),
        "进气唇口": ensure_mat("S8_InletLip", "#D9DCE0", 1.0, 0.12),
        "整流锥": ensure_mat("S8_Spinner", "#2A2C30", 0.8, 0.30),
        "风扇机匣": ensure_mat("S8_FanCase", "#3A3D42", 0.7, 0.45),
        "核心机喷口": ensure_mat("S8_CoreNozzle", "#9EA2A8", 0.9, 0.35),
        "尾喷锥": ensure_mat("S8_TailCone", "#4A4D52", 0.9, 0.40),
    }


def assign_engine_mat(ob, mats):
    for key, mat in mats.items():
        if key in ob.name:
            assign_mat(ob, mat)
            return


def assign_gear_mat(ob):
    if "舱门" in ob.name:
        assign_mat(ob, ensure_mat("S9_GearDoor", "#F2F3F5", 0.0, 0.35))
    elif "支柱轮" in ob.name:
        assign_mat(ob, ensure_mat("S9_GearStrut", "#3A3D42", 0.5, 0.45))


def base_name(n: str) -> str:
    if "." in n and n.rsplit(".", 1)[-1].isdigit():
        return n.rsplit(".", 1)[0]
    return n


def import_and_xform(path, keep_names, z0):
    """Import OBJ, apply T_REF then unscale, keep only keep_names, delete rest of import."""
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    log(f"[import] {len(new)} from {os.path.basename(path)}: {[o.name for o in new]}")

    M_ref = T_REF_matrix()
    M_un = unscale_matrix(z0)
    M = M_un @ M_ref
    for ob in new:
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    log("[xform] T_REF (T@S@R(Z180)) then unscale — no AABB")

    kept = []
    for ob in list(new):
        bn = base_name(ob.name)
        if bn in keep_names:
            if ob.name != bn:
                # rename away from .001 if target free
                if bpy.data.objects.get(bn) is None:
                    ob.name = bn
            kept.append(ob)
        else:
            delete_object(ob.name)
    log(f"[keep] {[o.name for o in kept]}")
    return kept


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


def fmt_table(rows):
    lines = []
    for r in rows:
        if r.get("missing"):
            lines.append(f"  {r['name']}: MISSING  是否通过=否")
        else:
            lines.append(
                f"  {r['name']}: 站位={r['station']:.4f} |x|={r['abs_x']:.4f} "
                f"离地={r['agl']:.4f}  Δ=({r['d_station']:.4f},{r['d_abs_x']:.4f},{r['d_agl']:.4f}) "
                f"是否通过={'是' if r['pass'] else '否'}"
            )
    return "\n".join(lines)


def main():
    open(os.path.join(LOG, "section10_console.txt"), "w", encoding="utf-8").close()
    log("=== section10 engine orient + gear check ===")
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
    log(f"[tip]={tip:.6f} z0(main-strut minZ)={z0:.6f} TZ={TZ}")

    before_rows = measure_all(tip, z0)
    log("[BEFORE]\n" + fmt_table(before_rows))
    failers = [r["name"] for r in before_rows if not r["pass"]]
    log(f"[fail] {len(failers)}: {failers}")

    reimported = []
    eng_fail = [n for n in failers if n.startswith("REF_发动机_")]
    gear_fail = [n for n in failers if n in GEAR_TARGETS]

    for n in failers:
        if delete_object(n):
            log(f"[del] {n}")

    emats = engine_mats()

    if eng_fail:
        path = find_engine_parts_obj()
        kept = import_and_xform(path, set(eng_fail), z0)
        for ob in kept:
            assign_engine_mat(ob, emats)
            reimported.append(ob.name)
        # if some failers missing from import, stop
        got = {base_name(o.name) for o in kept}
        missing = [n for n in eng_fail if n not in got]
        if missing:
            log(f"[STOP] engine parts not in OBJ: {missing}")
            result = {
                "stopped": True,
                "reason": "engine parts missing from OBJ",
                "missing": missing,
                "before": before_rows,
                "reimported": reimported,
            }
            json.dump(result, open(os.path.join(LOG, "section10.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            bpy.ops.wm.save_as_mainfile(filepath=BLEND)
            return result

    if gear_fail:
        path = find_gear_parts_obj()
        kept = import_and_xform(path, set(gear_fail), z0)
        for ob in kept:
            assign_gear_mat(ob)
            reimported.append(ob.name)
        got = {base_name(o.name) for o in kept}
        missing = [n for n in gear_fail if n not in got]
        if missing:
            log(f"[STOP] gear parts not in OBJ: {missing}")
            result = {
                "stopped": True,
                "reason": "gear parts missing from OBJ",
                "missing": missing,
                "before": before_rows,
                "reimported": reimported,
            }
            json.dump(result, open(os.path.join(LOG, "section10.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            bpy.ops.wm.save_as_mainfile(filepath=BLEND)
            return result

    # re-measure tip/z0 after (fuselage unchanged; z0 from strut — if strut reimported, remasure)
    tip = tip_y()
    main_strut = bpy.data.objects.get("REF_主起落架_支柱轮")
    z0_after = min(v.z for v in mwv(main_strut)) if main_strut else z0
    # Use same z0 as BEFORE for pass check consistency with table (ground of scene)
    # Table 离地 is relative to main-wheel ground; after correct reimport strut minZ IS ground.
    # Prefer z0_after if strut was reimported, else z0.
    z0_check = z0_after if "REF_主起落架_支柱轮" in reimported else z0
    log(f"[after tip]={tip:.6f} z0_check={z0_check:.6f}")

    after_rows = measure_all(tip, z0_check)
    log("[AFTER]\n" + fmt_table(after_rows))
    still_fail = [r["name"] for r in after_rows if not r["pass"]]

    # One retry if still failing (should not need AABB — report stop)
    if still_fail:
        log(f"[STOP] still failing after reimport (no AABB allowed): {still_fail}")
        n_glb = export_glb()
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        shutil.copy2(BLEND, BAK_DONE)
        result = {
            "stopped": True,
            "reason": "center check still fail after full-chain reimport",
            "still_fail": still_fail,
            "before": before_rows,
            "after": after_rows,
            "reimported": reimported,
            "z0": z0,
            "z0_check": z0_check,
            "tip": tip,
            "glb_mesh_count": n_glb,
            "pass": False,
        }
        json.dump(result, open(os.path.join(LOG, "section10.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump(result, open(os.path.join(ROOT, "logs", "section10.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        lines = [
            "# PROGRESS — section10 engine orient (STOPPED)",
            f"- backup: c919.bak-before-s10.blend",
            f"- reimported: {reimported}",
            f"- still_fail: {still_fail}",
            f"- glb meshes={n_glb}",
            "- script: section10_engine_orient.py",
        ]
        open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
        return result

    n_glb = export_glb()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    shutil.copy2(BLEND, BAK_DONE)

    result = {
        "stopped": False,
        "pass": True,
        "backup": BAK,
        "backup_done": BAK_DONE,
        "before": before_rows,
        "after": after_rows,
        "reimported": reimported,
        "failers_before": failers,
        "z0": z0,
        "z0_check": z0_check,
        "tip": tip,
        "T_REF": {
            "sx": SX, "sy": 1.0, "sz": SZ, "tx": TX, "ty": TY, "tz": TZ,
            "matrix_order": "T @ S(sx,1,sz) @ R(Z180)",
        },
        "unscale": {"inv_sx": INV_SX, "inv_sz": INV_SZ, "z0": z0},
        "glb": GLB,
        "glb_mesh_count": n_glb,
        "visible_meshes": sorted(
            o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_get()
        ),
        "scripts": ["section10_engine_orient.py"],
        "stamp": datetime.now().isoformat(timespec="seconds"),
    }
    json.dump(result, open(os.path.join(LOG, "section10.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(result, open(os.path.join(ROOT, "logs", "section10.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = [
        "# PROGRESS — section10 engine orient + gear check",
        "- backup: c919.bak-before-s10.blend -> c919.bak-section10.blend",
        f"- failers before: {len(failers)}; reimported: {len(reimported)}",
        f"- reimported names: {reimported}",
        f"- all 20 center checks pass (tol 0.01 m)",
        f"- tip={tip:.4f} z0={z0_check:.4f}",
        f"- T_REF = T @ S(sx,1,sz) @ R(Z180); then unscale; NO AABB",
        f"- glb meshes={n_glb}",
        "- script: section10_engine_orient.py",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== section10 DONE ===")
    return result


if __name__ == "__main__":
    main()

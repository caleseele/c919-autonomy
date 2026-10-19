# -*- coding: utf-8 -*-
"""Part1 delete 15 + Part2 import REF nose details + Part3 length PLAN only.

  blender -b --factory-startup -P scripts/ref_detail_pass_A.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "ref-detail")
REFS = os.path.join(ROOT, "refs")
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

DELETE_EXACT = [
    "CockpitPillar_Center", "CockpitPillar_L", "CockpitPillar_R", "CockpitSeals",
    "Wiper_L_Arm", "Wiper_L_Blade", "Wiper_R_Arm", "Wiper_R_Blade",
    "CockpitInterior", "CockpitGlareShield", "CockpitInstrumentPanel",
    "CockpitSeat_L_Base", "CockpitSeat_L_Back", "CockpitSeat_R_Base", "CockpitSeat_R_Back",
]

REF_LEN = 38.84
REF_TIP_TO_WING_LE = 13.18
REF_TIP_TO_NACELLE_LE = 12.27
REF_WING_LE_TO_VT_LE = 18.28
REF_VT_LE_TO_TAIL = 7.38


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "console_A.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    return name


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


def apply_mesh_matrix(obj, M: Matrix):
    mw = obj.matrix_world.copy()
    me = obj.data
    me.transform(mw)
    me.transform(M)
    me.update()
    obj.matrix_world = Matrix.Identity(4)


def shade_smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def ensure_mat(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def find_detail_obj():
    # Prefer exact Chinese name; fallback by size ~545832
    cand = os.path.join(REFS, "C919_REF_机头细节.obj")
    if os.path.isfile(cand):
        return cand
    for fn in os.listdir(REFS):
        if not fn.lower().endswith(".obj"):
            continue
        p = os.path.join(REFS, fn)
        if os.path.getsize(p) == 545832 or "细节" in fn or "detail" in fn.lower():
            return p
    raise FileNotFoundError("C919_REF_机头细节.obj not found in refs/")


def load_xform_chain():
    """Load nose_replace + seam scales/translations from logs if present."""
    xform_path = os.path.join(ROOT, "scripts", "_nose_replace_logs", "xform.json")
    seam_path = os.path.join(ROOT, "scripts", "_nose_seam_logs", "summary.json")
    xform = {}
    seam = {}
    if os.path.isfile(xform_path):
        with open(xform_path, encoding="utf-8") as f:
            xform = json.load(f)
    if os.path.isfile(seam_path):
        with open(seam_path, encoding="utf-8") as f:
            seam = json.load(f)
    return xform, seam


# ---------- Part 1 ----------
def part1_delete(nose):
    deleted = []
    missing = []
    for name in DELETE_EXACT:
        obj = bpy.data.objects.get(name)
        if obj is None:
            missing.append(name)
            log(f"[delete] MISSING {name}")
            continue
        delete_object(obj)
        deleted.append(name)
        log(f"[delete] {name}")
    return deleted, missing


def inspect_spikes(nose, glass):
    """List potential spike faces near lower windshield — DO NOT delete."""
    if nose is None or glass is None:
        return []
    gv = mesh_world_verts(glass)
    g_ymin = min(v.y for v in gv)
    g_ymax = max(v.y for v in gv)
    g_zmin = min(v.z for v in gv)

    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.faces.ensure_lookup_table()
    mw = nose.matrix_world
    suspects = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        # near lower windshield band
        if not (g_ymin - 0.4 <= c.y <= g_ymax + 0.2):
            continue
        if not (g_zmin - 0.6 <= c.z <= g_zmin + 0.35):
            continue
        area = f.calc_area()
        nrm = (mw.to_3x3() @ f.normal).normalized()
        # spike-like: small area, normal pointing oddly down/out, or elongated
        lengths = sorted(e.calc_length() for e in f.edges)
        elong = lengths[-1] / max(lengths[0], 1e-9) if lengths else 1.0
        inward = abs(c.x) < 1.2 and c.z < g_zmin + 0.1
        if area < 0.01 and (elong > 4.0 or (inward and nrm.z < -0.3)):
            suspects.append({
                "face_index": f.index,
                "center": [c.x, c.y, c.z],
                "area": area,
                "elong": elong,
                "normal": [nrm.x, nrm.y, nrm.z],
            })
    bm.free()
    # also check for verts sticking far below glass sill near nose
    nv = mesh_world_verts(nose)
    tip_y = max(v.y for v in nv)
    low_spikes = []
    for i, v in enumerate(nose.data.vertices):
        w = mw @ v.co
        if w.y < g_ymin - 0.2 or w.y > g_ymax + 0.3:
            continue
        if w.z < g_zmin - 0.25 and abs(w.x) < 1.5:
            low_spikes.append({"vert_index": i, "co": [w.x, w.y, w.z]})
    report = {
        "suspect_faces": suspects[:80],
        "suspect_face_count": len(suspects),
        "low_verts_under_sill": low_spikes[:40],
        "low_vert_count": len(low_spikes),
        "note": "NO Nose faces deleted — report only",
    }
    log(f"[spikes] faces={len(suspects)} low_verts={len(low_spikes)}")
    return report


def render_view(path, loc, look, lens=45):
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        ld = bpy.data.lights.new("RefDetailSun", "SUN")
        ld.energy = 4.5
        lo = bpy.data.objects.new("RefDetailSun", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(50), math.radians(15), math.radians(30))
    for o in list(bpy.data.objects):
        if o.name.startswith("RDCam_"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("RDCam")
    cam = bpy.data.objects.new("RDCam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log(f"[render] {path}")
    bpy.data.objects.remove(cam, do_unlink=True)


# ---------- Part 2 ----------
def compute_ref_to_nose_matrix(nose):
    """Build matrix that maps default-imported REF nose space → current Nose.

    Replay: Z-180, scale from replace logs, translate from replace, then seam scale+dy.
    Then refine translation so REF cut/tip match current Nose.
    """
    xform, seam = load_xform_chain()
    sx = float(xform.get("sx", 1.045685))
    sy = float(xform.get("sy", 1.021632))
    sz = float(xform.get("sz", 0.997579))
    # After rot+scale, xform.json dx,dy,dz were applied to place cut
    dx = float(xform.get("dx", 0.0))
    dy = float(xform.get("dy", 15.3458))
    dz = float(xform.get("dz", -4.1641))

    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((sx, sy, sz, 1.0))
    T = Matrix.Translation(Vector((dx, dy, dz)))
    M = T @ S @ R  # apply R first to verts, then S, then T

    # Seam cumulative (applied about aft pivot after first xform)
    seam_scale = seam.get("scale_applied") or {}
    sx2 = float(seam_scale.get("sx", 1.0)) / sx if seam_scale else 1.0
    # seam JSON stores cumulative sx including first? Check: "sx": 0.998292 was the seam-only in console
    # From console: [scale] mode=axis sx=0.998292 — that was the seam pass multiplier only.
    # But summary scale_applied might be cumulative product. Read carefully.
    # summary said: "sx": sx after possibly pass2 multiplying. Initial seam sx=0.998292.
    # We'll use seam multipliers from console-equivalent stored in scale_applied if ~1.0
    raw_sx2 = float(seam_scale.get("sx", 0.998292))
    raw_sz2 = float(seam_scale.get("sz", 0.999876))
    # If scale_applied is cumulative (~1.04), detect:
    if raw_sx2 > 1.01:
        # cumulative — divide out first sx
        sx2 = raw_sx2 / sx
        sz2 = float(seam_scale.get("sz", 1.0)) / sz
    else:
        sx2 = raw_sx2
        sz2 = raw_sz2
    sy2 = 1.0
    dy2 = float(seam_scale.get("dy", -0.0075))
    dx2 = float(seam_scale.get("dx", 0.0))
    dz2 = float(seam_scale.get("dz", 0.0))

    # Approximate pivot: aft of nose after M — use target_cut from xform
    pivot_y = float(xform.get("target_cut_y", 14.835))
    pivot = Vector((0.0, pivot_y, 0.0))
    S2 = (
        Matrix.Translation(pivot)
        @ Matrix.Diagonal((sx2, sy2, sz2, 1.0))
        @ Matrix.Translation(-pivot)
    )
    T2 = Matrix.Translation(Vector((dx2, dy2, dz2)))
    M_full = T2 @ S2 @ M

    log(f"[xform] sx={sx:.6f} sy={sy:.6f} sz={sz:.6f} T=({dx:.4f},{dy:.4f},{dz:.4f})")
    log(f"[seam] sx2={sx2:.6f} sz2={sz2:.6f} d=({dx2:.4f},{dy2:.4f},{dz2:.4f})")
    return M_full, xform, seam


def refine_align_to_nose(objs, nose):
    """After approximate xform, nudge so detail bbox centers with Nose in XZ and Y-overlap."""
    nv = mesh_world_verts(nose)
    n_ymin = min(v.y for v in nv)
    n_ymax = max(v.y for v in nv)
    n_cx = 0.5 * (min(v.x for v in nv) + max(v.x for v in nv))
    n_cz = 0.5 * (min(v.z for v in nv) + max(v.z for v in nv))

    # use largest detail object for alignment sample
    sample = max(objs, key=lambda o: len(o.data.vertices))
    sv = mesh_world_verts(sample)
    s_ymin = min(v.y for v in sv)
    s_ymax = max(v.y for v in sv)
    s_cx = 0.5 * (min(v.x for v in sv) + max(v.x for v in sv))
    s_cz = 0.5 * (min(v.z for v in sv) + max(v.z for v in sv))

    # Prefer matching tip (max Y)
    dy = n_ymax - s_ymax
    dx = n_cx - s_cx
    dz = n_cz - s_cz
    # If tip match moves aft too much, blend with cut match
    dy_cut = n_ymin - s_ymin
    # weighted: tip matters more for details on nose
    dy = 0.85 * dy + 0.15 * dy_cut
    T = Matrix.Translation(Vector((dx, dy, dz)))
    for o in objs:
        apply_mesh_matrix(o, T)
    log(f"[refine] dx={dx:.4f} dy={dy:.4f} dz={dz:.4f} (tip/cut blend)")
    return {"dx": dx, "dy": dy, "dz": dz, "n_ymax": n_ymax, "s_ymax_before": s_ymax}


def part2_import(nose):
    path = find_detail_obj()
    log(f"[import] {path}")
    before = set(bpy.data.objects)
    # Prefer mtl beside file
    bpy.ops.wm.obj_import(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    log(f"[import] objects={[o.name for o in imported]}")

    M, xform, seam = compute_ref_to_nose_matrix(nose)
    for o in imported:
        # bake any import object matrix first
        apply_mesh_matrix(o, M)
        shade_smooth(o)

    refine = refine_align_to_nose(imported, nose)

    # Rename + materials
    mat_map = {
        "窗框": ("REF_WindshieldFrame", hex_rgb("0E0E0E"), 0.4, 0.0),
        "雨刮": ("REF_Wiper", hex_rgb("2A2A2A"), 0.4, 0.5),
        "探头": ("REF_ProbeAntenna", hex_rgb("8E9196"), 0.3, 0.8),
        "天线": ("REF_ProbeAntenna", hex_rgb("8E9196"), 0.3, 0.8),
        "内饰": ("REF_CockpitInterior", hex_rgb("1A1C1F"), 0.8, 0.0),
    }
    named = {}
    for o in imported:
        assigned = False
        for key, (mname, col, rough, metal) in mat_map.items():
            if key in o.name:
                mat = ensure_mat(mname, col, rough, metal)
                o.data.materials.clear()
                o.data.materials.append(mat)
                # stable English-ish names for glTF
                if "窗框" in o.name:
                    o.name = "REF_WindshieldFrame"
                elif "雨刮" in o.name:
                    o.name = "REF_Wipers"
                elif "探头" in o.name or "天线" in o.name:
                    o.name = "REF_ProbesAntennas"
                elif "内饰" in o.name:
                    o.name = "REF_CockpitInterior"
                named[o.name] = mname
                assigned = True
                break
        if not assigned:
            log(f"[import] unmatched name {o.name} — keep as-is, dark mat")
            mat = ensure_mat("REF_DetailMisc", hex_rgb("1A1C1F"), 0.7, 0.0)
            o.data.materials.clear()
            o.data.materials.append(mat)
            named[o.name] = "REF_DetailMisc"

    # Dark plane behind interior if needed
    glass = bpy.data.objects.get("CockpitGlass_REF")
    interior = bpy.data.objects.get("REF_CockpitInterior")
    plane = None
    if glass and interior:
        gv = mesh_world_verts(glass)
        g_ymin = min(v.y for v in gv)
        g_zmin = min(v.z for v in gv)
        g_zmax = max(v.z for v in gv)
        # simple dark plane aft of glass, inside
        bm = bmesh.new()
        # quad in XZ at y = g_ymin - 0.15
        y = g_ymin - 0.12
        xs = [-1.1, 1.1]
        zs = [g_zmin - 0.05, g_zmax + 0.05]
        vs = [
            bm.verts.new((xs[0], y, zs[0])),
            bm.verts.new((xs[1], y, zs[0])),
            bm.verts.new((xs[1], y, zs[1])),
            bm.verts.new((xs[0], y, zs[1])),
        ]
        bm.faces.new(vs)
        me = bpy.data.meshes.new("CockpitDarkPlane")
        bm.to_mesh(me)
        bm.free()
        plane = bpy.data.objects.new("CockpitDarkPlane", me)
        bpy.context.scene.collection.objects.link(plane)
        mat = ensure_mat("CockpitDarkPlaneMat", hex_rgb("0C0D0F"), 0.9, 0.0)
        me.materials.append(mat)
        log("[interior] added CockpitDarkPlane behind glass")

    return {
        "imported": [o.name for o in imported],
        "materials": named,
        "refine": refine,
        "dark_plane": plane.name if plane else None,
        "source": path,
    }


# ---------- Part 3 plan ----------
def measure_segments():
    nose = bpy.data.objects.get("Nose")
    fuse = bpy.data.objects.get("Fuselage")
    tail = bpy.data.objects.get("TailCone")
    vt = bpy.data.objects.get("VerticalTail")
    wing_r = bpy.data.objects.get("Wing_R") or bpy.data.objects.get("Wing_L")
    eng = bpy.data.objects.get("Engine_R") or bpy.data.objects.get("Engine_L")

    tip_y = max(v.y for v in mesh_world_verts(nose)) if nose else None
    # Tailcone tip = aft-most (min Y) of TailCone, else Fuselage
    if tail:
        tail_y = min(v.y for v in mesh_world_verts(tail))
    elif fuse:
        tail_y = min(v.y for v in mesh_world_verts(fuse))
    else:
        tail_y = None

    # Wing root LE ≈ max Y of wing near root (|x| small). Use wing bbox ymax as LE approx at root.
    wing_le_y = None
    if wing_r:
        wv = mesh_world_verts(wing_r)
        # root: smallest |x|
        root = [v for v in wv if abs(v.x) < 2.5]
        if not root:
            root = wv
        wing_le_y = max(v.y for v in root)

    nacelle_le_y = None
    if eng:
        ev = mesh_world_verts(eng)
        nacelle_le_y = max(v.y for v in ev)

    vt_le_y = None
    if vt:
        vv = mesh_world_verts(vt)
        vt_le_y = max(v.y for v in vv)

    L = (tip_y - tail_y) if (tip_y is not None and tail_y is not None) else None

    def seg(a, b):
        if a is None or b is None:
            return None
        return a - b  # tip-relative distances: tip_y - feature_y

    table = {
        "tip_y": tip_y,
        "tailcone_tip_y": tail_y,
        "overall_length_m": L,
        "ref_overall_m": REF_LEN,
        "delta_overall_m": (L - REF_LEN) if L is not None else None,
        "segments": [
            {
                "name": "tip → wing root LE",
                "ours_m": seg(tip_y, wing_le_y),
                "ref_m": REF_TIP_TO_WING_LE,
                "delta_m": (seg(tip_y, wing_le_y) - REF_TIP_TO_WING_LE) if wing_le_y else None,
                "feature_y": wing_le_y,
            },
            {
                "name": "tip → engine nacelle LE",
                "ours_m": seg(tip_y, nacelle_le_y),
                "ref_m": REF_TIP_TO_NACELLE_LE,
                "delta_m": (seg(tip_y, nacelle_le_y) - REF_TIP_TO_NACELLE_LE) if nacelle_le_y else None,
                "feature_y": nacelle_le_y,
            },
            {
                "name": "wing root LE → VT root LE",
                "ours_m": (wing_le_y - vt_le_y) if (wing_le_y and vt_le_y) else None,
                "ref_m": REF_WING_LE_TO_VT_LE,
                "delta_m": ((wing_le_y - vt_le_y) - REF_WING_LE_TO_VT_LE) if (wing_le_y and vt_le_y) else None,
            },
            {
                "name": "VT root LE → tailcone tip",
                "ours_m": (vt_le_y - tail_y) if (vt_le_y and tail_y is not None) else None,
                "ref_m": REF_VT_LE_TO_TAIL,
                "delta_m": ((vt_le_y - tail_y) - REF_VT_LE_TO_TAIL) if (vt_le_y and tail_y is not None) else None,
            },
        ],
    }

    # Identify longest-over segment
    over = [s for s in table["segments"] if s.get("delta_m") is not None]
    over.sort(key=lambda s: -(s["delta_m"] or 0))
    longest = over[0] if over else None

    # Propose cut X from constant-section fuselage
    # Constant section roughly y in [-3, 6] or where doors aren't
    excess = (L - REF_LEN) if L else None
    # Prefer cutting from mid-cabin forward of wing? User said: cut from constant-section cylindrical fuselage;
    # translate everything aft of cut forward by X.
    # Suggest cut Y in constant section, e.g. y=4.0 (between nose join 14.85 and wing ~3)
    # Actually aft of cut moves forward — cut should be in cylindrical part.
    # If overall long by ~1.36m, X≈1.36m.
    propose = {
        "execute": False,
        "excess_m": excess,
        "suggested_cut_length_X_m": excess,
        "suggested_cut_plane_y": 5.0,  # mid constant cabin (doors at ~1.8 and -11; wing root ~3)
        "rationale": (
            "Cut X from constant-section fuselage around y≈5 (between forward door/wing and mid-cabin), "
            "NOT nose, NOT tapering tail, NOT through door islands. "
            "All objects with significant geometry aft of cut_plane translate by +X in Y "
            "(aft fuse remnant, wings, engines, gear, tail, flags, stripes clipped/shifted)."
        ),
        "longest_over_segment": longest,
        "do_not_cut": ["Nose", "CockpitGlass_REF", "doors_islands", "wing_root", "tail_taper"],
    }
    table["shorten_proposal"] = propose
    return table


def write_length_plan(table):
    plan_json = os.path.join(LOG, "length_plan.json")
    with open(plan_json, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2, ensure_ascii=False)
    md = os.path.join(ROOT, "scripts", "REF_LENGTH_SHORTEN_PLAN.zh-Hans.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 全长缩短方案（仅计划，未执行）\n\n")
        f.write(f"- 定义：机鼻尖 → 尾锥尖（APU 排气端），沿 **+Y**\n")
        f.write(f"- 当前全长：**{table.get('overall_length_m'):.4f} m**\n")
        f.write(f"- REF：**{table.get('ref_overall_m')} m**\n")
        f.write(f"- Δ：**{table.get('delta_overall_m'):.4f} m**\n\n")
        f.write("## 分段对比\n\n")
        f.write("| 段 | 本机 (m) | REF (m) | Δ (m) |\n|--|--|--|--|\n")
        for s in table["segments"]:
            f.write(
                f"| {s['name']} | {s.get('ours_m')} | {s.get('ref_m')} | {s.get('delta_m')} |\n"
            )
        p = table["shorten_proposal"]
        f.write("\n## 建议（未执行）\n\n")
        f.write(f"- 超长量 X ≈ **{p.get('suggested_cut_length_X_m'):.4f} m**\n")
        f.write(f"- 建议切面：**y ≈ {p.get('suggested_cut_plane_y')}**（等截面机身段）\n")
        f.write(f"- 最长超差段：`{p.get('longest_over_segment')}`\n")
        f.write(f"- 做法：在切面切开 Fuselage，删掉切面处约 X 厚的圆柱环；"
                f"切面之后的机身/机翼/发动机/起落架/尾翼/涂装整体沿 +Y 平移 X。\n")
        f.write(f"- **禁止**：切机头、切尾锥收缩段、切舱门岛、切机翼根。\n")
        f.write(f"- **execute=false** — 本文件仅为计划。\n")
    log(f"[plan] {md}")
    return md, plan_json


def main():
    open(os.path.join(LOG, "console_A.txt"), "w").close()
    log("=== REF DETAIL PASS A ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    nose = bpy.data.objects.get("Nose")
    glass = bpy.data.objects.get("CockpitGlass_REF")
    if nose is None:
        raise RuntimeError("Nose missing")

    # Part 1
    deleted, missing = part1_delete(nose)
    spikes = inspect_spikes(nose, glass)
    with open(os.path.join(LOG, "spikes_report.json"), "w", encoding="utf-8") as f:
        json.dump(spikes, f, indent=2)

    look = Vector((0.0, 17.8, 0.55))
    render_view(
        os.path.join(PREV, "after_delete_oblique45.png"),
        Vector((8.5, look.y + 8.5, 2.0)),
        look,
        45,
    )

    # Part 2
    imp = part2_import(nose)

    if os.path.isfile(GLB):
        shutil.copy2(GLB, GLB + ".bak-ref-detail-A")
        log("backup .bak-ref-detail-A")
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    size = os.path.getsize(GLB)
    log(f"GLB {size} ({size/1e6:.2f} MB)")

    render_view(os.path.join(PREV, "front.png"), Vector((0, look.y + 13, 0.9)), look, 45)
    render_view(os.path.join(PREV, "oblique45.png"), Vector((8.5, look.y + 8.5, 2.0)), look, 45)

    # Part 3 plan only
    table = measure_segments()
    md, plan_json = write_length_plan(table)

    summary = {
        "deleted": deleted,
        "missing": missing,
        "spikes": spikes,
        "import": imp,
        "glb_bytes": size,
        "length_plan": table,
        "previews": [
            os.path.join(PREV, "after_delete_oblique45.png"),
            os.path.join(PREV, "front.png"),
            os.path.join(PREV, "oblique45.png"),
        ],
    }
    with open(os.path.join(LOG, "summary_A.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "REF_DETAIL_A_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# REF 机头细节 A（删除+导入）\n\n")
        f.write("## 已删除\n")
        for n in deleted:
            f.write(f"- `{n}`\n")
        if missing:
            f.write("\n缺失（本来就不在）：\n")
            for n in missing:
                f.write(f"- `{n}`\n")
        f.write("\n## 尖刺（仅报告，未删 Nose 面）\n")
        f.write(f"- suspect_faces={spikes.get('suspect_face_count')} "
                f"low_verts={spikes.get('low_vert_count')}\n")
        f.write("\n## 导入\n")
        f.write(f"- source: `{imp.get('source')}`\n")
        f.write(f"- objects: {imp.get('imported')}\n")
        f.write(f"- materials: {imp.get('materials')}\n")
        f.write(f"- dark_plane: {imp.get('dark_plane')}\n")
        f.write(f"\n## GLB {size/1e6:.2f} MB · 备份 `.bak-ref-detail-A`\n")
        f.write(f"\n## 全长计划见 `REF_LENGTH_SHORTEN_PLAN.zh-Hans.md`（未执行）\n")
    log(f"notes -> {notes}")
    log("=== DONE A ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise

# -*- coding: utf-8 -*-
"""Replace procedural C919 nose with REF_机头 OBJ (no knife, no boolean join).

Run on PC:
  blender -b -P scripts/nose_replace_ref.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import traceback
from collections import defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "public", "models")
GLB_PATH = os.path.join(OUT_DIR, "c919.glb")
BLEND_PATH = os.path.join(OUT_DIR, "c919.blend")
LOG_DIR = os.path.join(ROOT, "scripts", "_nose_replace_logs")
PREV_DIR = os.path.join(OUT_DIR, "nose-replace")
REF_OBJ = os.path.join(ROOT, "refs", "C919_REF_机头.obj")
REF_W0, REF_H0 = 3.94, 4.13  # cut-section size after default import (user-measured)
OVERLAP = 0.015  # 1.5 cm aft overlap into fuselage

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PREV_DIR, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG_DIR, "console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def clear_log() -> None:
    p = os.path.join(LOG_DIR, "console.txt")
    if os.path.exists(p):
        os.remove(p)


def world_bbox(obj):
    mat = obj.matrix_world
    pts = [mat @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts


def apply_object_transform(obj) -> None:
    mw = obj.matrix_world.copy()
    me = obj.data
    me.transform(mw)
    me.update()
    obj.matrix_world = Matrix.Identity(4)


def shade_smooth(obj) -> None:
    for p in obj.data.polygons:
        p.use_smooth = True
    try:
        obj.data.use_auto_smooth = False
    except Exception:
        pass


def ensure_material_white_paint(name="SkinPaint"):
    mat = bpy.data.materials.get(name)
    if mat is None:
        # try common names from build_c919
        for cand in ("Skin", "FuselageSkin", "WhitePaint", "Paint"):
            if bpy.data.materials.get(cand):
                return bpy.data.materials.get(cand)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.92, 0.93, 0.95, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.42
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.08
    return mat


def make_glass_mat(name="REF_CockpitGlass"):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = (0xDD / 255.0, 0xEE / 255.0, 0xEB / 255.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        for key, val in (
            ("Transmission Weight", 1.0),
            ("Transmission", 1.0),
            ("Alpha", 0.3),
            ("IOR", 1.5),
            ("Roughness", 0.02),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    for attr, val in (
        ("blend_method", "BLEND"),
        ("use_backface_culling", False),
    ):
        try:
            setattr(mat, attr, val)
        except Exception:
            pass
    try:
        mat.shadow_method = "NONE"
    except Exception:
        pass
    # Blender 4+/5 EEVEE next
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    return mat


def make_cabin_mat(name="REF_CabinDark"):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.06, 0.065, 0.07, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def delete_object(obj) -> None:
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)


def hide_object(obj) -> None:
    obj.hide_set(True)
    obj.hide_render = True
    obj.hide_viewport = True


def rebuild_clean_body() -> None:
    """Run build_c919.main to get intact smooth skin (no boolean holes)."""
    import importlib.util

    build_path = os.path.join(ROOT, "scripts", "build_c919.py")
    log(f"[1] rebuild via {build_path}")
    spec = importlib.util.spec_from_file_location("build_c919", build_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    log("[1] build_c919.main done")


def cleanup_failed_and_old_nose() -> dict:
    """Remove / hide old procedural nose glass/frames and failed cut leftovers."""
    kill_exact = {
        "机身_开窗",
        "C919_玻璃",
        "WindowOutline",
        "CockpitFrames",
        "CockpitCabin",
        "GlareShield",
        "WindshieldWipers",
        "WS_L",
        "WS_R",
        "SW_L",
        "SW_R",
        "Nose",
        "PitotProbes",
    }
    kill_prefix = (
        "WindowOutline",
        "风挡",
        "切割",
        "Cutter",
        "cutter",
        "WS_",
        "SW_",
        "Bool_",
        "REF_",
    )
    removed = []
    # delete collections named for cutters
    for col in list(bpy.data.collections):
        if "风挡切割" in col.name or "切割体" in col.name:
            for o in list(col.objects):
                delete_object(o)
                removed.append(o.name if False else col.name)
            bpy.data.collections.remove(col)

    for obj in list(bpy.data.objects):
        n = obj.name
        if n in kill_exact or any(n.startswith(p) for p in kill_prefix):
            removed.append(n)
            delete_object(obj)
            continue
        if "Outline" in n or "切割" in n:
            removed.append(n)
            delete_object(obj)
    log(f"[1] cleaned objects: {removed}")
    return {"removed": removed}


def measure_fuselage() -> dict:
    """Measure constant-section W/H/center and forward axis from Fuselage mesh."""
    fuse = bpy.data.objects.get("Fuselage")
    if fuse is None:
        # fallback: largest mesh by vert count excluding wings
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
        fuse = meshes[0] if meshes else None
    if fuse is None:
        raise RuntimeError("No Fuselage mesh found")

    verts = mesh_world_verts(fuse)
    # Forward = +Y (build_c919 convention); confirm by tip of any remaining tipward verts
    ys = [v.y for v in verts]
    y_min, y_max = min(ys), max(ys)
    forward = "+Y"
    # Sample slices: find plateau of max width near mid body
    bins = defaultdict(list)
    for v in verts:
        key = round(v.y * 2) / 2.0  # 0.5 m bins
        bins[key].append(v)

    slice_stats = []
    for yk in sorted(bins.keys(), reverse=True):
        pts = bins[yk]
        if len(pts) < 8:
            continue
        xs = [p.x for p in pts]
        zs = [p.z for p in pts]
        w = max(xs) - min(xs)
        h = max(zs) - min(zs)
        cx = 0.5 * (max(xs) + min(xs))
        cz = 0.5 * (max(zs) + min(zs))
        slice_stats.append({"y": yk, "W": w, "H": h, "cx": cx, "cz": cz, "n": len(pts)})

    # Mid-body plateau: y in [-4, 8], take median of top-width slices
    mid = [s for s in slice_stats if -4.0 <= s["y"] <= 8.0 and s["W"] > 3.0]
    if not mid:
        mid = [s for s in slice_stats if s["W"] > 3.0]
    mid.sort(key=lambda s: s["W"], reverse=True)
    w_max = mid[0]["W"]
    plateau = [s for s in mid if s["W"] >= w_max * 0.98]
    plateau.sort(key=lambda s: s["y"], reverse=True)
    front = plateau[0]
    cut_y_const_front = front["y"]

    fuse_bb = world_bbox(fuse)
    join_y = fuse_bb[3]  # max Y
    cut_y = join_y

    # CRITICAL: scale to the JOIN section (fuse front ring), not mid-cabin max,
    # so seam ΔW/ΔH stays ≤1 cm.
    join_slices = [s for s in slice_stats if abs(s["y"] - join_y) <= 0.6 and s["n"] >= 8]
    if not join_slices:
        join_slices = [s for s in slice_stats if s["y"] >= join_y - 1.0]
    join_slices.sort(key=lambda s: abs(s["y"] - join_y))
    best = join_slices[0]
    W = best["W"]
    H = best["H"]
    cx = best["cx"]
    cz = best["cz"]

    meas = {
        "forward": forward,
        "fuselage_object": fuse.name,
        "fuse_y_min": y_min,
        "fuse_y_max": y_max,
        "W": W,
        "H": H,
        "cx": cx,
        "cz": cz,
        "constant_front_y_plateau": cut_y_const_front,
        "join_y_fuse_max": join_y,
        "cut_y": cut_y,
        "plateau_n": len(plateau),
        "slice_sample": plateau[:5],
    }
    with open(os.path.join(LOG_DIR, "measure.json"), "w", encoding="utf-8") as f:
        json.dump(meas, f, indent=2, ensure_ascii=False)
    log(
        f"[2] MEASURE forward={forward} W={W:.4f} H={H:.4f} cx={cx:.4f} cz={cz:.4f} "
        f"cut_y={cut_y:.4f} join_y={join_y:.4f} plateau_front={cut_y_const_front:.4f}"
    )
    return meas


def import_ref_nose():
    before = set(bpy.data.objects)
    if not os.path.isfile(REF_OBJ):
        raise FileNotFoundError(REF_OBJ)
    bpy.ops.wm.obj_import(filepath=REF_OBJ)
    imported = [o for o in bpy.data.objects if o not in before]
    log(f"[3] imported: {[o.name for o in imported]}")
    skin = None
    glass = None
    for o in imported:
        n = o.name
        if "蒙皮" in n or "skin" in n.lower():
            skin = o
        elif "玻璃" in n or "glass" in n.lower() or "风挡" in n:
            glass = o
    if skin is None or glass is None:
        # fallback by size
        imported.sort(key=lambda o: len(o.data.vertices) if o.type == "MESH" else 0, reverse=True)
        skin = imported[0]
        glass = imported[1] if len(imported) > 1 else None
    if glass is None:
        raise RuntimeError("REF glass object missing")
    # rename stable
    skin.name = "REF_机头蒙皮"
    glass.name = "REF_风挡玻璃"
    return skin, glass


def transform_ref_pair(skin, glass, meas: dict) -> dict:
    """Rotate to +Y forward, scale to W/H, place cut with overlap."""
    W, H, cx, cz = meas["W"], meas["H"], meas["cx"], meas["cz"]
    cut_y = meas["cut_y"]
    sx = W / REF_W0
    sz = H / REF_H0
    sy = 0.5 * (sx + sz)

    # Apply rotation 180° about Z so -Y nose becomes +Y
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((sx, sy, sz, 1.0))

    info = {"sx": sx, "sy": sy, "sz": sz}

    for obj in (skin, glass):
        # first apply current (import) transform to mesh
        apply_object_transform(obj)
        me = obj.data
        me.transform(R)
        me.transform(S)
        me.update()

    # Measure cut section on skin after rot+scale: aft face is min Y (was +0.5, now -0.5*sy)
    verts = mesh_world_verts(skin)
    # Cut plane ≈ vertices near min Y (aft after flip)
    y_min = min(v.y for v in verts)
    y_max = max(v.y for v in verts)
    # band near aft cut
    band = [v for v in verts if v.y <= y_min + 0.05]
    if len(band) < 4:
        band = [v for v in verts if v.y <= y_min + 0.15]
    bx = [v.x for v in band]
    bz = [v.z for v in band]
    cut_cx = 0.5 * (min(bx) + max(bx))
    cut_cz = 0.5 * (min(bz) + max(bz))
    cut_w = max(bx) - min(bx)
    cut_h = max(bz) - min(bz)

    # Target: cut plane at cut_y - OVERLAP (extends aft into fuselage)
    target_cut_y = cut_y - OVERLAP
    dy = target_cut_y - y_min
    dx = cx - cut_cx
    dz = cz - cut_cz
    T = Vector((dx, dy, dz))
    for obj in (skin, glass):
        me = obj.data
        me.transform(Matrix.Translation(T))
        me.update()

    # verify
    verts2 = mesh_world_verts(skin)
    y_min2 = min(v.y for v in verts2)
    y_max2 = max(v.y for v in verts2)
    band2 = [v for v in verts2 if v.y <= y_min2 + 0.05]
    bx2 = [v.x for v in band2]
    bz2 = [v.z for v in band2]
    info.update(
        {
            "ref_y_min": y_min2,
            "ref_y_max": y_max2,
            "cut_W": max(bx2) - min(bx2),
            "cut_H": max(bz2) - min(bz2),
            "cut_cx": 0.5 * (min(bx2) + max(bx2)),
            "cut_cz": 0.5 * (min(bz2) + max(bz2)),
            "target_cut_y": target_cut_y,
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "pre_cut_W": cut_w,
            "pre_cut_H": cut_h,
        }
    )
    log(
        f"[3] xform sx={sx:.4f} sy={sy:.4f} sz={sz:.4f} "
        f"cutW={info['cut_W']:.4f} cutH={info['cut_H']:.4f} "
        f"y=[{y_min2:.3f},{y_max2:.3f}] target_cut={target_cut_y:.3f}"
    )
    with open(os.path.join(LOG_DIR, "xform.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return info


def duplicate_fuselage(name="Fuselage_Cut") -> bpy.types.Object:
    src = bpy.data.objects.get("Fuselage")
    if src is None:
        raise RuntimeError("Fuselage missing")
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = name
    bpy.context.scene.collection.objects.link(dup)
    hide_object(src)
    src.name = "Fuselage_ORIG"
    return dup


def bisect_remove_nose(fuse: bpy.types.Object, cut_y: float, forward="+Y") -> None:
    """Bisect at cut plane; delete geometry forward of cut (old nose side)."""
    bm = bmesh.new()
    bm.from_mesh(fuse.data)
    bm.verts.ensure_lookup_table()
    # Plane: normal points toward nose (+Y). clear_outer removes positive side.
    plane_co = Vector((0.0, cut_y, 0.0))
    plane_no = Vector((0.0, 1.0, 0.0))  # +Y
    # clear_outer=True removes geom on normal side (y > cut_y) — the nose side
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        dist=1e-5,
        plane_co=plane_co,
        plane_no=plane_no,
        clear_outer=True,
        clear_inner=False,
    )
    # fill the cut hole? user said no bridge — leave open or use grid? 
    # Leaving open is OK; REF overlaps and covers seam visually.
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(fuse.data)
    fuse.data.update()
    bm.free()
    fuse.name = "Fuselage"
    shade_smooth(fuse)
    log(f"[4] bisect at y={cut_y:.4f} clear_outer(+Y) done; verts={len(fuse.data.vertices)}")


def assign_materials(skin, glass) -> None:
    paint = None
    fuse = bpy.data.objects.get("Fuselage")
    if fuse and fuse.data.materials:
        paint = fuse.data.materials[0]
    if paint is None:
        paint = ensure_material_white_paint()
    skin.data.materials.clear()
    skin.data.materials.append(paint)
    shade_smooth(skin)

    gmat = make_glass_mat()
    glass.data.materials.clear()
    glass.data.materials.append(gmat)
    shade_smooth(glass)
    log("[5] materials assigned")


def add_cabin_box(glass, skin) -> bpy.types.Object:
    """Closed dark box strictly behind glass, inset so it cannot poke through panes."""
    gv = mesh_world_verts(glass)
    xs = [v.x for v in gv]
    ys = [v.y for v in gv]
    zs = [v.z for v in gv]
    y_gmin, y_gmax = min(ys), max(ys)
    z_gmin, z_gmax = min(zs), max(zs)
    x_gmin, x_gmax = min(xs), max(xs)
    gcx = 0.5 * (x_gmin + x_gmax)
    gcz = 0.5 * (z_gmin + z_gmax)

    # Stay well inside: half-size from glass span * shrink, and clamp to ~inner nose
    span_x = x_gmax - x_gmin
    span_z = z_gmax - z_gmin
    # Cabin sits aft of the glass belt (lower Y), thin in Y
    # Overlap glass Y span so forward/side panes see dark cabin
    y0 = y_gmin - 0.08
    y1 = y_gmax - 0.05
    cx = gcx
    cz = gcz
    total_w = min(span_x * 0.55, 1.8)
    total_h = min(span_z * 0.75, 0.7)
    hx = total_w * 0.5
    hz = total_h * 0.5
    hy = 0.5 * abs(y1 - y0)
    cy = 0.5 * (y0 + y1)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=list(bm.verts), vec=(hx * 2, hy * 2, hz * 2))
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx, cy, cz))
    me = bpy.data.meshes.new("CockpitCabin_REF")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("CockpitCabin", me)
    bpy.context.scene.collection.objects.link(obj)
    mat = make_cabin_mat()
    me.materials.append(mat)
    shade_smooth(obj)
    log(f"[5] cabin box at ({cx:.2f},{cy:.2f},{cz:.2f}) size=({hx*2:.2f},{hy*2:.2f},{hz*2:.2f})")
    return obj


def hide_helpers() -> None:
    keep_visible_substrings = ()
    for obj in bpy.data.objects:
        n = obj.name
        if n.startswith("REF_") and ("切割" in n or "helper" in n.lower()):
            hide_object(obj)
        if n.endswith("_ORIG") or n.startswith("Empty") or n == "C919":
            # root empty can stay
            if n.endswith("_ORIG"):
                hide_object(obj)


def export_glb() -> int:
    # backup
    if os.path.isfile(GLB_PATH):
        bak = GLB_PATH + ".bak-nose-replace"
        shutil.copy2(GLB_PATH, bak)
        log(f"[6] backup {bak}")
    # only visible
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        obj.select_set(False)
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_visible=True,
        use_selection=False,
        export_apply=True,
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    size = os.path.getsize(GLB_PATH)
    log(f"[6] exported {GLB_PATH} size={size} ({size/1e6:.2f} MB)")
    return size


def setup_camera(location, look_at, name="QA_Cam"):
    cam_data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    direction = Vector(look_at) - Vector(location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 50
    return cam


def render_views(tag: str, look_at: Vector, objs_only=None) -> list:
    """Render front / side / 45 of look_at. If objs_only, hide others temporarily."""
    scene = bpy.context.scene
    # Workbench: reliable in -b, shows shape clearly; glass alpha may look solid
    scene.render.engine = "BLENDER_WORKBENCH"
    try:
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_cavity = True
    except Exception:
        pass

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    # lighting
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        light_data = bpy.data.lights.new("QA_Sun", "SUN")
        light_data.energy = 3.0
        light = bpy.data.objects.new("QA_Sun", light_data)
        bpy.context.scene.collection.objects.link(light)
        light.rotation_euler = (math.radians(45), math.radians(20), math.radians(30))

    hidden = []
    if objs_only is not None:
        allow = set(objs_only)
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            if o not in allow and not o.hide_render:
                hidden.append(o)
                o.hide_render = True
                o.hide_viewport = True

    la = Vector(look_at)
    dist = 12.0
    views = {
        "front": (Vector((0, la.y + dist, la.z + 0.5)), la),
        "side": (Vector((dist, la.y, la.z + 0.3)), la),
        "oblique45": (Vector((dist * 0.7, la.y + dist * 0.7, la.z + 1.0)), la),
    }
    paths = []
    # remove old cams
    for o in list(bpy.data.objects):
        if o.name.startswith("QA_Cam"):
            bpy.data.objects.remove(o, do_unlink=True)

    for vname, (loc, tgt) in views.items():
        cam = setup_camera(loc, tgt, name=f"QA_Cam_{vname}")
        scene.camera = cam
        out = os.path.join(PREV_DIR, f"{tag}_{vname}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        paths.append(out)
        log(f"[QA] wrote {out}")
        bpy.data.objects.remove(cam, do_unlink=True)

    for o in hidden:
        o.hide_render = False
        o.hide_viewport = False
    return paths


def qa_join_gap(skin, fuse) -> dict:
    """Check section mismatch at overlap region."""
    cut_y = min(v.co.y for v in skin.data.vertices)  # approx local; use world
    sv = mesh_world_verts(skin)
    fv = mesh_world_verts(fuse)
    y_cut = min(v.y for v in sv)
    # compare sections near y_cut
    def sect(verts, y0, tol=0.08):
        band = [v for v in verts if abs(v.y - y0) < tol]
        if len(band) < 4:
            return None
        xs = [v.x for v in band]
        zs = [v.z for v in band]
        return {
            "W": max(xs) - min(xs),
            "H": max(zs) - min(zs),
            "cx": 0.5 * (max(xs) + min(xs)),
            "cz": 0.5 * (max(zs) + min(zs)),
            "n": len(band),
        }

    # skin aft band and fuse at same y
    y_ref = y_cut + 0.02
    s = sect(sv, y_ref)
    f = sect(fv, y_ref)
    gap = {}
    if s and f:
        gap = {
            "y": y_ref,
            "dW": abs(s["W"] - f["W"]),
            "dH": abs(s["H"] - f["H"]),
            "dcx": abs(s["cx"] - f["cx"]),
            "dcz": abs(s["cz"] - f["cz"]),
            "skin": s,
            "fuse": f,
        }
        log(
            f"[QA] join gap dW={gap['dW']*100:.2f}cm dH={gap['dH']*100:.2f}cm "
            f"dcx={gap['dcx']*100:.2f}cm dcz={gap['dcz']*100:.2f}cm"
        )
    else:
        log(f"[QA] join gap: insufficient band verts s={s} f={f}")
    with open(os.path.join(LOG_DIR, "join_gap.json"), "w", encoding="utf-8") as f:
        json.dump(gap, f, indent=2)
    return gap


def main():
    clear_log()
    log("=== NOSE REPLACE REF START ===")
    log(f"ROOT={ROOT}")
    log(f"REF_OBJ={REF_OBJ} exists={os.path.isfile(REF_OBJ)}")

    # Step 1: rebuild clean
    rebuild_clean_body()
    cleanup_failed_and_old_nose()

    # Step 2: measure
    meas = measure_fuselage()

    # Step 3: import + transform
    skin, glass = import_ref_nose()
    xinfo = transform_ref_pair(skin, glass, meas)

    # Step 4: bisect fuselage copy (cut at join so REF overlaps aft)
    fuse = duplicate_fuselage()
    # Remove geometry forward of (cut_y - OVERLAP/2) so fuselage doesn't poke through REF
    bisect_y = meas["cut_y"] - OVERLAP * 0.5
    bisect_remove_nose(fuse, bisect_y)

    # Step 5: materials + cabin
    assign_materials(skin, glass)
    cabin = add_cabin_box(glass, skin)

    # Rename for clarity
    skin.name = "Nose"
    glass.name = "CockpitGlass_REF"

    hide_helpers()

    # QA gap
    gap = qa_join_gap(skin, fuse)

    # Renders: result
    tip_y = max(v.co.y for v in skin.data.vertices)
    # world tip
    look = Vector((meas["cx"], tip_y - 2.5, meas["cz"] + 0.8))
    # better from world verts
    sv = mesh_world_verts(skin)
    look = Vector(
        (
            sum(v.x for v in sv) / len(sv),
            sum(v.y for v in sv) / len(sv),
            sum(v.z for v in sv) / len(sv),
        )
    )
    paths_res = render_views("result", look)

    # Renders: REF alone
    paths_ref = render_views("ref_alone", look, objs_only={skin, glass})

    size = export_glb()

    summary = {
        "measure": meas,
        "xform": xinfo,
        "join_gap": gap,
        "glb_bytes": size,
        "glb_mb": size / 1e6,
        "previews": paths_res + paths_ref,
        "objects": [o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_render],
    }
    with open(os.path.join(LOG_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "NOSE_REPLACE_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 机头整体替换（REF OBJ）\n\n")
        f.write(f"- forward: `{meas['forward']}`\n")
        f.write(f"- W={meas['W']:.4f} m  H={meas['H']:.4f} m  cx={meas['cx']:.4f}  cz={meas['cz']:.4f}\n")
        f.write(f"- cut_y={meas['cut_y']:.4f}  overlap={OVERLAP} m\n")
        f.write(f"- scale sx={xinfo['sx']:.4f} sy={xinfo['sy']:.4f} sz={xinfo['sz']:.4f}\n")
        f.write(f"- REF cut W/H after xform: {xinfo.get('cut_W'):.4f} / {xinfo.get('cut_H'):.4f}\n")
        if gap:
            f.write(f"- join ΔW={gap.get('dW',0)*100:.2f} cm  ΔH={gap.get('dH',0)*100:.2f} cm\n")
        f.write(f"- GLB: {size/1e6:.2f} MB\n")
        f.write(f"- previews: `public/models/nose-replace/`\n")
        f.write("\n## 诚实差距\n")
        f.write("- 接缝未桥接/布尔，靠 1.5 cm 重叠遮盖；近距离可能看出双层。\n")
        f.write("- REF 蒙皮拓扑密度高于程序化机身，接缝处细分不同。\n")
        if gap and gap.get("dW", 0) > 0.01:
            f.write(f"- 截面宽度差 {gap['dW']*100:.2f} cm，超过 1 cm 目标。\n")
        if gap and gap.get("dH", 0) > 0.01:
            f.write(f"- 截面高度差 {gap['dH']*100:.2f} cm，超过 1 cm 目标。\n")
    log(f"[done] notes -> {notes}")
    log("=== NOSE REPLACE REF END ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise

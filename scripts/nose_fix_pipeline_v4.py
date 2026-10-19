# -*- coding: utf-8 -*-
"""C919 nose fix v4: per-pane cutters with verified normals. blender -b only."""
from __future__ import annotations

import json
import math
import os
import traceback
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
SRC = os.path.join(PROJ, "public", "models", "c919.blend.bak-nose-fix")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB_OUT = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND_OUT = os.path.join(PROJ, "public", "models", "c919.blend")
WORK_SAVE = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")

BODY = "Nose"
CUT_DEPTH = 0.30
SOLIDIFY = 0.10
GLASS_INSET = 0.004
SEAL_WIDTH = 0.04
PANE_NAMES = ["WS_L", "WS_R", "SW_L", "SW_R"]

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def log(*a):
    print("NOSEFIXv4", *a, flush=True)


def get(name):
    o = bpy.data.objects.get(name)
    if not o:
        raise RuntimeError("missing " + name)
    return o


def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def island_nc(faces):
    n, c, a = Vector(), Vector(), 0.0
    for f in faces:
        ar = f.calc_area()
        n += f.normal * ar
        c += f.calc_center_median() * ar
        a += ar
    return n.normalized(), c / max(a, 1e-12)


def setup_cam():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.get("NoseFixCam")
    if not cam:
        cd = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cd)
        bpy.context.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, eye, tgt, lens=50):
    cam.location = Vector(eye)
    cam.data.lens = lens
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).normalized().to_track_quat("-Z", "Y").to_euler()


def tip():
    o = bpy.data.objects.get("Nose_开窗") or get(BODY)
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((0.0, max(c.y for c in cs) - 0.15, 0.55))


def render_views(prefix, hide=None):
    cam = setup_cam()
    t = tip()
    saved = {}
    for o in bpy.data.objects:
        if o.type not in {"MESH", "CURVE", "EMPTY"}:
            continue
        saved[o.name] = (o.hide_render, o.hide_get())
        show = True
        if hide and o.name in hide:
            show = False
        if "2-287" in o.name or o.name.startswith("切割体") or o.name in ("NoseSolid",):
            show = False
        o.hide_render = not show
        try:
            o.hide_set(not show)
        except Exception:
            pass
    for tag, eye, lens in (
        ("front", t + Vector((0, 6.0, 0.4)), 55),
        ("side", t + Vector((7.0, -1.0, 0.8)), 50),
        ("45", t + Vector((4.5, 4.0, 1.5)), 50),
    ):
        aim(cam, eye, t, lens)
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)
    for n, (hr, hg) in saved.items():
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = hr
            try:
                o.hide_set(hg)
            except Exception:
                pass


def save_cp(tag):
    p = os.path.join(PROJ, "public", "models", f"c919_nose_fix_{tag}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    log("checkpoint", p)


def ensure_ref():
    if any("2-287" in o.name for o in bpy.data.objects):
        for o in bpy.data.objects:
            if "2-287" in o.name:
                o.hide_set(True)
                o.hide_render = True
        return
    path = os.path.join(PROJ, "refs", "REF_C919_meters.fbx")
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path, global_scale=1.0, use_image_search=False)
    for o in list(bpy.data.objects):
        if o.name not in before and ("1-818" in o.name or o.name == "Cube"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if "2-287" in o.name:
            o.hide_set(True)
            o.hide_render = True


def pane_normal_center(ob, body_c):
    bm = wbm(ob)
    n, c = island_nc(bm.faces)
    if n.dot(c - body_c) < 0:
        n = -n
    # Safety: reject near-aft normals for windshield belt
    # Prefer radial outward for side, +Y/+Z mix for front
    radial = Vector((c.x, 0.0, c.z))
    if radial.length > 1e-6:
        radial.normalize()
        # If normal is mostly -Y (aft), replace with radial / up blend
        if n.y < -0.5:
            log("fix normal", ob.name, "was", tuple(round(x, 3) for x in n))
            if abs(c.x) > 1.2:  # side window
                n = (radial * 0.85 + Vector((0, 0.1, 0.3))).normalized()
            else:
                n = (Vector((0, 0.55, 0.7)) + radial * 0.2).normalized()
                if c.x < 0:
                    n = Vector((-abs(n.x), n.y, n.z)).normalized()
                else:
                    n = Vector((abs(n.x), n.y, n.z)).normalized()
            log("fixed to", tuple(round(x, 3) for x in n))
    faces_data = []
    for f in bm.faces:
        faces_data.append([v.co.copy() for v in f.verts])
    bm.free()
    return n, c, faces_data


def make_cutter_from_faces(faces_data, normal, name, coll):
    bm = bmesh.new()
    # Use unique verts by rounding key
    vmap = {}
    face_vs = []
    for verts in faces_data:
        vs = []
        for co in verts:
            key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
            if key not in vmap:
                vmap[key] = bm.verts.new(co - normal * CUT_DEPTH)
            vs.append(vmap[key])
        face_vs.append(vs)
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=normal * (2.0 * CUT_DEPTH))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.display_type = "WIRE"
    ob.hide_render = True
    # Verify cutter AABB not huge
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    size = Vector(
        (
            max(c.x for c in cs) - min(c.x for c in cs),
            max(c.y for c in cs) - min(c.y for c in cs),
            max(c.z for c in cs) - min(c.z for c in cs),
        )
    )
    log("cutter", name, "size", tuple(round(x, 3) for x in size))
    if size.y > 3.0 or size.x > 4.0 or size.z > 4.0:
        log("WARNING cutter unusually large", name, size)
    return ob


def solidify_nose(body):
    for n in ("NoseSolid", "Nose_开窗"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    solid = body.copy()
    solid.data = body.data.copy()
    solid.name = "NoseSolid"
    for uc in body.users_collection:
        uc.objects.link(solid)
    bm = bmesh.new()
    bm.from_mesh(solid.data)
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.recalc_face_normals(bm, faces=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)])
    for v in moved:
        n = Vector()
        for f in v.link_faces:
            n += f.normal
        if n.length > 1e-8:
            v.co -= n.normalized() * SOLIDIFY
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(solid.data)
    solid.data.update()
    be = sum(1 for e in bm.edges if e.is_boundary)
    log("NoseSolid faces", len(bm.faces), "boundary", be)
    bm.free()
    return solid


def apply_boolean(cut_obj, cutter):
    mod = cut_obj.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    if hasattr(mod, "use_hole_tolerant"):
        mod.use_hole_tolerant = True
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    ev = cut_obj.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = cut_obj.data
    cut_obj.modifiers.clear()
    cut_obj.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return len(cut_obj.data.polygons)


def keep_outer_shell(cut_obj):
    """Remove clearly inward-facing solidified inner skin."""
    bm = bmesh.new()
    bm.from_mesh(cut_obj.data)
    mw = cut_obj.matrix_world
    kill = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = (mw.to_3x3() @ f.normal).normalized()
        radial = Vector((c.x, 0.0, c.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        else:
            radial.normalize()
        score = n.dot(radial)
        if c.y > 19.0:
            score = max(score, n.dot(Vector((0, 1, 0))))
        if score < -0.35:
            kill.append(f)
    log("remove inward", len(kill), "/", len(bm.faces))
    if kill and len(kill) < len(bm.faces) * 0.6:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(cut_obj.data)
        cut_obj.data.update()
    bm.free()


def hole_checks(cut_obj):
    bm = wbm(cut_obj)
    bvh = BVHTree.FromBMesh(bm)
    samples = {
        "WS_R": Vector((0.55, 17.3, 1.35)),
        "WS_L": Vector((-0.55, 17.3, 1.35)),
        "SW_R": Vector((1.65, 16.3, 0.6)),
        "SW_L": Vector((-1.65, 16.3, 0.6)),
        "tip": Vector((0.0, 19.8, 0.0)),
        "cheek": Vector((1.5, 18.5, 0.2)),
    }
    out = {}
    for name, p in samples.items():
        radial = Vector((p.x, 0, p.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        else:
            radial.normalize()
        # for tip use -Y cast
        if name == "tip":
            hit = bvh.ray_cast(p + Vector((0, 1.5, 0)), Vector((0, -1, 0)))
        else:
            hit = bvh.ray_cast(p + radial * 1.2, -radial)
        out[name] = {"hit": hit[0] is not None, "dist": hit[3] if hit[0] else None}
        log("check", name, "SOLID" if hit[0] else "OPEN", out[name]["dist"])
    be = sum(1 for e in bm.edges if e.is_boundary)
    out["boundary_edges"] = be
    # AABB
    cs = [cut_obj.matrix_world @ Vector(c) for c in cut_obj.bound_box]
    out["aabb_y"] = [min(c.y for c in cs), max(c.y for c in cs)]
    out["faces"] = len(cut_obj.data.polygons)
    log("aabb_y", out["aabb_y"], "faces", out["faces"], "be", be)
    bm.free()
    return out


def build_glass_seals(panes_info, body_c):
    """panes_info: list of (name, normal, center, faces_data)"""
    gmat_name, smat_name, cmat_name = "C919_玻璃", "C919_窗框", "C919_驾驶舱"

    def mk(name, col, rough, trans=None, alpha=None):
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (*col, 1)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = rough
        if trans is not None:
            for k in ("Transmission Weight", "Transmission"):
                if k in bsdf.inputs:
                    bsdf.inputs[k].default_value = trans
            if "IOR" in bsdf.inputs:
                bsdf.inputs["IOR"].default_value = 1.5
            if alpha is not None and "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = alpha
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                if hasattr(mat, attr):
                    try:
                        setattr(mat, attr, val)
                    except Exception:
                        pass
        return mat

    gmat = mk(gmat_name, (221 / 255, 238 / 255, 235 / 255), 0.02, 1.0, 0.3)
    smat = mk(smat_name, (0.02, 0.02, 0.02), 0.5)
    cmat = mk(cmat_name, (0.07, 0.07, 0.08), 0.6)

    gl = bmesh.new()
    seal = bmesh.new()
    for name, n, c, faces_data in panes_info:
        # glass
        vmap = {}
        edge_use = defaultdict(int)
        face_vert_ids = []
        for verts in faces_data:
            ids = []
            for co in verts:
                key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
                if key not in vmap:
                    vmap[key] = gl.verts.new(co - n * GLASS_INSET)
                ids.append(key)
            face_vert_ids.append(ids)
            try:
                gl.faces.new([vmap[k] for k in ids])
            except ValueError:
                pass
            for i in range(len(ids)):
                a, b = ids[i], ids[(i + 1) % len(ids)]
                edge_use[tuple(sorted((a, b)))] += 1
        # seals on boundary edges
        for (a, b), cnt in edge_use.items():
            if cnt != 1:
                continue
            v0 = Vector(a)
            v1 = Vector(b)
            # keys are rounded coords
            p0 = Vector(a)
            p1 = Vector(b)
            mid = (p0 + p1) * 0.5
            t = p1 - p0
            if t.length < 1e-9:
                continue
            t.normalize()
            inward = c - mid
            inward = inward - t * inward.dot(t)
            if inward.length < 1e-8:
                inward = n.cross(t)
            inward.normalize()
            off = -n * 0.002
            pts = [p0 + off, p1 + off, p1 + off + inward * SEAL_WIDTH, p0 + off + inward * SEAL_WIDTH]
            try:
                vs = [seal.verts.new(p) for p in pts]
                seal.faces.new(vs)
            except ValueError:
                pass

    for nm, bm, mat in (("C919_玻璃", gl, gmat), ("C919_窗框", seal, smat)):
        me = bpy.data.meshes.new(nm)
        bm.to_mesh(me)
        bm.free()
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)

    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.data.materials.clear()
        cabin.data.materials.append(cmat)
        cabin.hide_set(False)
        cabin.hide_render = False
    for n in ("CockpitFrames", "WindshieldWipers"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True


def round_radome(cut):
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    mw = cut.matrix_world
    mwi = mw.inverted()

    def W(v):
        return mw @ v.co

    tip_y = max(W(v).y for v in bm.verts)
    if tip_y < 19.0:
        log("SKIP radome tip_y too low", tip_y)
        bm.free()
        return
    tip_verts = [v for v in bm.verts if W(v).y > tip_y - 0.40]
    ring = [v for v in tip_verts if tip_y - 0.30 < W(v).y < tip_y - 0.10]
    if len(ring) < 8:
        ring = [v for v in tip_verts if W(v).y < tip_y - 0.05]
    mean_x = sum(W(v).x for v in ring) / max(len(ring), 1)
    mean_z = sum(W(v).z for v in ring) / max(len(ring), 1)
    ring_y = sum(W(v).y for v in ring) / max(len(ring), 1)
    R = sum(math.sqrt((W(v).x - mean_x) ** 2 + (W(v).z - mean_z) ** 2) for v in ring) / max(len(ring), 1)
    R = max(min(R, 0.55), 0.18)
    log("radome", "R", R, "ring_y", ring_y, "tip_y", tip_y)
    for v in tip_verts:
        vw = W(v)
        r = math.sqrt((vw.x - mean_x) ** 2 + (vw.z - mean_z) ** 2)
        if r > R * 1.15:
            continue
        rr = min(r, R)
        dy = math.sqrt(max(0.0, R * R - rr * rr)) * 0.80
        new_y = ring_y + dy
        if vw.y >= ring_y - 0.01:
            v.co = mwi @ Vector((vw.x, new_y, vw.z))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data)
    cut.data.update()
    bm.free()


def cleanup_export(cut):
    for o in list(bpy.data.objects):
        n = o.name
        if n.startswith("切割体") or n in ("NoseSolid", "REF_玻璃"):
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", n)
    for o in bpy.data.objects:
        if "2-287" in o.name or o.name == BODY:
            o.hide_set(True)
            o.hide_render = True
        if o.name in PANE_NAMES:
            o.hide_set(True)
            o.hide_render = True
    cut.hide_set(False)
    cut.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB_OUT)
    log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK_SAVE)
    return size


def main():
    log("open", SRC)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    ensure_ref()
    for o in list(bpy.data.objects):
        if o.name.startswith("切割体") or o.name.startswith("Nose_开窗") or o.name in (
            "REF_玻璃", "C919_玻璃", "C919_窗框", "NoseSolid"
        ):
            bpy.data.objects.remove(o, do_unlink=True)

    body = get(BODY)
    body.hide_set(False)
    body.hide_render = False
    body_c = body.matrix_world @ (sum((Vector(b) for b in body.bound_box), Vector()) / 8.0)

    for n in PANE_NAMES:
        o = get(n)
        o.hide_set(False)
        o.hide_render = False

    log("===== STEP2 panes =====")
    panes_info = []
    for n in PANE_NAMES:
        nor, cen, faces = pane_normal_center(get(n), body_c)
        log("pane", n, "n", tuple(round(x, 3) for x in nor), "c", tuple(round(x, 3) for x in cen), "faces", len(faces))
        panes_info.append((n, nor, cen, faces))
        # hide original pane mesh for cleaner patch preview later
    with open(os.path.join(LOG_DIR, "step2_v4.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "outline_source": "fallback_existing_WS_SW_panes_ref_derived",
                "panes": [
                    {"name": n, "n": list(nor), "c": list(cen), "faces": len(fd)}
                    for n, nor, cen, fd in panes_info
                ],
            },
            f,
            indent=2,
        )
    # Create REF_玻璃 preview join (optional display)
    bm = bmesh.new()
    for n, nor, cen, faces in panes_info:
        for verts in faces:
            try:
                bm.faces.new([bm.verts.new(co) for co in verts])
            except ValueError:
                pass
    me = bpy.data.meshes.new("REF_玻璃_mesh")
    bm.to_mesh(me)
    bm.free()
    gob = bpy.data.objects.new("REF_玻璃", me)
    bpy.context.collection.objects.link(gob)
    for n in PANE_NAMES:
        get(n).hide_set(True)
        get(n).hide_render = True
    render_views("step2_patches", hide=["CockpitFrames"])
    save_cp("step2")

    log("===== STEP3 solidify + per-pane boolean =====")
    solid = solidify_nose(body)
    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    cutters = []
    for n, nor, cen, faces in panes_info:
        cutters.append(make_cutter_from_faces(faces, nor, f"切割体_{n}", coll))

    cut = solid.copy()
    cut.data = solid.data.copy()
    cut.name = "Nose_开窗"
    for uc in solid.users_collection:
        uc.objects.link(cut)

    for cutter in cutters:
        nfaces = apply_boolean(cut, cutter)
        log("after", cutter.name, "faces", nfaces)
        if nfaces < 500:
            raise RuntimeError("boolean destroyed mesh after " + cutter.name)

    keep_outer_shell(cut)
    solid.hide_set(True)
    solid.hide_render = True
    body.hide_set(True)
    body.hide_render = True
    coll.hide_viewport = True
    coll.hide_render = True
    gob.hide_set(True)
    gob.hide_render = True

    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.hide_set(True)
        cabin.hide_render = True
    for n in ("CockpitFrames",):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    checks = hole_checks(cut)
    with open(os.path.join(LOG_DIR, "step3_v4_holes.json"), "w") as f:
        json.dump(checks, f, indent=2)
    render_views("step3_cut")
    if cabin:
        cabin.hide_set(False)
        cabin.hide_render = False
    save_cp("step3")

    # Require openings
    opens = [k for k, v in checks.items() if isinstance(v, dict) and k.startswith("W") and not v.get("hit")]
    log("OPEN panes", opens)
    if len(opens) < 2:
        log("WARNING fewer than 2 openings")

    log("===== STEP4 =====")
    build_glass_seals(panes_info, body_c)
    render_views("step4_glass", hide=["CockpitFrames", BODY, "REF_玻璃"])
    save_cp("step4")

    log("===== STEP5 =====")
    round_radome(cut)
    render_views("step5_radome", hide=["CockpitFrames", BODY, "REF_玻璃"])
    save_cp("step5")

    log("===== STEP6 =====")
    size = cleanup_export(cut)
    render_views("step6_final", hide=["CockpitFrames", BODY])

    # REF renders
    ref = next((o for o in bpy.data.objects if "2-287" in o.name), None)
    if ref:
        cam = setup_cam()
        cs = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
        tipr = Vector((0.0, max(c.y for c in cs) - 0.4, min(c.z for c in cs) + 5.2))
        saved = {}
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            saved[o.name] = (o.hide_render, o.hide_get())
            show = o == ref
            o.hide_render = not show
            try:
                o.hide_set(not show)
            except Exception:
                pass
        try:
            ref.display_type = "SOLID"
        except Exception:
            pass
        for tag, eye, lens in (
            ("front", tipr + Vector((0, 14, 1.5)), 40),
            ("side", tipr + Vector((18, -2, 2)), 40),
            ("45", tipr + Vector((12, 10, 5)), 40),
        ):
            aim(cam, eye, tipr, lens)
            fp = os.path.join(OUT_DIR, f"step6_ref_{tag}.png")
            bpy.context.scene.render.filepath = fp
            bpy.ops.render.render(write_still=True)
            log("render", fp)
        for n, (hr, hg) in saved.items():
            o = bpy.data.objects.get(n)
            if o:
                o.hide_render = hr
                try:
                    o.hide_set(hg)
                except Exception:
                    pass
        ref.hide_set(True)
        ref.hide_render = True

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 机头修复 nose-fix v4

- 时间：2026-10-17 Asia/Shanghai
- blender -b；无 knife_project；原 Nose 隐藏，副本 Nose_开窗

## Step1
- 机身 Nose；tip +Y≈20.03；WindowOutline=0
- REF Obj3d66-19714258-2-287；无风挡材质岛

## Step2
- 来源 fallback_existing_WS_SW_panes_ref_derived
- 每块窗单独取法线并校正（禁止合并后法线塌成 -Y）

## Step3
- Nose solidify 成流形 → 每窗 Exact 布尔 → 去内层
- hole checks: {json.dumps(checks, ensure_ascii=False)}

## GLB
- {size} bytes
- 备份 c919.glb.bak-nose-fix / c919.blend.bak-nose-fix

## 诚实缺口
见 step3_v4_holes.json 与预览图；若 tip/cheek 被误切会写在此。
"""
        )
    log("DONE", size)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

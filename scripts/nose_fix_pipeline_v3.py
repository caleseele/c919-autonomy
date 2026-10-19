# -*- coding: utf-8 -*-
"""C919 nose fix v3: solidify shell → boolean → keep outer. blender -b only."""
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

BODY_NAME = "Nose"
CUT_DEPTH = 0.40
SOLIDIFY = 0.12  # inward thickness to make manifold
GLASS_INSET = 0.004
SEAL_WIDTH = 0.04

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def log(*a):
    print("NOSEFIXv3", *a, flush=True)


def get_obj(name):
    o = bpy.data.objects.get(name)
    if not o:
        raise RuntimeError("missing " + name)
    return o


def world_bmesh(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def face_islands_set(faces):
    face_set = set(faces)
    seen, islands = set(), []
    for f in face_set:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb in face_set and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        islands.append(island)
    return islands


def island_nc(island):
    n, c, a = Vector(), Vector(), 0.0
    for f in island:
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


def aim(cam, eye, target, lens=50):
    cam.location = Vector(eye)
    cam.data.lens = lens
    cam.rotation_euler = (Vector(target) - Vector(eye)).normalized().to_track_quat("-Z", "Y").to_euler()


def tip_pt():
    o = bpy.data.objects.get("Nose_开窗") or get_obj(BODY_NAME)
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((0.0, max(c.y for c in cs) - 0.15, 0.55))


def render_views(prefix, hide=None):
    cam = setup_cam()
    tip = tip_pt()
    saved = {}
    for o in bpy.data.objects:
        if o.type not in {"MESH", "CURVE", "EMPTY"}:
            continue
        saved[o.name] = (o.hide_render, o.hide_get())
        show = True
        if hide and o.name in hide:
            show = False
        if "2-287" in o.name or o.name.startswith("切割体") or o.name == "NoseSolid":
            show = False
        o.hide_render = not show
        try:
            o.hide_set(not show)
        except Exception:
            pass
    for tag, eye, lens in (
        ("front", tip + Vector((0, 6.0, 0.4)), 55),
        ("side", tip + Vector((7.0, -1.0, 0.8)), 50),
        ("45", tip + Vector((4.5, 4.0, 1.5)), 50),
    ):
        aim(cam, eye, tip, lens)
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


def build_glass():
    names = ["WS_L", "WS_R", "SW_L", "SW_R"]
    body = get_obj(BODY_NAME)
    body_c = body.matrix_world @ (sum((Vector(b) for b in body.bound_box), Vector()) / 8.0)
    bm = bmesh.new()
    meta = []
    for n in names:
        ob = get_obj(n)
        wbm = world_bmesh(ob)
        for isl in face_islands_set(wbm.faces):
            nor, cen = island_nc(isl)
            if nor.dot(cen - body_c) < 0:
                for f in isl:
                    f.normal_flip()
                nor, cen = island_nc(isl)
            vmap = {}
            for f in isl:
                vs = []
                for v in f.verts:
                    if v not in vmap:
                        vmap[v] = bm.verts.new(v.co.copy())
                    vs.append(vmap[v])
                try:
                    bm.faces.new(vs)
                except ValueError:
                    pass
            meta.append({"name": n, "faces": len(isl), "n": list(nor), "c": list(cen)})
        wbm.free()
        ob.hide_set(True)
        ob.hide_render = True
    for f in bm.faces:
        if f.normal.dot(f.calc_center_median() - body_c) < 0:
            f.normal_flip()
    me = bpy.data.meshes.new("REF_玻璃_mesh")
    bm.to_mesh(me)
    bm.free()
    old = bpy.data.objects.get("REF_玻璃")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    gob = bpy.data.objects.new("REF_玻璃", me)
    bpy.context.collection.objects.link(gob)
    with open(os.path.join(LOG_DIR, "step2_v3.json"), "w", encoding="utf-8") as f:
        json.dump({"outline_source": "fallback_existing_WS_SW_panes_ref_derived", "panes": meta}, f, indent=2)
    log("glass", len(me.polygons), meta)
    return gob, body_c


def make_manifold_nose(body):
    """Duplicate Nose and solidify inward so boolean works on open shell."""
    # Remove old
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
    # Extrude all faces inward (-normal) to create thickness
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    # move along local -normal of original — use individual vert normals
    for v in moved:
        v.normal_update() if hasattr(v, "normal_update") else None
    bmesh.ops.recalc_face_normals(bm, faces=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)])
    # translate extruded verts along average of linked face normals inward
    for v in moved:
        n = Vector()
        for f in v.link_faces:
            n += f.normal
        if n.length > 1e-8:
            n.normalize()
            v.co -= n * SOLIDIFY
    # Close aft open rim if still open: optional
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(solid.data)
    solid.data.update()
    bm.free()

    # Check manifold-ish
    bm2 = bmesh.new()
    bm2.from_mesh(solid.data)
    be = sum(1 for e in bm2.edges if e.is_boundary)
    log("NoseSolid faces", len(bm2.faces), "boundary_edges", be)
    bm2.free()
    return solid


def split_panes(gbm, body_c):
    buckets = {"WS_L": [], "WS_R": [], "SW_L": [], "SW_R": []}
    for f in gbm.faces:
        c = f.calc_center_median()
        if c.y >= 16.85:
            key = "WS_R" if c.x >= 0 else "WS_L"
        else:
            key = "SW_R" if c.x >= 0 else "SW_L"
        buckets[key].append(f)
    out = []
    for k, faces in buckets.items():
        if not faces:
            continue
        n, c = island_nc(faces)
        if n.dot(c - body_c) < 0:
            n = -n
        out.append((k, faces, n, c))
        log("pane", k, len(faces), tuple(round(x, 3) for x in n), tuple(round(x, 3) for x in c))
    return out


def make_cutter(faces, normal, name, coll):
    bm = bmesh.new()
    vmap = {}
    for f in faces:
        vs = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm.verts.new(v.co - normal * CUT_DEPTH)
            vs.append(vmap[v])
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
    return ob


def boolean_cut(solid, glass, body_c):
    gbm = world_bmesh(glass)
    islands = split_panes(gbm, body_c)

    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    for k, faces, n, c in islands:
        make_cutter(faces, n, f"切割体_{k}", coll)

    # Boolean on solid copy → Nose_开窗
    cut = solid.copy()
    cut.data = solid.data.copy()
    cut.name = "Nose_开窗"
    for uc in solid.users_collection:
        uc.objects.link(cut)

    # Apply cutters one-by-one for reliability
    for o in list(coll.objects):
        mod = cut.modifiers.new("cut_" + o.name, "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        if hasattr(mod, "use_hole_tolerant"):
            mod.use_hole_tolerant = True
        mod.object = o
        dg = bpy.context.evaluated_depsgraph_get()
        ev = cut.evaluated_get(dg)
        baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        old = cut.data
        cut.modifiers.clear()
        cut.data = baked
        if old.users == 0:
            bpy.data.meshes.remove(old)
        log("after", o.name, "faces", len(cut.data.polygons))

    # Keep only outer shell: delete faces whose center is clearly inside (toward body_c more than half solidify)
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    bm.normal_update()
    # World transform
    mw = cut.matrix_world
    kill = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = (mw.to_3x3() @ f.normal).normalized()
        # inner faces point toward axis / inward
        radial = Vector((c.x, 0.0, c.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        radial.normalize()
        # outer faces have normal · radial > 0 (approx for cylindrical)
        # also tip faces have n·+Y > 0
        outward_score = n.dot(radial)
        if c.y > 18.5:
            outward_score = max(outward_score, n.dot(Vector((0, 1, 0))))
        # faces deep inside: center closer to axis than skin
        r = math.sqrt(c.x * c.x + c.z * c.z)
        # Heuristic: if normal points inward, delete
        if outward_score < -0.15:
            kill.append(f)
    log("delete inward faces", len(kill), "of", len(bm.faces))
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(cut.data)
    cut.data.update()
    bm.free()

    solid.hide_set(True)
    solid.hide_render = True
    get_obj(BODY_NAME).hide_set(True)
    get_obj(BODY_NAME).hide_render = True
    coll.hide_viewport = True
    coll.hide_render = True
    gbm.free()

    # Verify holes
    wbm = world_bmesh(cut)
    from mathutils.bvhtree import BVHTree as BVH

    bvh = BVH.FromBMesh(wbm)
    samples = {
        "WS_R": Vector((0.55, 17.3, 1.35)),
        "WS_L": Vector((-0.55, 17.3, 1.35)),
        "SW_R": Vector((1.65, 16.3, 0.6)),
        "SW_L": Vector((-1.65, 16.3, 0.6)),
    }
    hits = {}
    for name, p in samples.items():
        radial = Vector((p.x, 0, p.z))
        radial.normalize()
        hit = bvh.ray_cast(p + radial * 1.0, -radial)
        hits[name] = hit[0] is not None
        log("hole_check", name, "still_solid" if hit[0] else "OPEN", hit[3] if hit[0] else None)
    be = sum(1 for e in wbm.edges if e.is_boundary)
    log("boundary_edges", be)
    wbm.free()
    with open(os.path.join(LOG_DIR, "step3_v3_holes.json"), "w") as f:
        json.dump({"hits_still_solid": hits, "boundary_edges": be}, f, indent=2)
    return cut, islands


def mats():
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
                    break
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

    return (
        mk("C919_玻璃", (221 / 255, 238 / 255, 235 / 255), 0.02, 1.0, 0.3),
        mk("C919_窗框", (0.02, 0.02, 0.02), 0.5),
        mk("C919_驾驶舱", (0.07, 0.07, 0.08), 0.6),
    )


def step4(islands, body_c):
    gmat, smat, cmat = mats()
    # Need live faces — rebuild from REF_玻璃
    glass = get_obj("REF_玻璃")
    gbm = world_bmesh(glass)
    islands = split_panes(gbm, body_c)

    gl = bmesh.new()
    for k, faces, n, c in islands:
        if n.dot(c - body_c) < 0:
            n = -n
        vmap = {}
        for f in faces:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = gl.verts.new(v.co - n * GLASS_INSET)
                vs.append(vmap[v])
            try:
                gl.faces.new(vs)
            except ValueError:
                pass
    me = bpy.data.meshes.new("C919_玻璃")
    gl.to_mesh(me)
    gl.free()
    old = bpy.data.objects.get("C919_玻璃")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    gob = bpy.data.objects.new("C919_玻璃", me)
    bpy.context.collection.objects.link(gob)
    gob.data.materials.append(gmat)

    seal = bmesh.new()
    for k, faces, n, c in islands:
        if n.dot(c - body_c) < 0:
            n = -n
        ec = defaultdict(int)
        for f in faces:
            for e in f.edges:
                ec[e] += 1
        for e, cnt in ec.items():
            if cnt != 1:
                continue
            v0, v1 = e.verts[0].co, e.verts[1].co
            mid = (v0 + v1) * 0.5
            t = (v1 - v0)
            if t.length < 1e-9:
                continue
            t.normalize()
            inward = c - mid
            inward = inward - t * inward.dot(t)
            if inward.length < 1e-8:
                inward = n.cross(t)
            inward.normalize()
            off = -n * 0.002
            pts = [v0 + off, v1 + off, v1 + off + inward * SEAL_WIDTH, v0 + off + inward * SEAL_WIDTH]
            try:
                vs = [seal.verts.new(p) for p in pts]
                seal.faces.new(vs)
            except ValueError:
                pass
    sme = bpy.data.meshes.new("C919_窗框")
    seal.to_mesh(sme)
    seal.free()
    old = bpy.data.objects.get("C919_窗框")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    sob = bpy.data.objects.new("C919_窗框", sme)
    bpy.context.collection.objects.link(sob)
    sob.data.materials.append(smat)

    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.data.materials.clear()
        cabin.data.materials.append(cmat)
        cabin.hide_set(False)
        cabin.hide_render = False
    for n in ("CockpitFrames", "WindshieldWipers", "REF_玻璃"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True
    gbm.free()
    return gob


def round_radome(cut):
    """Gentler radome: move tip verts on sphere, avoid spike."""
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    mw = cut.matrix_world
    mwi = mw.inverted()

    def W(v):
        return mw @ v.co

    tip_y = max(W(v).y for v in bm.verts)
    # Find ring at tip_y - 0.25
    ring_y_target = tip_y - 0.22
    # Collect verts near tip
    tip_verts = [v for v in bm.verts if W(v).y > tip_y - 0.45]
    if not tip_verts:
        bm.free()
        return
    # Use verts around tip_y - 0.15..0.30 as ring reference
    ring = [v for v in tip_verts if tip_y - 0.32 < W(v).y < tip_y - 0.08]
    if len(ring) < 8:
        ring = [v for v in tip_verts if W(v).y < tip_y - 0.05]
    mean_x = sum(W(v).x for v in ring) / max(len(ring), 1)
    mean_z = sum(W(v).z for v in ring) / max(len(ring), 1)
    ring_y = sum(W(v).y for v in ring) / max(len(ring), 1)
    R = sum(math.sqrt((W(v).x - mean_x) ** 2 + (W(v).z - mean_z) ** 2) for v in ring) / max(len(ring), 1)
    R = max(R, 0.15)
    log("radome soft R", R, "ring_y", ring_y, "tip_y", tip_y)

    for v in tip_verts:
        vw = W(v)
        r = math.sqrt((vw.x - mean_x) ** 2 + (vw.z - mean_z) ** 2)
        if r > R * 1.2:
            continue
        # Map y to hemisphere: at r=0, y=ring_y+R*0.85; at r=R, y=ring_y
        rr = min(r, R)
        sphere_dy = math.sqrt(max(0.0, R * R - rr * rr)) * 0.85
        new_y = ring_y + sphere_dy
        # Only push forward verts that were flat tip (high y, low r) or blend
        if vw.y > ring_y - 0.02:
            blend = 1.0
        else:
            blend = 0.5
        target = Vector((vw.x, vw.y * (1 - blend) + new_y * blend, vw.z))
        v.co = mwi @ target

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data)
    cut.data.update()
    bm.free()


def cleanup_export(cut):
    to_del = []
    for o in bpy.data.objects:
        n = o.name
        if n.startswith("切割体") or n in ("REF_玻璃", "NoseSolid") or n.startswith("WS_Patch"):
            to_del.append(n)
    for n in to_del:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", n)
    for o in bpy.data.objects:
        if "2-287" in o.name or o.name == "Nose":
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

    nose = get_obj(BODY_NAME)
    nose.hide_set(False)
    nose.hide_render = False
    for n in ("WS_L", "WS_R", "SW_L", "SW_R"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(False)
            o.hide_render = False

    log("===== STEP2 =====")
    glass, body_c = build_glass()
    render_views("step2_patches", hide=["CockpitFrames"])
    save_cp("step2")

    log("===== STEP3 solidify+boolean =====")
    solid = make_manifold_nose(nose)
    cut, islands = boolean_cut(solid, glass, body_c)
    glass.hide_set(True)
    glass.hide_render = True
    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.hide_set(True)
        cabin.hide_render = True
    for n in ("CockpitFrames", "C919_玻璃"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True
    render_views("step3_cut")
    if cabin:
        cabin.hide_set(False)
        cabin.hide_render = False
    save_cp("step3")

    log("===== STEP4 =====")
    step4(islands, body_c)
    render_views("step4_glass", hide=["CockpitFrames", "Nose", "REF_玻璃"])
    save_cp("step4")

    log("===== STEP5 =====")
    round_radome(cut)
    render_views("step5_radome", hide=["CockpitFrames", "Nose", "REF_玻璃"])
    save_cp("step5")

    log("===== STEP6 =====")
    size = cleanup_export(cut)
    render_views("step6_final", hide=["CockpitFrames", "Nose"])

    # REF compares
    ref = next((o for o in bpy.data.objects if "2-287" in o.name), None)
    if ref:
        cam = setup_cam()
        cs = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
        tip = Vector((0.0, max(c.y for c in cs) - 0.4, min(c.z for c in cs) + 5.2))
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
            ("front", tip + Vector((0, 14, 1.5)), 40),
            ("side", tip + Vector((18, -2, 2)), 40),
            ("45", tip + Vector((12, 10, 5)), 40),
        ):
            aim(cam, eye, tip, lens)
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
            f"""# C919 机头修复（nose-fix v3）

- 时间：2026-10-17 Asia/Shanghai
- blender -b；无 knife_project；原 Nose 隐藏

## Step1
- 机身：`Nose`；tip +Y≈20.03
- WindowOutline：0
- REF：`Obj3d66-19714258-2-287`；无风挡专用材质岛

## Step2
- 来源：`fallback_existing_WS_SW_panes_ref_derived`（WS_L/R SW_L/R）
- （a）（b）均不可直接用

## Step3
- **关键**：Nose 为开口壳，直接 Exact 布尔无效
- 做法：先向内 solidify {SOLIDIFY}m → 逐窗 Exact 布尔 → 删内层
- 见 `step3_v3_holes.json`（OPEN=穿孔成功）

## GLB
- {size} bytes（目标 <<2.5MB）
- 备份：`c919.glb.bak-nose-fix`

## 预览
`public/models/nose-fix/step*.png`
"""
        )
    log("DONE", size)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

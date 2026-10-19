# -*- coding: utf-8 -*-
"""Focused: solidify Nose + bmesh boolean with per-pane prisms. Verify OPEN holes."""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
SRC = os.path.join(PROJ, "public", "models", "c919.blend.bak-nose-fix")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")

CUT_DEPTH = 0.45
SOLIDIFY = 0.12
PANE_NAMES = ["WS_L", "WS_R", "SW_L", "SW_R"]


def log(*a):
    print("BMCUT", *a, flush=True)


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


def pane_info(ob, body_c):
    bm = wbm(ob)
    n, c = island_nc(bm.faces)
    if n.dot(c - body_c) < 0:
        n = -n
    if n.y < -0.4:
        radial = Vector((c.x, 0, c.z))
        radial.normalize() if radial.length > 1e-6 else None
        if abs(c.x) > 1.2:
            n = (radial * 0.9 + Vector((0, 0.15, 0.25))).normalized()
        else:
            n = Vector((math.copysign(0.35, c.x), 0.5, 0.75)).normalized()
    faces = [[v.co.copy() for v in f.verts] for f in bm.faces]
    bm.free()
    return n, c, faces


def prism_bmesh(faces, normal):
    bm = bmesh.new()
    vmap = {}
    for verts in faces:
        vs = []
        for co in verts:
            key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
            if key not in vmap:
                vmap[key] = bm.verts.new(co - normal * CUT_DEPTH)
            vs.append(vmap[key])
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=normal * (2.0 * CUT_DEPTH))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Ensure manifold-ish: remove doubles
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    return bm


def solidify_to_bmesh(body):
    bm = bmesh.new()
    bm.from_mesh(body.data)
    # apply world
    bm.transform(body.matrix_world)
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
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    log("solid faces", len(bm.faces), "boundary", sum(1 for e in bm.edges if e.is_boundary))
    return bm


def bvh_overlap_test(bm_a, bm_b):
    # crude: any vert of B inside AABB of A and near surface
    cs = [v.co for v in bm_a.verts]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    inside = 0
    for v in bm_b.verts:
        p = v.co
        if mn.x <= p.x <= mx.x and mn.y <= p.y <= mx.y and mn.z <= p.z <= mx.z:
            inside += 1
    return inside, mn, mx


def hole_check(bm):
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
        if name == "tip":
            hit = bvh.ray_cast(p + Vector((0, 1.5, 0)), Vector((0, -1, 0)))
        else:
            radial = Vector((p.x, 0, p.z))
            radial.normalize()
            hit = bvh.ray_cast(p + radial * 1.2, -radial)
        out[name] = hit[0] is not None
        log("check", name, "SOLID" if hit[0] else "OPEN")
    out["faces"] = len(bm.faces)
    out["boundary"] = sum(1 for e in bm.edges if e.is_boundary)
    ys = [v.co.y for v in bm.verts]
    out["y"] = [min(ys), max(ys)]
    return out


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    cam = bpy.data.objects.get("NoseFixCam")
    if not cam:
        cd = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cd)
        bpy.context.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render_nose(prefix, cut_obj):
    cam = setup_render()
    tip = Vector((0, 19.9, 0.55))
    # show only cut + fuselage + wings etc but hide original nose
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        hide = o.name in ("Nose", "NoseSolid") or "2-287" in o.name or o.name.startswith("切割")
        if o.name.startswith("WS_") or o.name.startswith("SW_"):
            hide = True
        o.hide_render = hide
        try:
            o.hide_set(hide)
        except Exception:
            pass
    cut_obj.hide_render = False
    try:
        cut_obj.hide_set(False)
    except Exception:
        pass
    for tag, eye, lens in (
        ("front", tip + Vector((0, 6, 0.4)), 55),
        ("side", tip + Vector((7, -1, 0.8)), 50),
        ("45", tip + Vector((4.5, 4, 1.5)), 50),
    ):
        cam.location = eye
        cam.data.lens = lens
        cam.rotation_euler = (tip - eye).normalized().to_track_quat("-Z", "Y").to_euler()
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    # cleanup
    for o in list(bpy.data.objects):
        if o.name.startswith("Nose_开窗") or o.name in ("NoseSolid", "C919_玻璃", "C919_窗框", "REF_玻璃"):
            bpy.data.objects.remove(o, do_unlink=True)

    body = bpy.data.objects["Nose"]
    body_c = body.matrix_world @ (sum((Vector(b) for b in body.bound_box), Vector()) / 8.0)

    panes = []
    for n in PANE_NAMES:
        nor, cen, faces = pane_info(bpy.data.objects[n], body_c)
        log("pane", n, tuple(round(x, 3) for x in nor), tuple(round(x, 3) for x in cen))
        panes.append((n, nor, cen, faces))

    bm_body = solidify_to_bmesh(body)

    # First test: unit cube boolean at WS_R location
    test = bmesh.new()
    bmesh.ops.create_cube(test, size=0.6)
    for v in test.verts:
        v.co += Vector((0.55, 17.3, 1.35))
    ov, mn, mx = bvh_overlap_test(bm_body, test)
    log("test cube verts inside body AABB", ov, "bodyAABB", list(mn), list(mx))
    try:
        # Blender 5 bmesh boolean
        ret = bmesh.ops.boolean(
            bm_body,
            geom=list(bm_body.faces) + list(bm_body.edges) + list(bm_body.verts),
            operation="DIFFERENCE",
            use_hole_tolerant=True,
            use_exact=True,
            bm2=test,
        )
        log("test boolean faces now", len(bm_body.faces))
    except TypeError as e:
        log("boolean signature mismatch", e)
        # try alternate API
        try:
            bmesh.ops.boolean(
                bm_body,
                faces=list(bm_body.faces),
                operation="DIFFERENCE",
                boolean_sets=[list(bm_body.faces), list(test.faces)],
            )
        except Exception as e2:
            log("alt boolean failed", e2)
    test.free()
    chk = hole_check(bm_body)
    log("after test cube", chk)

    # If test worked, continue with panes on a fresh solidify
    bm_body.free()
    bm_body = solidify_to_bmesh(body)

    for n, nor, cen, faces in panes:
        prism = prism_bmesh(faces, nor)
        ov, _, _ = bvh_overlap_test(bm_body, prism)
        log("overlap", n, "prism verts in AABB", ov, "prism faces", len(prism.faces))
        before = len(bm_body.faces)
        try:
            bmesh.ops.boolean(
                bm_body,
                geom=list(bm_body.faces) + list(bm_body.edges) + list(bm_body.verts),
                operation="DIFFERENCE",
                use_hole_tolerant=True,
                use_exact=True,
                bm2=prism,
            )
        except Exception as e:
            log("bmesh boolean fail", n, e)
            # Fallback: modifier path with mesh objects
            me_p = bpy.data.meshes.new(f"prism_{n}")
            prism.to_mesh(me_p)
            ob_p = bpy.data.objects.new(f"切割体_{n}", me_p)
            bpy.context.collection.objects.link(ob_p)
            # bake current bm_body to object
            me_b = bpy.data.meshes.new("tmp_body")
            bm_body.to_mesh(me_b)
            # ensure object
            tmp = bpy.data.objects.get("_TmpCut")
            if tmp:
                bpy.data.objects.remove(tmp, do_unlink=True)
            tmp = bpy.data.objects.new("_TmpCut", me_b)
            bpy.context.collection.objects.link(tmp)
            mod = tmp.modifiers.new("b", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            if hasattr(mod, "use_hole_tolerant"):
                mod.use_hole_tolerant = True
            mod.object = ob_p
            dg = bpy.context.evaluated_depsgraph_get()
            ev = tmp.evaluated_get(dg)
            baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
            bm_body.free()
            bm_body = bmesh.new()
            bm_body.from_mesh(baked)
            bm_body.normal_update()
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.meshes.remove(me_b, do_unlink=True)
        prism.free()
        log("after", n, "faces", before, "->", len(bm_body.faces))

    # Remove inward faces
    kill = []
    for f in bm_body.faces:
        c = f.calc_center_median()
        n = f.normal.normalized()
        radial = Vector((c.x, 0, c.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        else:
            radial.normalize()
        score = n.dot(radial)
        if c.y > 19.0:
            score = max(score, n.dot(Vector((0, 1, 0))))
        if score < -0.35:
            kill.append(f)
    if kill and len(kill) < len(bm_body.faces) * 0.55:
        bmesh.ops.delete(bm_body, geom=kill, context="FACES")
        log("removed inward", len(kill))

    chk = hole_check(bm_body)
    with open(os.path.join(LOG_DIR, "bmesh_cut_holes.json"), "w") as f:
        json.dump(chk, f, indent=2)

    # Write to Nose_开窗 object (local coords = world if identity)
    me = bpy.data.meshes.new("Nose_开窗")
    bm_body.to_mesh(me)
    bm_body.free()
    # Inverse of body matrix if needed — body typically identity
    mwi = body.matrix_world.inverted()
    for v in me.vertices:
        v.co = mwi @ v.co

    cut = bpy.data.objects.new("Nose_开窗", me)
    for uc in body.users_collection:
        uc.objects.link(cut)
    body.hide_set(True)
    body.hide_render = True

    # Glass / seals / cabin quickly
    def mkmat(name, col, rough, trans=None, alpha=None):
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
            if "Alpha" in bsdf.inputs and alpha is not None:
                bsdf.inputs["Alpha"].default_value = alpha
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                if hasattr(mat, attr):
                    try:
                        setattr(mat, attr, val)
                    except Exception:
                        pass
        return mat

    gmat = mkmat("C919_玻璃", (0.867, 0.933, 0.922), 0.02, 1.0, 0.3)
    smat = mkmat("C919_窗框", (0.02, 0.02, 0.02), 0.5)
    cmat = mkmat("C919_驾驶舱", (0.07, 0.07, 0.08), 0.6)

    gl = bmesh.new()
    seal = bmesh.new()
    for n, nor, cen, faces in panes:
        edge_use = defaultdict(int)
        vmap = {}
        for verts in faces:
            ids = []
            keys = []
            for co in verts:
                key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
                keys.append(key)
                if key not in vmap:
                    vmap[key] = gl.verts.new(co - nor * 0.004)
                ids.append(vmap[key])
            try:
                gl.faces.new(ids)
            except ValueError:
                pass
            for i in range(len(keys)):
                a, b = keys[i], keys[(i + 1) % len(keys)]
                edge_use[tuple(sorted((a, b)))] += 1
        for (a, b), cnt in edge_use.items():
            if cnt != 1:
                continue
            p0, p1 = Vector(a), Vector(b)
            mid = (p0 + p1) * 0.5
            t = (p1 - p0)
            if t.length < 1e-9:
                continue
            t.normalize()
            inward = cen - mid
            inward = inward - t * inward.dot(t)
            if inward.length < 1e-8:
                inward = nor.cross(t)
            inward.normalize()
            off = -nor * 0.002
            pts = [p0 + off, p1 + off, p1 + off + inward * 0.04, p0 + off + inward * 0.04]
            try:
                seal.faces.new([seal.verts.new(p) for p in pts])
            except ValueError:
                pass

    for nm, bm, mat in (("C919_玻璃", gl, gmat), ("C919_窗框", seal, smat)):
        me2 = bpy.data.meshes.new(nm)
        bm.to_mesh(me2)
        bm.free()
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(nm, me2)
        bpy.context.collection.objects.link(ob)
        # to local if needed — glass was world; objects at origin OK
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
    for n in PANE_NAMES:
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    # Soft radome if tip intact
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    tip_y = max(v.co.y for v in bm.verts)
    if tip_y > 19.5:
        tip_verts = [v for v in bm.verts if v.co.y > tip_y - 0.4]
        ring = [v for v in tip_verts if tip_y - 0.3 < v.co.y < tip_y - 0.1]
        if len(ring) < 8:
            ring = [v for v in tip_verts if v.co.y < tip_y - 0.05]
        mx = sum(v.co.x for v in ring) / max(len(ring), 1)
        mz = sum(v.co.z for v in ring) / max(len(ring), 1)
        ry = sum(v.co.y for v in ring) / max(len(ring), 1)
        R = sum(math.sqrt((v.co.x - mx) ** 2 + (v.co.z - mz) ** 2) for v in ring) / max(len(ring), 1)
        R = max(min(R, 0.5), 0.18)
        for v in tip_verts:
            r = math.sqrt((v.co.x - mx) ** 2 + (v.co.z - mz) ** 2)
            if r > R * 1.15:
                continue
            dy = math.sqrt(max(0.0, R * R - min(r, R) ** 2)) * 0.8
            if v.co.y >= ry - 0.01:
                v.co.y = ry + dy
        bm.to_mesh(cut.data)
        cut.data.update()
        log("radome ok tip", tip_y, "R", R)
    bm.free()

    render_nose("step3_cut", cut)
    render_nose("step6_final", cut)

    # hide helpers
    for o in list(bpy.data.objects):
        if o.name.startswith("切割体") or o.name == "_TmpCut":
            bpy.data.objects.remove(o, do_unlink=True)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB)
    log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend"))

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 nose-fix bmesh cut

- hole checks: {json.dumps(chk)}
- GLB: {size}
- outline_source: fallback_existing_WS_SW_panes_ref_derived
- WindowOutline: 0; REF mats not windshield-specific
"""
        )
    log("DONE")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""C919 nose fix v2 — more robust boolean + radome. blender -b only."""
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

PROJ = os.environ.get("C919_PROJ", r"C:\Users\希儿\Projects\c919-autonomy")
SRC_BLEND = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
# Prefer fresh backup if work blend was half-modified
FALLBACK_BLEND = os.path.join(PROJ, "public", "models", "c919.blend.bak-nose-fix")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB_OUT = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND_OUT = os.path.join(PROJ, "public", "models", "c919.blend")
WORK_SAVE = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")

BODY_NAME = "Nose"
FORWARD = Vector((0.0, 1.0, 0.0))
ONLY_FRONT = False
CUT_DEPTH = 0.35
GLASS_INSET = 0.004
SEAL_WIDTH = 0.04
FRONT_DOT = 0.20

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def log(*a):
    print("NOSEFIXv2", *a, flush=True)


def save_checkpoint(tag):
    path = os.path.join(PROJ, "public", "models", f"c919_nose_fix_{tag}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    log("checkpoint", path)
    return path


def get_obj(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise RuntimeError("missing: " + name)
    return ob


def world_bmesh(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def face_islands_set(face_set):
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


def island_normal_center(island):
    n, c, area = Vector(), Vector(), 0.0
    for f in island:
        a = f.calc_area()
        n += f.normal * a
        c += f.calc_center_median() * a
        area += a
    if area < 1e-12:
        return Vector((0, 1, 0)), Vector()
    return n.normalized(), c / area


def setup_cam():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
    except Exception:
        pass
    cam = bpy.data.objects.get("NoseFixCam")
    if cam is None:
        cd = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cd)
        bpy.context.collection.objects.link(cam)
    scene.camera = cam
    return cam


def aim_cam(cam, eye, target, lens=50):
    cam.location = Vector(eye)
    cam.data.lens = lens
    direction = (Vector(target) - Vector(eye)).normalized()
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def nose_tip_pt():
    nose = bpy.data.objects.get("Nose_开窗") or get_obj(BODY_NAME)
    corners = [nose.matrix_world @ Vector(c) for c in nose.bound_box]
    return Vector((0.0, max(c.y for c in corners) - 0.15, 0.55))


def render_views(prefix, hide_names=None, show_extra=None):
    cam = setup_cam()
    tip = nose_tip_pt()
    saved = {}
    for o in bpy.data.objects:
        if o.type not in {"MESH", "CURVE", "EMPTY"}:
            continue
        saved[o.name] = (o.hide_render, o.hide_get())
        show = True
        if hide_names and o.name in hide_names:
            show = False
        if "2-287" in o.name:
            show = False
        if o.name.startswith("切割体"):
            show = False
        if show_extra and o.name in show_extra:
            show = True
        o.hide_render = not show
        try:
            o.hide_set(not show)
        except Exception:
            pass
    shots = [
        ("front", tip + Vector((0, 6.0, 0.4)), tip, 55),
        ("side", tip + Vector((7.0, -1.0, 0.8)), tip, 50),
        ("45", tip + Vector((4.5, 4.0, 1.5)), tip, 50),
    ]
    paths = []
    for tag, eye, tgt, lens in shots:
        aim_cam(cam, eye, tgt, lens)
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)
        paths.append(fp)
    for name, (hr, hg) in saved.items():
        o = bpy.data.objects.get(name)
        if o:
            o.hide_render = hr
            try:
                o.hide_set(hg)
            except Exception:
                pass
    return paths


def ensure_ref():
    for o in bpy.data.objects:
        if "2-287" in o.name:
            o.hide_set(True)
            o.hide_render = True
            return o
    return None


def build_glass_from_ws():
    """Join WS_L/R SW_L/R into REF_玻璃 with outward normals."""
    names = ["WS_L", "WS_R", "SW_L", "SW_R"]
    objs = []
    for n in names:
        o = bpy.data.objects.get(n)
        if o is None or o.type != "MESH":
            raise RuntimeError("missing pane " + n)
        objs.append(o)

    body = get_obj(BODY_NAME)
    body_center = body.matrix_world @ (
        sum((Vector(b) for b in body.bound_box), Vector()) / 8.0
    )

    bm = bmesh.new()
    pane_meta = []
    for ob in objs:
        wbm = world_bmesh(ob)
        # One island expected
        islands = face_islands_set(set(wbm.faces))
        for isl in islands:
            n, c = island_normal_center(isl)
            if n.dot(c - body_center) < 0:
                for f in isl:
                    f.normal_flip()
                n, c = island_normal_center(isl)
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
            pane_meta.append({"name": ob.name, "faces": len(isl), "n": list(n), "c": list(c)})
        wbm.free()
        ob.hide_set(True)
        ob.hide_render = True

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # flip any still inward
    for f in bm.faces:
        if f.normal.dot(f.calc_center_median() - body_center) < 0:
            f.normal_flip()

    me = bpy.data.meshes.new("REF_玻璃_mesh")
    bm.to_mesh(me)
    bm.free()
    old = bpy.data.objects.get("REF_玻璃")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    gob = bpy.data.objects.new("REF_玻璃", me)
    bpy.context.collection.objects.link(gob)
    log("REF_玻璃 faces", len(me.polygons), "meta", pane_meta)
    with open(os.path.join(LOG_DIR, "step2_v2.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "outline_source": "fallback_existing_WS_SW_panes_ref_derived",
                "note": "REF materials not windshield-specific; WindowOutline absent; "
                "using Soft WS_L/R SW_L/R panes (REF soft_y derived)",
                "panes": pane_meta,
                "faces": len(me.polygons),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return gob


def make_cutter_from_island(island, normal, name, coll):
    bm = bmesh.new()
    vmap = {}
    for f in island:
        verts = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm.verts.new(v.co - normal * CUT_DEPTH)
            verts.append(vmap[v])
        try:
            bm.faces.new(verts)
        except ValueError:
            pass
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=normal * (2.0 * CUT_DEPTH))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # solidify-ish: ensure volume — extrude already creates prism
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.display_type = "WIRE"
    return ob


def split_panes(gbm, body_center):
    """Split glass bmesh into up to 4 panes by quadrant / normal."""
    buckets = {"WS_L": [], "WS_R": [], "SW_L": [], "SW_R": []}
    for f in gbm.faces:
        c = f.calc_center_median()
        n = f.normal.normalized()
        # Front windshield: strong +Y component or high Y
        if c.y >= 16.9 and abs(n.y) >= abs(n.x) * 0.55:
            key = "WS_R" if c.x >= 0 else "WS_L"
        elif c.y >= 16.9:
            key = "WS_R" if c.x >= 0 else "WS_L"
        else:
            key = "SW_R" if c.x >= 0 else "SW_L"
        buckets[key].append(f)
    islands = []
    for k, faces in buckets.items():
        if not faces:
            continue
        n, c = island_normal_center(faces)
        if n.dot(c - body_center) < 0:
            n = -n
        islands.append((k, faces, n, c))
        log("pane", k, "faces", len(faces), "n", tuple(round(x, 3) for x in n), "c", tuple(round(x, 3) for x in c))
    return islands


def count_nose_holes(obj):
    bm = world_bmesh(obj)
    be = [e for e in bm.edges if e.is_boundary]
    # windshield belt
    tip = [e for e in be if ((e.verts[0].co + e.verts[1].co) * 0.5).y > 15.5]
    n = len(tip)
    bm.free()
    return len(be), n


def boolean_cut(body, glass):
    gbm = world_bmesh(glass)
    body_center = body.matrix_world @ (
        sum((Vector(b) for b in body.bound_box), Vector()) / 8.0
    )
    islands = split_panes(gbm, body_center)
    if len(islands) < 4:
        log("WARNING panes", len(islands))

    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    panes_for_glass = []
    for i, (k, faces, n, c) in enumerate(islands):
        make_cutter_from_island(faces, n, f"切割体_{k}", coll)
        panes_for_glass.append((faces, n, c, k.startswith("WS")))

    # Duplicate body
    new_body = body.copy()
    new_body.data = body.data.copy()
    new_body.name = body.name + "_开窗"
    for uc in body.users_collection:
        if new_body.name not in [o.name for o in uc.objects]:
            uc.objects.link(new_body)

    # Remove old cut body if any
    for o in list(bpy.data.objects):
        if o.name.startswith("Nose_开窗") and o != new_body:
            bpy.data.objects.remove(o, do_unlink=True)

    mod = new_body.modifiers.new("风挡开窗", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    if hasattr(mod, "use_hole_tolerant"):
        mod.use_hole_tolerant = True

    dg = bpy.context.evaluated_depsgraph_get()
    ev = new_body.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = new_body.data
    new_body.modifiers.clear()
    new_body.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)

    body.hide_set(True)
    body.hide_render = True
    coll.hide_viewport = True
    coll.hide_render = True

    total_be, tip_be = count_nose_holes(new_body)
    log("cut faces", len(new_body.data.polygons), "boundary_edges", total_be, "tip_belt_be", tip_be)

    gbm.free()
    return new_body, panes_for_glass, islands


def glass_mat():
    mat = bpy.data.materials.get("C919_玻璃") or bpy.data.materials.new("C919_玻璃")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

    def setin(names, val):
        for nm in names:
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = val
                return

    setin(["Base Color"], (221 / 255, 238 / 255, 235 / 255, 1.0))
    setin(["Roughness"], 0.02)
    setin(["IOR"], 1.5)
    setin(["Transmission Weight", "Transmission"], 1.0)
    setin(["Alpha"], 0.3)
    for attr, val in (
        ("surface_render_method", "BLENDED"),
        ("blend_method", "BLEND"),
    ):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat


def dark_mat(name, rgb, rough):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = rough
    return mat


def build_glass_seals_cabin(islands, body_center):
    # Glass inset
    gl_bm = bmesh.new()
    for k, faces, n, c in islands:
        if n.dot(c - body_center) < 0:
            n = -n
        vmap = {}
        for f in faces:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = gl_bm.verts.new(v.co - n * GLASS_INSET)
                vs.append(vmap[v])
            try:
                gl_bm.faces.new(vs)
            except ValueError:
                pass
    me = bpy.data.meshes.new("C919_玻璃")
    gl_bm.to_mesh(me)
    gl_bm.free()
    for nm in ("C919_玻璃",):
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    gob = bpy.data.objects.new("C919_玻璃", me)
    bpy.context.collection.objects.link(gob)
    gob.data.materials.append(glass_mat())

    # Seals from each island boundary
    seal_bm = bmesh.new()
    for k, faces, n, c in islands:
        if n.dot(c - body_center) < 0:
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
            tangent = (v1 - v0)
            if tangent.length < 1e-9:
                continue
            tangent.normalize()
            inward = c - mid
            inward = inward - tangent * inward.dot(tangent)
            if inward.length < 1e-8:
                inward = n.cross(tangent)
            inward.normalize()
            off = -n * 0.002
            a = v0 + off
            b = v1 + off
            d = v1 + off + inward * SEAL_WIDTH
            c2 = v0 + off + inward * SEAL_WIDTH
            try:
                vs = [seal_bm.verts.new(p) for p in (a, b, d, c2)]
                seal_bm.faces.new(vs)
            except ValueError:
                pass
    sme = bpy.data.meshes.new("C919_窗框")
    seal_bm.to_mesh(sme)
    seal_bm.free()
    old = bpy.data.objects.get("C919_窗框")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    sob = bpy.data.objects.new("C919_窗框", sme)
    bpy.context.collection.objects.link(sob)
    sob.data.materials.append(dark_mat("C919_窗框", (0.02, 0.02, 0.02), 0.5))

    # Cabin — ensure dark
    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin is None:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= 2.5
            v.co.y *= 1.5
            v.co.z *= 1.4
            v.co += Vector((0, 16.7, 0.5))
        cme = bpy.data.meshes.new("CockpitCabin")
        bm.to_mesh(cme)
        bm.free()
        cabin = bpy.data.objects.new("CockpitCabin", cme)
        bpy.context.collection.objects.link(cabin)
    cabin.data.materials.clear()
    cabin.data.materials.append(dark_mat("C919_驾驶舱", (0.07, 0.07, 0.08), 0.6))
    cabin.hide_set(False)
    cabin.hide_render = False

    for n in ("CockpitFrames", "WindshieldWipers", "REF_玻璃"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    return gob, sob, cabin


def round_radome(cut_body):
    """Remove flat tip disk; grid-fill ring; push spherical pole +Y."""
    bm = bmesh.new()
    bm.from_mesh(cut_body.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    mw = cut_body.matrix_world
    mwi = mw.inverted()

    def W(v):
        return mw @ v.co

    tip_y = max(W(v).y for v in bm.verts)
    # Collect tip flat faces (facing +Y near tip)
    flat = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = (mw.to_3x3() @ f.normal).normalized()
        if c.y > tip_y - 0.12 and n.dot(Vector((0, 1, 0))) > 0.75:
            flat.append(f)
    log("radome flat faces", len(flat), "tip_y", tip_y)

    # Also grab faces in tip cap by vertex: all verts with y > tip_y - 0.05
    if len(flat) < 3:
        flat = []
        for f in bm.faces:
            if all(W(v).y > tip_y - 0.06 for v in f.verts):
                flat.append(f)
        log("radome tip-by-verts faces", len(flat))

    if flat:
        # ring verts before delete
        ring_verts = set()
        for f in flat:
            for e in f.edges:
                linked_flat = sum(1 for lf in e.link_faces if lf in flat)
                if linked_flat == 1:
                    ring_verts.update(e.verts)
        bmesh.ops.delete(bm, geom=list(flat), context="FACES")
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # boundary edges near tip
        tip_edges = [
            e
            for e in bm.edges
            if e.is_boundary
            and (W(e.verts[0]).y + W(e.verts[1]).y) * 0.5 > tip_y - 0.4
        ]
        log("radome tip_edges", len(tip_edges))
        if tip_edges:
            try:
                ret = bmesh.ops.holes_fill(bm, edges=tip_edges, sides=len(tip_edges))
                log("holes_fill", len(ret.get("faces", [])))
            except Exception as ex:
                log("holes_fill err", ex)
                try:
                    bmesh.ops.edgenet_fill(bm, edges=tip_edges)
                except Exception as ex2:
                    log("edgenet err", ex2)

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Ring from current tip boundary or from previous ring_verts still alive
        ring = []
        for e in bm.edges:
            if e.is_boundary:
                midy = (W(e.verts[0]).y + W(e.verts[1]).y) * 0.5
                if midy > tip_y - 0.55:
                    ring.extend(e.verts)
        ring = list({v for v in ring})
        if len(ring) < 4:
            ring = [v for v in bm.verts if W(v).y > tip_y - 0.35]
        log("radome ring verts", len(ring))

        if len(ring) >= 4:
            mean_x = sum(W(v).x for v in ring) / len(ring)
            mean_z = sum(W(v).z for v in ring) / len(ring)
            ring_y = sum(W(v).y for v in ring) / len(ring)
            R = sum(
                math.sqrt((W(v).x - mean_x) ** 2 + (W(v).z - mean_z) ** 2) for v in ring
            ) / len(ring)
            R = max(R, 0.08)
            log("radome R", R, "ring_y", ring_y, "mean_z", mean_z)

            # Dissolve n-gon into triangle fan with new pole
            # Find tip faces (new fill)
            tip_faces = [
                f
                for f in bm.faces
                if (mw @ f.calc_center_median()).y > ring_y - 0.05
            ]
            # Create pole vert
            pole_world = Vector((mean_x, ring_y + 0.65 * R, mean_z))
            pole = bm.verts.new(mwi @ pole_world)
            bm.verts.ensure_lookup_table()

            # Delete tip fill faces and rebuild fan from ring to pole
            if tip_faces:
                # get ordered ring loop
                tip_edges2 = [e for e in bm.edges if e.is_boundary and (
                    W(e.verts[0]).y + W(e.verts[1]).y) * 0.5 > ring_y - 0.2]
                bmesh.ops.delete(bm, geom=tip_faces, context="FACES")
                bm.edges.ensure_lookup_table()
                tip_edges2 = [e for e in bm.edges if e.is_boundary and (
                    W(e.verts[0]).y + W(e.verts[1]).y) * 0.5 > ring_y - 0.25]
                # order edges into loop
                if tip_edges2:
                    from collections import defaultdict as dd

                    adj = dd(list)
                    for e in tip_edges2:
                        adj[e.verts[0]].append(e.verts[1])
                        adj[e.verts[1]].append(e.verts[0])
                    start = next(iter(adj))
                    ordered = [start]
                    prev = None
                    cur = start
                    for _ in range(len(tip_edges2) + 2):
                        nbs = [x for x in adj[cur] if x != prev]
                        if not nbs:
                            break
                        nxt = nbs[0]
                        if nxt == start:
                            ordered.append(nxt)
                            break
                        ordered.append(nxt)
                        prev, cur = cur, nxt
                    if ordered and ordered[0] == ordered[-1]:
                        ordered = ordered[:-1]
                    for i in range(len(ordered)):
                        a = ordered[i]
                        b = ordered[(i + 1) % len(ordered)]
                        try:
                            bm.faces.new([a, b, pole])
                        except ValueError:
                            pass

            # Spherical reshape all tip verts (ring + near)
            for v in list(bm.verts):
                vw = W(v)
                if vw.y < ring_y - 0.15:
                    continue
                r = math.sqrt((vw.x - mean_x) ** 2 + (vw.z - mean_z) ** 2)
                if r > R * 1.15:
                    continue
                # hemisphere
                sphere_dy = math.sqrt(max(0.0, R * R - min(r, R) ** 2)) * 0.92
                target = Vector((vw.x, ring_y + sphere_dy, vw.z))
                # don't pull ring back
                if v in ring or abs(vw.y - ring_y) < 0.02 and r > R * 0.85:
                    continue
                v.co = mwi @ target
            pole.co = mwi @ Vector((mean_x, ring_y + 0.92 * R, mean_z))

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut_body.data)
    cut_body.data.update()
    bm.free()
    log("radome final faces", len(cut_body.data.polygons))


def cleanup_and_export(cut_body):
    # delete helpers by name snapshot
    to_delete = []
    for o in bpy.data.objects:
        n = o.name
        if (
            n.startswith("切割体")
            or n.startswith("WindowOutline")
            or n.startswith("WS_Patch_")
            or n.startswith("窗户轮廓")
            or n == "REF_玻璃"
        ):
            to_delete.append(n)
    for n in to_delete:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", n)

    for o in bpy.data.objects:
        if "2-287" in o.name or o.name == "Nose":
            o.hide_set(True)
            o.hide_render = True
            try:
                o.hide_viewport = True
            except Exception:
                pass

    cut_body.hide_set(False)
    cut_body.hide_render = False
    try:
        cut_body.hide_viewport = False
    except Exception:
        pass

    coll = bpy.data.collections.get("风挡切割体")
    if coll:
        coll.hide_viewport = True
        coll.hide_render = True

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    bpy.ops.export_scene.gltf(
        filepath=GLB_OUT,
        export_format="GLB",
        use_visible=True,
        export_apply=True,
    )
    size = os.path.getsize(GLB_OUT)
    log("GLB", GLB_OUT, size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK_SAVE)
    return size


def ref_compare_renders():
    ref = next((o for o in bpy.data.objects if "2-287" in o.name), None)
    if not ref:
        return
    cam = setup_cam()
    corners = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
    tip = Vector(
        (
            0.0,
            max(c.y for c in corners) - 0.4,
            min(c.z for c in corners) + 5.2,
        )
    )
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
        aim_cam(cam, eye, tip, lens)
        fp = os.path.join(OUT_DIR, f"step6_ref_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)
    for name, (hr, hg) in saved.items():
        o = bpy.data.objects.get(name)
        if o:
            o.hide_render = hr
            try:
                o.hide_set(hg)
            except Exception:
                pass
    ref.hide_set(True)
    ref.hide_render = True


def main():
    src = SRC_BLEND if os.path.isfile(SRC_BLEND) else FALLBACK_BLEND
    # Always start from bak-nose-fix for clean Nose if work blend may be dirty
    # Prefer bak for clean procedural state
    if os.path.isfile(FALLBACK_BLEND):
        src = FALLBACK_BLEND
    log("open", src)
    bpy.ops.wm.open_mainfile(filepath=src)

    # Re-import REF if missing (bak may not have it)
    ensure_ref()
    if not any("2-287" in o.name for o in bpy.data.objects):
        ref_path = os.path.join(PROJ, "refs", "REF_C919_meters.fbx")
        before = set(bpy.data.objects.keys())
        bpy.ops.import_scene.fbx(filepath=ref_path, global_scale=1.0, use_image_search=False)
        for o in list(bpy.data.objects):
            if o.name not in before and ("1-818" in o.name or o.name == "Cube"):
                bpy.data.objects.remove(o, do_unlink=True)
        ensure_ref()

    # Clear leftover cutters / prior cut body
    for o in list(bpy.data.objects):
        if o.name.startswith("切割体") or o.name.startswith("Nose_开窗") or o.name in (
            "REF_玻璃",
            "C919_玻璃",
            "C919_窗框",
        ):
            bpy.data.objects.remove(o, do_unlink=True)

    # Unhide Nose
    nose = get_obj(BODY_NAME)
    nose.hide_set(False)
    nose.hide_render = False

    # Unhide WS panes for join
    for n in ("WS_L", "WS_R", "SW_L", "SW_R"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(False)
            o.hide_render = False

    log("===== STEP2 =====")
    glass = build_glass_from_ws()
    render_views("step2_patches", hide_names=["CockpitFrames"])
    save_checkpoint("step2")

    log("===== STEP3 =====")
    cut_body, panes_meta, islands = boolean_cut(nose, glass)
    # Hide glass so holes visible
    glass.hide_set(True)
    glass.hide_render = True
    for n in ("CockpitFrames", "C919_玻璃", "WS_L", "WS_R", "SW_L", "SW_R"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True
    # Temporarily hide cabin to see through holes
    cabin = bpy.data.objects.get("CockpitCabin")
    cabin_state = None
    if cabin:
        cabin_state = cabin.hide_get()
        cabin.hide_set(True)
        cabin.hide_render = True
    render_views("step3_cut")
    if cabin and cabin_state is not None:
        cabin.hide_set(cabin_state)
        cabin.hide_render = False
    save_checkpoint("step3")

    total_be, tip_be = count_nose_holes(cut_body)
    if tip_be < 20:
        log("WARNING: few tip boundary edges — boolean may have failed", tip_be)

    log("===== STEP4 =====")
    # Re-read glass for islands (gbm from boolean used freed data — rebuild from REF_玻璃)
    gbm = world_bmesh(glass)
    body_center = cut_body.matrix_world @ (
        sum((Vector(b) for b in cut_body.bound_box), Vector()) / 8.0
    )
    islands2 = split_panes(gbm, body_center)
    # convert to (k, faces, n, c)
    build_glass_seals_cabin(islands2, body_center)
    gbm.free()
    render_views("step4_glass", hide_names=["CockpitFrames", "REF_玻璃", "Nose"])
    save_checkpoint("step4")

    log("===== STEP5 =====")
    round_radome(cut_body)
    render_views("step5_radome", hide_names=["CockpitFrames", "REF_玻璃", "Nose"])
    save_checkpoint("step5")

    log("===== STEP6 =====")
    size = cleanup_and_export(cut_body)
    render_views("step6_final", hide_names=["CockpitFrames", "Nose"])
    ref_compare_renders()

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 机头修复笔记（nose-fix v2）

- **时间**：2026-10-17（Asia/Shanghai）
- **模式**：blender `-b`；禁止 knife_project；原 Nose 隐藏，副本 `Nose_开窗`

## Step1 摘要
- 机身：`Nose`（Fuselage 分离）
- 机头：Soft tip **+Y ≈ 20.03**
- WindowOutline：**0**（blend 内无）
- REF：`Obj3d66-19714258-2-287`；材质 Transmission 全 0；无独立风挡材质岛

## Step2
- 轮廓来源：`fallback_existing_WS_SW_panes_ref_derived`
- （a）REF 材质岛非风挡专用；（b）WindowOutline 缺失
- 使用场景内已有 `WS_L/WS_R/SW_L/SW_R`（nose-ref 按 REF soft_y 生成）并成 `REF_玻璃`

## Step3–6
- 布尔 EXACT + hole_tolerant，ONLY_FRONT=False，CUT_DEPTH={CUT_DEPTH}
- tip_belt boundary_edges≈（见控制台）
- GLB bytes: **{size}**
- 备份：`c919.glb.bak-nose-fix` / `c919.blend.bak-nose-fix`

## 预览
`public/models/nose-fix/step{{1..6}}_*.png`
"""
        )
    log("notes", notes)
    log("DONE", size)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

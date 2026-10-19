# -*- coding: utf-8 -*-
"""ws4: knife_project windshield — GUI only (no -b).

  blender --factory-startup --python scripts/ws4_knife_project_windshield.py
"""
from __future__ import annotations

import math
import os
import sys
import traceback

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
OUT = os.path.join(ROOT, "public", "models")

Z_LO, Z_HI = 0.58, 1.18
FRONT_Y = 17.85
WS_R_XZ = [(0.20, Z_LO), (0.90, Z_LO), (0.85, Z_HI), (0.24, Z_HI)]
WS_L_XZ = [(-x, z) for x, z in WS_R_XZ]
SIDE_X = 2.85
SW_YZ = [(17.08, Z_LO), (16.28, Z_LO), (16.22, Z_HI), (16.98, Z_HI)]


def log(*a):
    print("WS4", *a, flush=True)


def get_view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is not None:
                return window, area, region, area.spaces.active
    return None, None, None, None


def ensure_object_mode(active=None):
    if active is not None:
        bpy.ops.object.select_all(action="DESELECT")
        active.hide_set(False)
        active.hide_viewport = False
        active.select_set(True)
        bpy.context.view_layer.objects.active = active
    obj = bpy.context.view_layer.objects.active
    if obj is None:
        # pick any mesh
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                obj = o
                break
    if obj is not None and obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def mesh_from_quads(name, quads):
    bm = bmesh.new()
    for quad in quads:
        vs = [bm.verts.new(Vector(p)) for p in quad]
        bm.faces.new(vs)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def build_outlines():
    for n in (
        "WindowOutline",
        "WindowOutline_Front",
        "WindowOutline_Side",
        "窗户轮廓",
        "窗户轮廓_前",
        "窗户轮廓_侧",
    ):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)

    front = mesh_from_quads(
        "WindowOutline_Front",
        [
            [(x, FRONT_Y, z) for x, z in WS_L_XZ],
            [(x, FRONT_Y, z) for x, z in WS_R_XZ],
        ],
    )
    side = mesh_from_quads(
        "WindowOutline_Side",
        [[(SIDE_X, y, z) for y, z in SW_YZ]],
    )
    # User-facing Chinese empty
    empty = bpy.data.objects.new("窗户轮廓", None)
    bpy.context.collection.objects.link(empty)
    front.parent = empty
    side.parent = empty
    # Also alias Chinese mesh names via duplication? Keep ASCII for ops stability.
    log("outlines", front.name, side.name)
    return front, side


def knife_project(target, cutter, view_axis: str, cut_through=True):
    window, area, region, space = get_view3d()
    if area is None:
        raise RuntimeError("No VIEW_3D — run without --background")

    for ob in (target, cutter):
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.hide_select = False
        try:
            ob.hide_get()
        except Exception:
            pass

    # Select both; active = target. Use override for edit mode (Blender 5 context).
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    cutter.select_set(True)
    bpy.context.view_layer.objects.active = target
    sel = [o for o in bpy.context.view_layer.objects if o.select_get()]
    log(
        "knife prep",
        view_axis,
        "active",
        getattr(bpy.context.view_layer.objects.active, "name", None),
        "sel",
        [o.name for o in sel],
    )

    # Blender 5 timer context: use minimal override; selection via select_set
    with bpy.context.temp_override(
        window=window,
        area=area,
        region=region,
        active_object=target,
        object=target,
    ):
        # Ensure selection state inside override
        bpy.ops.object.select_all(action="DESELECT")
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode="EDIT")
        cutter.select_set(True)  # selected non-active = cutter
        log("knife begin", view_axis, "mode", bpy.context.mode,
            "active", bpy.context.view_layer.objects.active.name)
        bpy.ops.view3d.view_axis(type=view_axis)
        bpy.ops.mesh.knife_project(cut_through=cut_through)
        bpy.ops.object.mode_set(mode="OBJECT")
    log("knife ok", view_axis)
    cutter.select_set(False)


def _point_in_poly_2d(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi):
            inside = not inside
        j = i
    return inside


def delete_faces_inside_outlines(nose):
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.faces.ensure_lookup_table()
    side_poly = list(SW_YZ)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        # Strict upper band — never below centerline, never onto crown tip
        if c.z < Z_LO - 0.05 or c.z > Z_HI + 0.05:
            continue
        # Reject near-tip crown (y too far forward / too high z relative)
        if c.y > 17.70:
            continue
        # Front panes: only forward cheek facing, limited |x|
        if 16.90 <= c.y <= 17.75 and abs(c.x) <= 1.35:
            xz = WS_L_XZ if c.x < 0 else WS_R_XZ
            # After FRONT knife, trust XZ outline; only require outer-ish skin
            if _point_in_poly_2d((c.x, c.z), xz):
                rx, rz = _section_rx_rz(c.y)
                rad = math.hypot(c.x / max(rx, 1e-6), c.z / max(rz, 1e-6))
                if rad > 0.75:
                    kill.append(f)
                    continue
        # Side panes
        if 16.18 <= c.y <= 17.12 and abs(c.x) > 1.25:
            if _point_in_poly_2d((c.y, c.z), side_poly):
                rx, rz = _section_rx_rz(c.y)
                if abs(c.x) / max(rx, 1e-6) > 0.88:
                    kill.append(f)
    n = len(kill)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    dead = [v for v in bm.verts if not v.link_faces]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="VERTS")
    # dissolve short boundary edges lightly
    bm.edges.ensure_lookup_table()
    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.02]
    if short:
        try:
            bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
        except Exception:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(nose.data)
    nose.data.update()
    bm.free()
    log("deleted_interior_faces", n)
    return n


def _section_rx_rz(y):
    stations = [
        (19.88, 0.55, 0.50),
        (18.88, 1.26, 1.18),
        (17.68, 1.64, 1.57),
        (17.28, 1.72, 1.66),
        (16.58, 1.85, 1.80),
        (15.82, 1.95, 1.92),
        (14.85, 2.06, 2.06),
        (0.0, 2.09, 2.10),
    ]
    if y >= stations[0][0]:
        return stations[0][1], stations[0][2]
    if y <= stations[-1][0]:
        return stations[-1][1], stations[-1][2]
    for (y0, rx0, rz0), (y1, rx1, rz1) in zip(stations, stations[1:]):
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1 + 1e-9)
            return rx0 + (rx1 - rx0) * t, rz0 + (rz1 - rz0) * t
    return 2.0, 2.0


def snap_to_skin(x, y, z, r_off=0.0):
    rx, rz = _section_rx_rz(y)
    zz = max(-rz * 0.98, min(rz * 0.98, z))
    inside = max(0.0, 1.0 - (zz / rz) ** 2)
    xx = math.copysign(rx * math.sqrt(inside), x if abs(x) > 1e-6 else 1.0)
    sx, sz = xx / max(rx, 1e-6), zz / max(rz, 1e-6)
    nx, nz = sx / max(rx, 1e-6), sz / max(rz, 1e-6)
    nlen = math.hypot(nx, nz) or 1.0
    nx, nz = nx / nlen, nz / nlen
    return Vector((xx + nx * r_off, y, zz + nz * r_off))


def make_glass_pane(name, corners_xyz, segs=8):
    bm = bmesh.new()
    c0, c1, c2, c3 = [Vector(c) for c in corners_xyz]
    grid = []
    for j in range(segs + 1):
        v = j / segs
        row = []
        for i in range(segs + 1):
            u = i / segs
            p = c0 * (1 - u) * (1 - v) + c1 * u * (1 - v) + c2 * u * v + c3 * (1 - u) * v
            row.append(bm.verts.new(snap_to_skin(p.x, p.y, p.z, r_off=-0.005)))
        grid.append(row)
    for j in range(segs):
        for i in range(segs):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def glass_material():
    name = "CockpitGlass"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = (0.867, 0.933, 0.922, 1.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = col
        for k, v in (
            ("Transmission Weight", 1.0),
            ("Transmission", 1.0),
            ("Alpha", 0.18),
            ("Roughness", 0.02),
            ("IOR", 1.5),
            ("Metallic", 0.0),
        ):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = v
    try:
        mat.blend_method = "HASHED"
    except Exception:
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    return mat


def seal_material():
    name = "CockpitSeal"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1)
        bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def extrude_hole_seals(nose, depth=0.04):
    bm_src = bmesh.new()
    bm_src.from_mesh(nose.data)
    bm_src.edges.ensure_lookup_table()
    be = []
    for e in bm_src.edges:
        if not e.is_boundary:
            continue
        m = (e.verts[0].co + e.verts[1].co) * 0.5
        if 16.1 <= m.y <= 18.0 and Z_LO - 0.15 <= m.z <= Z_HI + 0.2:
            be.append(e)
    log("boundary_edges_ws", len(be))
    bm = bmesh.new()
    for e in be:
        v0, v1 = e.verts[0].co.copy(), e.verts[1].co.copy()
        mid = (v0 + v1) * 0.5
        inward = Vector((-mid.x, 0.0, -mid.z))
        if inward.length < 1e-6:
            inward = Vector((0, 0, -1))
        inward.normalize()
        a = bm.verts.new(v0)
        b = bm.verts.new(v1)
        c = bm.verts.new(v1 + inward * depth)
        d = bm.verts.new(v0 + inward * depth)
        try:
            bm.faces.new((a, b, c, d))
        except ValueError:
            pass
    bm_src.free()
    old = bpy.data.objects.get("CockpitFrames")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    if not bm.faces:
        bm.free()
        return None
    me = bpy.data.meshes.new("CockpitFrames_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("CockpitFrames", me)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(seal_material())
    return obj


def ensure_cabin():
    old = bpy.data.objects.get("CockpitCabin")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    bm = bmesh.new()
    x, y0, y1, z0, z1 = 1.1, 16.15, 17.55, 0.15, 1.35
    corners = [
        (-x, y0, z0), (x, y0, z0), (x, y1, z0), (-x, y1, z0),
        (-x, y0, z1), (x, y0, z1), (x, y1, z1), (-x, y1, z1),
    ]
    vs = [bm.verts.new(c) for c in corners]
    for f in (
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ):
        bm.faces.new(tuple(vs[i] for i in f))
    me = bpy.data.meshes.new("CockpitCabin_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("CockpitCabin", me)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.get("CockpitCabinMat") or bpy.data.materials.new("CockpitCabinMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.03, 0.035, 0.04, 1)
        bsdf.inputs["Roughness"].default_value = 0.8
    obj.data.materials.append(mat)
    return obj



def glass_from_hole_boundaries(nose):
    """Build WS/SW panes from actual knife hole boundary loops (guaranteed alignment)."""
    for n in ("WS_L", "WS_R", "SW_L", "SW_R", "Windshield", "CockpitMask"):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)

    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # collect windshield-band boundary edges
    bedges = []
    for e in bm.edges:
        if not e.is_boundary:
            continue
        m = (e.verts[0].co + e.verts[1].co) * 0.5
        if 16.1 <= m.y <= 17.75 and Z_LO - 0.2 <= m.z <= Z_HI + 0.25:
            bedges.append(e)

    # walk loops
    unused = set(bedges)
    loops = []
    while unused:
        start = unused.pop()
        loop_e = [start]
        changed = True
        while changed:
            changed = False
            verts = set()
            for e in loop_e:
                verts.add(e.verts[0]); verts.add(e.verts[1])
            add = [e for e in list(unused) if e.verts[0] in verts or e.verts[1] in verts]
            for e in add:
                unused.discard(e)
                loop_e.append(e)
                changed = True
        # ordered verts
        if len(loop_e) < 4:
            continue
        # order around loop
        vset = []
        e0 = loop_e[0]
        v_cur, v_prev = e0.verts[0], e0.verts[1]
        vset.append(v_cur)
        used_e = {e0}
        for _ in range(len(loop_e) - 1):
            found = None
            for e in loop_e:
                if e in used_e:
                    continue
                if e.verts[0] == v_cur:
                    found = e; nxt = e.verts[1]; break
                if e.verts[1] == v_cur:
                    found = e; nxt = e.verts[0]; break
            if not found:
                break
            used_e.add(found)
            v_cur = nxt
            vset.append(v_cur)
        if len(vset) >= 4:
            loops.append([v.co.copy() for v in vset])

    bm.free()
    log("hole_loops", len(loops), [len(L) for L in loops])

    gmat = glass_material()
    # Classify loops: by mean x sign and mean y
    named = []
    for pts in loops:
        mx = sum(p.x for p in pts) / len(pts)
        my = sum(p.y for p in pts) / len(pts)
        mz = sum(p.z for p in pts) / len(pts)
        if my >= 17.05:
            name = "WS_R" if mx >= 0 else "WS_L"
        else:
            name = "SW_R" if mx >= 0 else "SW_L"
        # Avoid name collision if duplicate
        base = name
        i = 2
        while any(n == name for n, *_rest in named):
            name = f"{base}_{i}"; i += 1
        named.append((name, pts, mx, my, mz))

    # Prefer canonical 4 names — if extras, keep largest loops per quadrant
    best = {}
    for name, pts, mx, my, mz in named:
        key = name.split("_")[0] + ("_R" if mx >= 0 else "_L")
        if key.startswith("WS") and my < 17.0:
            key = "SW" + key[2:]
        if key.startswith("SW") and my >= 17.1:
            key = "WS" + key[2:]
        # map to WS_L/WS_R/SW_L/SW_R
        if my >= 17.05:
            key = "WS_R" if mx >= 0 else "WS_L"
        else:
            key = "SW_R" if mx >= 0 else "SW_L"
        area = abs(mx) * len(pts)  # crude
        if key not in best or len(pts) > len(best[key][1]):
            best[key] = (name, pts)

    objs = []
    for key, (_n, pts) in best.items():
        # Build inset glass: fan from center, offset inward
        bm2 = bmesh.new()
        center = sum(pts, Vector((0, 0, 0))) / len(pts)
        inward = Vector((-center.x, 0, -center.z))
        if inward.length < 1e-6:
            inward = Vector((0, 0, -1))
        inward.normalize()
        vs = [bm2.verts.new(p + inward * 0.005) for p in pts]
        # ngon
        try:
            bm2.faces.new(vs)
        except ValueError:
            # fan
            c = bm2.verts.new(center + inward * 0.005)
            for i in range(len(vs)):
                bm2.faces.new((c, vs[i], vs[(i + 1) % len(vs)]))
        me = bpy.data.meshes.new(key + "_mesh")
        bm2.to_mesh(me)
        bm2.free()
        # remove existing same name
        old = bpy.data.objects.get(key)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        obj = bpy.data.objects.new(key, me)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(gmat)
        for p in obj.data.polygons:
            p.use_smooth = True
        objs.append(obj)
        log("glass_from_loop", key, len(pts))

    # Ensure all 4 exist — fallback to procedural if missing
    have = {o.name for o in objs}
    if len(have) < 4:
        log("WARN only", sorted(have), "— procedural fill for missing panes")
        # replace_glass_panes() clears all WS/SW; rebuild everything procedurally
        return replace_glass_panes()
    return objs


def replace_glass_panes():
    for n in ("WS_L", "WS_R", "SW_L", "SW_R", "Windshield", "CockpitMask"):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    gmat = glass_material()
    panes = {
        "WS_R": [(0.18, 17.52, Z_LO), (0.95, 17.45, Z_LO), (0.90, 17.08, Z_HI), (0.22, 17.15, Z_HI)],
        "WS_L": [(-0.18, 17.52, Z_LO), (-0.95, 17.45, Z_LO), (-0.90, 17.08, Z_HI), (-0.22, 17.15, Z_HI)],
        "SW_R": [(1.55, 17.05, Z_LO), (1.72, 16.30, Z_LO), (1.55, 16.25, Z_HI), (1.40, 16.98, Z_HI)],
        "SW_L": [(-1.55, 17.05, Z_LO), (-1.72, 16.30, Z_LO), (-1.55, 16.25, Z_HI), (-1.40, 16.98, Z_HI)],
    }
    objs = []
    for name, corners in panes.items():
        ob = make_glass_pane(name, corners, segs=10)
        ob.data.materials.append(gmat)
        objs.append(ob)
    return objs


def parent_to_c919(*objs):
    root = bpy.data.objects.get("C919")
    if not root:
        return
    for ob in objs:
        if ob is not None:
            ob.parent = root


def export_glb():
    addon = "io_scene_gltf2"
    if addon not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon)
    for n in (
        "WindowOutline_Front",
        "WindowOutline_Side",
        "窗户轮廓",
    ):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    # Timer context lacks active_object — restore before glTF export
    nose = bpy.data.objects.get("Nose")
    ensure_object_mode(nose)
    kwargs = dict(
        filepath=GLB,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_extras=True,
    )
    window, area, region, _ = get_view3d()
    override = {}
    if window and area and region:
        override = dict(window=window, area=area, region=region, active_object=nose, object=nose)
    def _do(**extra):
        if override:
            with bpy.context.temp_override(**override):
                bpy.ops.export_scene.gltf(**kwargs, **extra)
        else:
            bpy.ops.export_scene.gltf(**kwargs, **extra)
    for key, val in (("use_visible", True), ("export_visible", True)):
        try:
            _do(**{key: val})
            log("exported", GLB, os.path.getsize(GLB), key)
            return
        except TypeError:
            continue
        except Exception as e:
            log("export try fail", key, e)
    _do()
    log("exported", GLB, os.path.getsize(GLB))


def audit():
    keys = [
        "Nose", "WS_L", "WS_R", "SW_L", "SW_R", "CockpitFrames", "CockpitCabin",
        "Doors", "Wing_R", "Engine_R", "VerticalTail",
    ]
    missing = 0
    for n in keys:
        ob = bpy.data.objects.get(n)
        if not ob:
            missing += 1
            log("MISSING", n)
        else:
            log("OK", n, len(ob.data.polygons) if ob.type == "MESH" else 0)
    if bpy.data.objects.get("CockpitMask"):
        missing += 1
        log("FAIL CockpitMask")
    else:
        log("OK CockpitMask absent")
    log("MISSING_COUNT", missing)
    return missing


def render_previews():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 28
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 800
    scene.render.image_settings.file_format = "PNG"
    world = scene.world or bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.55, 0.62, 0.70, 1)
        bg.inputs[1].default_value = 1.15
    for name in list(bpy.data.objects.keys()):
        if name.startswith("Prev"):
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    sun = bpy.data.lights.new("PrevKey", type="SUN")
    sun.energy = 5.5
    so = bpy.data.objects.new("PrevKey", sun)
    scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(48), 0, math.radians(35))
    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def shot(path, loc, look, lens=42):
        cam_data.lens = lens
        cam.location = Vector(loc)
        d = Vector(look) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        log("WROTE", path)

    shot(os.path.join(OUT, "c919-detail-windshield-34.png"), (7.0, 21.0, 4.2), (0.2, 17.0, 0.9), 40)
    shot(os.path.join(OUT, "c919-detail-windshield-side.png"), (11.0, 16.9, 1.3), (0.0, 16.9, 0.9), 48)
    shot(os.path.join(OUT, "c919-detail-nose-top.png"), (0.0, 16.9, 11.5), (0.0, 16.9, 0.5), 48)
    shot(os.path.join(OUT, "c919-preview-ws4.png"), (19.0, 25.0, 8.5), (1.0, 6.0, 1.0), 38)


def run():
    try:
        log("start", "bg=", bpy.app.background)
        if bpy.app.background:
            log("FATAL need GUI (no -b)")
            return None
        if not os.path.isfile(BLEND):
            log("FATAL no blend", BLEND)
            return None

        bpy.ops.wm.open_mainfile(filepath=BLEND)
        bpy.context.view_layer.update()
        nose = bpy.data.objects.get("Nose")
        if nose is None:
            log("FATAL no Nose", "objects", [o.name for o in bpy.data.objects][:30])
            return None
        log("nose", nose.name, nose.type, "parent", getattr(nose.parent, "name", None),
            "users_collection", [c.name for c in nose.users_collection])
        ensure_object_mode(nose)
        log("after ensure active", getattr(bpy.context.view_layer.objects.active, "name", None))

        for n in ("CockpitMask",):
            ob = bpy.data.objects.get(n)
            if ob:
                bpy.data.objects.remove(ob, do_unlink=True)

        front, side = build_outlines()
        # Unparent cutters from empty for cleaner selection (empty can confuse)
        front.parent = None
        side.parent = None

        knife_project(nose, side, "RIGHT", cut_through=True)
        # Front cut_through with cutter close to skin (FRONT_Y≈17.85)
        knife_project(nose, front, "FRONT", cut_through=True)

        n_del = delete_faces_inside_outlines(nose)
        if n_del < 5:
            log("WARN few faces deleted", n_del)

        panes = glass_from_hole_boundaries(nose)
        seals = extrude_hole_seals(nose, depth=0.04)
        cabin = ensure_cabin()
        parent_to_c919(*panes, seals, cabin)

        missing = audit()
        export_glb()
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        try:
            render_previews()
        except Exception as e:
            log("render_fail", e)
            traceback.print_exc()
        log("DONE missing", missing, "glb", os.path.getsize(GLB) if os.path.isfile(GLB) else 0)
    except Exception:
        log("EXCEPTION")
        traceback.print_exc()
    finally:
        log("quit")
        bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=0.5)

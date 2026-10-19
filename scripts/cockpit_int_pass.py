# -*- coding: utf-8 -*-
"""Full dark cockpit interior + frames + wipers + glass update.

Does NOT move/reshape Nose / CockpitGlass_REF panes / fuselage join.

  blender -b --factory-startup -P scripts/cockpit_int_pass.py
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
LOG = os.path.join(ROOT, "scripts", "_cockpit_int_logs")
PREV = os.path.join(OUT, "cockpit-int")
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

KEEP = {
    "Nose", "CockpitGlass_REF", "Fuselage", "Fuselage_ORIG",
    "Windows", "WindowFrames", "Doors", "DoorFrames", "DoorWindows",
    "Stripe_L", "Stripe_R", "Wing_L", "Wing_R", "Winglet_L", "Winglet_R",
    "WingFairing_L", "WingFairing_R", "WingLE_L", "WingLE_R",
    "WingBodyFairing_L", "WingBodyFairing_R",
    "Engine_L", "Engine_R", "EngineLip_L", "EngineLip_R", "Fan_L", "Fan_R",
    "Pylon_L", "Pylon_R", "Stab_L", "Stab_R", "VerticalTail", "Rudder",
    "TailCone", "TailMark", "TailMark_L", "Title", "Title_L",
    "Gear_L", "Gear_R", "Gear_Nose", "GearBayDoors",
    "AntennasAPU", "Flag_L", "Flag_R", "RadomePanelLines",
}


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


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
        "dx": max(xs) - min(xs),
        "dy": max(ys) - min(ys),
        "dz": max(zs) - min(zs),
    }


def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    return name


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


def link_obj(name, me, mat=None):
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        me.materials.clear()
        me.materials.append(mat)
    shade_smooth(obj)
    return obj


# ---------- inventory ----------
def inventory_cockpit_scraps(glass, nose):
    gb = world_bbox(glass)
    # expand region a bit
    region = {
        "ymin": gb["ymin"] - 1.5,
        "ymax": gb["ymax"] + 2.0,
        "zmin": gb["zmin"] - 1.0,
        "zmax": gb["zmax"] + 1.2,
        "xmin": gb["xmin"] - 0.5,
        "xmax": gb["xmax"] + 0.5,
    }
    rows = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        bb = world_bbox(obj)
        # intersects cockpit region?
        overlap = not (
            bb["ymax"] < region["ymin"]
            or bb["ymin"] > region["ymax"]
            or bb["zmax"] < region["zmin"]
            or bb["zmin"] > region["zmax"]
            or bb["xmax"] < region["xmin"]
            or bb["xmin"] > region["xmax"]
        )
        if not overlap and obj.name not in (
            "CockpitCabin", "WindshieldGapStrip", "CockpitFrames",
            "GlareShield", "PilotSeats", "WindshieldWipers",
        ):
            continue
        me = obj.data
        rows.append({
            "name": obj.name,
            "type": obj.type,
            "verts": len(me.vertices),
            "edges": len(me.edges),
            "faces": len(me.polygons),
            "hide": bool(obj.hide_render),
            "bbox": bb,
            "keep": obj.name in KEEP or obj.name.startswith("Wing") or obj.name.startswith("Engine"),
        })
    rows.sort(key=lambda r: r["name"])
    return rows, region


# ---------- interior shell from nose ----------
def build_interior_shell(nose, glass):
    """Duplicate nose faces behind windshield, flip normals, shrink 5cm inward."""
    gv = mesh_world_verts(glass)
    g_ymin = min(v.y for v in gv)
    g_ymax = max(v.y for v in gv)
    g_zmin = min(v.z for v in gv)
    g_zmax = max(v.z for v in gv)

    nv = mesh_world_verts(nose)
    tip_y = max(v.y for v in nv)
    # Cover all windows: from tip-3.2 to tip-1.0, but also expand to glass extents + margin
    y0 = min(tip_y - 3.2, g_ymin - 0.35)
    y1 = max(tip_y - 1.0, g_ymax + 0.15)
    z0 = g_zmin - 0.30
    z1 = g_zmax + 0.30

    log(f"[interior] tip_y={tip_y:.3f} y=[{y0:.3f},{y1:.3f}] z=[{z0:.3f},{z1:.3f}]")

    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    mw = nose.matrix_world.copy()
    bmesh.ops.transform(bm, matrix=mw, verts=list(bm.verts))

    keep = []
    for f in bm.faces:
        c = f.calc_center_median()
        if y0 <= c.y <= y1 and z0 <= c.z <= z1:
            # skip very bottom belly far from windows
            keep.append(f)
    kill = [f for f in bm.faces if f not in set(keep)]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    if len(bm.faces) < 10:
        bm.free()
        raise RuntimeError("interior shell: too few faces selected")

    # shrink 5 cm toward centerline (X=0, Z ~ window mid)
    zc = 0.5 * (g_zmin + g_zmax)
    for v in bm.verts:
        # toward (0, y, zc) in XZ, keep Y
        target = Vector((0.0, v.co.y, zc))
        delta = target - v.co
        # only pull in XZ
        delta.y = 0.0
        if delta.length > 1e-8:
            v.co += delta.normalized() * min(0.05, delta.length * 0.15)
            # stronger fixed 5cm when far enough
            radial = Vector((v.co.x, 0.0, v.co.z - zc))
            if radial.length > 0.08:
                v.co -= radial.normalized() * 0.05

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # flip inward
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

    me = bpy.data.meshes.new("CockpitInteriorShell")
    bm.to_mesh(me)
    bm.free()
    mat = ensure_mat("CockpitDark", hex_rgb("1A1C1F"), roughness=0.8, metallic=0.0)
    obj = link_obj("CockpitInterior", me, mat)
    log(f"[interior] shell faces={len(me.polygons)} verts={len(me.vertices)}")
    return obj, (y0, y1, z0, z1, zc, tip_y, g_ymin, g_ymax, g_zmin, g_zmax)


def add_box(name, cx, cy, cz, sx, sy, sz, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=list(bm.verts), vec=(sx, sy, sz))
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx, cy, cz))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link_obj(name, me, mat)


def build_internals(glass, tip_y, g_ymin, g_ymax, g_zmin, g_zmax, zc):
    """Glare shield, instrument panel, seat silhouettes."""
    dark = ensure_mat("CockpitDark2", hex_rgb("121416"), roughness=0.85)
    black = ensure_mat("CockpitBlack", hex_rgb("0A0B0C"), roughness=0.9)
    objs = []

    # Glare shield: curved-ish plate behind lower edge of FRONT windshields
    # Front panes are the higher-Y part of glass
    front_y = g_ymax - 0.15
    # plate just aft of glass lower front, spanning X of glass
    gv = mesh_world_verts(bpy.data.objects["CockpitGlass_REF"])
    front_verts = [v for v in gv if v.y >= g_ymax - 0.55]
    if not front_verts:
        front_verts = gv
    fx0 = min(v.x for v in front_verts)
    fx1 = max(v.x for v in front_verts)
    fz_low = min(v.z for v in front_verts)
    # shield behind glass (lower Y), at lower z band
    objs.append(
        add_box(
            "CockpitGlareShield",
            0.0,
            front_y - 0.22,
            fz_low - 0.02,
            max(0.8, (fx1 - fx0) * 0.85),
            0.12,
            0.08,
            black,
        )
    )
    # mild curve approx: two side wings slightly aft
    for side, sx in ((-1, fx0 * 0.55), (1, fx1 * 0.55)):
        objs.append(
            add_box(
                f"CockpitGlareWing_{'L' if side < 0 else 'R'}",
                sx,
                front_y - 0.28,
                fz_low + 0.02,
                0.35,
                0.10,
                0.06,
                black,
            )
        )

    # Instrument panel below glare shield
    objs.append(
        add_box(
            "CockpitInstrumentPanel",
            0.0,
            front_y - 0.38,
            fz_low - 0.18,
            max(0.9, (fx1 - fx0) * 0.75),
            0.18,
            0.22,
            dark,
        )
    )

    # Seats further aft (lower Y)
    seat_y = g_ymin - 0.15
    for side, name in ((-1, "CockpitSeat_L"), (1, "CockpitSeat_R")):
        # base
        objs.append(
            add_box(name + "_Base", side * 0.42, seat_y, g_zmin - 0.05, 0.38, 0.40, 0.12, dark)
        )
        # back
        objs.append(
            add_box(name + "_Back", side * 0.42, seat_y - 0.12, g_zmin + 0.28, 0.36, 0.12, 0.55, black)
        )

    # Join seats under one empty? Keep separate named; also make aggregate parent empty
    log(f"[interior] internals={[o.name for o in objs]}")
    return objs


# ---------- frames ----------
def glass_islands(glass):
    """Return list of face-island world vert sets for each pane."""
    bm = bmesh.new()
    bm.from_mesh(glass.data)
    bm.faces.ensure_lookup_table()
    mw = glass.matrix_world
    remaining = set(bm.faces)
    islands = []
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        faces = {seed}
        while stack:
            f = stack.pop()
            for e in f.edges:
                for of in e.link_faces:
                    if of in remaining:
                        remaining.remove(of)
                        faces.add(of)
                        stack.append(of)
        # world centers / bbox of island
        pts = []
        for f in faces:
            for v in f.verts:
                pts.append(mw @ v.co)
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        zs = [p.z for p in pts]
        islands.append({
            "faces": faces,
            "cx": 0.5 * (min(xs) + max(xs)),
            "cy": 0.5 * (min(ys) + max(ys)),
            "cz": 0.5 * (min(zs) + max(zs)),
            "xmin": min(xs), "xmax": max(xs),
            "ymin": min(ys), "ymax": max(ys),
            "zmin": min(zs), "zmax": max(zs),
            "pts": pts,
        })
    bm.free()
    islands.sort(key=lambda d: (d["cy"], d["cx"]))
    return islands


def build_frames(glass, nose):
    """3cm black seals around each pane + metal pillars between panes."""
    # remove old
    for n in list(bpy.data.objects):
        if n.name.startswith("CockpitSeal_") or n.name.startswith("CockpitPillar_"):
            delete_object(n)

    seal_mat = ensure_mat("CockpitSeal", hex_rgb("0E0E0E"), roughness=0.4)
    metal_mat = ensure_mat("CockpitPillarMetal", hex_rgb("9A9DA1"), roughness=0.35, metallic=0.6)

    islands = glass_islands(glass)
    log(f"[frames] glass islands={len(islands)}")
    for i, isl in enumerate(islands):
        log(
            f"  pane{i} cx={isl['cx']:.2f} cy={isl['cy']:.2f} cz={isl['cz']:.2f} "
            f"x=[{isl['xmin']:.2f},{isl['xmax']:.2f}] y=[{isl['ymin']:.2f},{isl['ymax']:.2f}] "
            f"z=[{isl['zmin']:.2f},{isl['zmax']:.2f}]"
        )

    # Build seal rim from glass boundary edges extruded outward 3cm along surface, thickness 3mm
    bm_g = bmesh.new()
    bm_g.from_mesh(glass.data)
    bm_g.edges.ensure_lookup_table()
    bm_g.faces.ensure_lookup_table()
    mw = glass.matrix_world.copy()
    bmesh.ops.transform(bm_g, matrix=mw, verts=list(bm_g.verts))
    bmesh.ops.recalc_face_normals(bm_g, faces=list(bm_g.faces))

    # boundary edges
    boundary = [e for e in bm_g.edges if len(e.link_faces) == 1]
    # create seal mesh: for each boundary edge, make a quad strip outward 3cm and outward-normal 3mm
    bm_s = bmesh.new()
    width = 0.03
    thick = 0.003
    for e in boundary:
        f = e.link_faces[0]
        n = f.normal.normalized()
        # outward in face plane: from face center to edge mid, projected
        mid = 0.5 * (e.verts[0].co + e.verts[1].co)
        fc = f.calc_center_median()
        out = mid - fc
        out = out - n * out.dot(n)
        if out.length < 1e-8:
            # fallback tangential
            out = n.cross(e.verts[1].co - e.verts[0].co)
        out.normalize()
        a, b = e.verts[0].co, e.verts[1].co
        # four corners of outer strip + push slightly out of skin
        push = n * thick
        v0 = a + push
        v1 = b + push
        v2 = b + out * width + push
        v3 = a + out * width + push
        vs = [bm_s.verts.new(p) for p in (v0, v1, v2, v3)]
        try:
            bm_s.faces.new(vs)
        except ValueError:
            pass
        # thin side wall
        v0b = a
        v1b = b
        vs2 = [bm_s.verts.new(p) for p in (v0b, v1b, v1, v0)]
        try:
            bm_s.faces.new(vs2)
        except ValueError:
            pass

    me_s = bpy.data.meshes.new("CockpitSeals")
    bm_s.to_mesh(me_s)
    bm_s.free()
    seal_obj = link_obj("CockpitSeals", me_s, seal_mat)
    log(f"[frames] seals faces={len(me_s.polygons)}")

    # Pillars: between islands — front center (between two front panes) and front-side junctions
    # Classify: front panes have higher mean Y; left/right by cx
    if len(islands) >= 2:
        by_y = sorted(islands, key=lambda d: -d["cy"])
        # top 2 by Y approx front
        front = by_y[:2] if len(by_y) >= 2 else by_y
        front = sorted(front, key=lambda d: d["cx"])
        pillars = []
        if len(front) == 2:
            # center pillar between front panes
            a, b = front[0], front[1]
            cx = 0.5 * (a["xmax"] + b["xmin"]) if a["xmax"] < b["xmin"] else 0.5 * (a["cx"] + b["cx"])
            cy = 0.5 * (a["cy"] + b["cy"])
            cz = 0.5 * (a["cz"] + b["cz"])
            hz = max(0.25, 0.5 * (min(a["zmax"], b["zmax"]) - max(a["zmin"], b["zmin"])) + 0.05)
            hy = max(0.08, 0.35 * min(a["ymax"] - a["ymin"], b["ymax"] - b["ymin"]))
            pillars.append(("CockpitPillar_Center", cx, cy - 0.01, cz, 0.028, hy, hz * 2))

        # pillars between each front and nearest side (lower Y)
        sides = [isl for isl in islands if isl not in front]
        for s in sides:
            # nearest front
            f = min(front, key=lambda p: abs(p["cx"] - s["cx"])) if front else None
            if f is None:
                continue
            cx = 0.5 * (f["cx"] + s["cx"])
            # place at contact Y
            cy = 0.5 * (min(f["ymin"], s["ymax"]) + max(f["ymax"], s["ymin"])) if False else 0.5 * (f["ymin"] + s["ymax"])
            cy = 0.5 * (f["cy"] + s["cy"])
            cz = 0.5 * (f["cz"] + s["cz"])
            side = "L" if s["cx"] < 0 else "R"
            pillars.append((
                f"CockpitPillar_{side}",
                cx,
                cy,
                cz,
                0.026,
                max(0.12, abs(f["cy"] - s["cy"]) * 0.5 + 0.08),
                max(0.35, 0.55 * (min(f["zmax"], s["zmax"]) - max(f["zmin"], s["zmin"])) + 0.1),
            ))

        for name, cx, cy, cz, sx, sy, sz in pillars:
            # box then push slightly outward along radial so flush-ish
            obj = add_box(name, cx, cy, cz, sx, sy, sz, metal_mat)
            # nudge outward 2mm
            radial = Vector((cx, 0.0, cz - 0.4))
            if radial.length > 1e-6:
                for v in obj.data.vertices:
                    v.co += radial.normalized() * 0.002
            log(f"[frames] {name} at ({cx:.2f},{cy:.2f},{cz:.2f})")

    bm_g.free()
    return seal_obj, islands


# ---------- wipers ----------
def build_wipers(glass, islands):
    for n in list(bpy.data.objects):
        if n.name.startswith("Wiper_"):
            delete_object(n)
    mat = ensure_mat("WiperDark", hex_rgb("2A2C2E"), roughness=0.55)
    # front panes = two highest cy
    front = sorted(islands, key=lambda d: -d["cy"])[:2]
    front = sorted(front, key=lambda d: d["cx"])
    objs = []
    for i, pane in enumerate(front):
        side = "L" if pane["cx"] < 0 else "R"
        # park at lower edge of front windshield
        y = pane["ymin"] + 0.04
        z = pane["zmin"] + 0.03
        x = pane["cx"]
        # outward normal approx from centerline
        radial = Vector((x, 0.0, z - 0.3))
        nrm = radial.normalized() if radial.length > 1e-6 else Vector((0, 0, 1))
        # 5mm outside glass
        base = Vector((x, y, z)) + nrm * 0.005

        # arm: from base toward mid of pane, length ~0.25 then blade 0.6
        # parked roughly along lower edge (mostly ±X)
        blade_dir = Vector((1.0 if pane["cx"] >= 0 else -1.0, 0.15, 0.05)).normalized()
        # arm root near center of lower edge going out
        arm_len = 0.22
        blade_len = 0.60
        arm_end = base + blade_dir * arm_len

        # arm box
        arm = add_box(
            f"Wiper_{side}_Arm",
            0.5 * (base.x + arm_end.x),
            0.5 * (base.y + arm_end.y),
            0.5 * (base.z + arm_end.z),
            0.012,
            arm_len,
            0.008,
            mat,
        )
        # orient arm along blade_dir roughly by rebuilding oriented box
        # simpler: transform verts
        _orient_box_along(arm, base, arm_end, 0.012, 0.008)

        blade_end = arm_end + blade_dir * blade_len
        blade = add_box(
            f"Wiper_{side}_Blade",
            0.5 * (arm_end.x + blade_end.x),
            0.5 * (arm_end.y + blade_end.y),
            0.5 * (arm_end.z + blade_end.z),
            0.015,
            blade_len,
            0.006,
            mat,
        )
        _orient_box_along(blade, arm_end, blade_end, 0.015, 0.006)
        objs.extend([arm, blade])
        log(f"[wiper] {side} base={base} arm_end={arm_end}")
    return objs


def _orient_box_along(obj, a: Vector, b: Vector, width, height):
    """Replace mesh with a box from a to b (cube size=1 → scale to width/length/height)."""
    direction = b - a
    length = direction.length
    if length < 1e-8:
        return
    mid = 0.5 * (a + b)
    y_axis = direction.normalized()
    tmp = Vector((0, 0, 1)) if abs(y_axis.z) < 0.9 else Vector((1, 0, 0))
    x_axis = y_axis.cross(tmp).normalized()
    z_axis = x_axis.cross(y_axis).normalized()
    basis = Matrix((
        (x_axis.x, y_axis.x, z_axis.x),
        (x_axis.y, y_axis.y, z_axis.y),
        (x_axis.z, y_axis.z, z_axis.z),
    ))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        local = Vector((v.co.x * width, v.co.y * length, v.co.z * height))
        v.co = mid + basis @ local
    me = obj.data
    bm.to_mesh(me)
    bm.free()
    me.update()


# ---------- glass mat ----------
def update_glass(glass):
    mat = glass.data.materials[0] if glass.data.materials else None
    if mat is None:
        mat = bpy.data.materials.new("REF_CockpitGlass")
        glass.data.materials.append(mat)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = hex_rgb("2E3A3E")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    for key, val in (
        ("Transmission Weight", 1.0),
        ("Transmission", 1.0),
        ("Alpha", 0.45),
        ("IOR", 1.5),
        ("Roughness", 0.03),
        ("Metallic", 0.0),
        ("Specular IOR Level", 0.55),
    ):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    info = {
        "base": "#2E3A3E",
        "alpha": 0.45,
        "trans": 1.0,
        "ior": 1.5,
        "rough": 0.03,
        "blend": getattr(mat, "blend_method", None),
        "surface": getattr(mat, "surface_render_method", None),
    }
    log(f"[glass] {info}")
    return info


# ---------- render ----------
def render_eevee():
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.eevee.use_raytracing = True
    except Exception:
        pass
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.15, 0.17, 1.0)
        bg.inputs[1].default_value = 0.85
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        ld = bpy.data.lights.new("CockpitSun", "SUN")
        ld.energy = 5.0
        lo = bpy.data.objects.new("CockpitSun", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(48), math.radians(15), math.radians(30))

    nose_look = Vector((0.0, 17.8, 0.55))
    fuse = bpy.data.objects.get("Fuselage")
    nose = bpy.data.objects.get("Nose")
    verts = mesh_world_verts(nose)
    if fuse:
        verts += mesh_world_verts(fuse)
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    y_mid = 0.5 * (min(ys) + max(ys))
    z_mid = 0.5 * (min(zs) + max(zs))
    span = max(ys) - min(ys)
    views = {
        "front": (Vector((0.0, nose_look.y + 13.0, 0.9)), nose_look, 45),
        "oblique45": (Vector((8.5, nose_look.y + 8.5, 2.0)), nose_look, 45),
        "side": (Vector((span * 0.55, y_mid, z_mid + 0.6)), Vector((0, y_mid, z_mid)), 40),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        for o in list(bpy.data.objects):
            if o.name.startswith("CICam_"):
                bpy.data.objects.remove(o, do_unlink=True)
        cd = bpy.data.cameras.new("CICam_" + name)
        cam = bpy.data.objects.new("CICam_" + name, cd)
        bpy.context.scene.collection.objects.link(cam)
        cam.location = loc
        cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens
        scene.camera = cam
        out = os.path.join(PREV, f"{name}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        paths.append(out)
        log(f"[render] {out}")
        bpy.data.objects.remove(cam, do_unlink=True)
    return paths


def main():
    open(os.path.join(LOG, "console.txt"), "w").close()
    log("=== COCKPIT INT PASS ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    nose = bpy.data.objects.get("Nose")
    glass = bpy.data.objects.get("CockpitGlass_REF")
    if not nose or not glass:
        raise RuntimeError("Nose / CockpitGlass_REF required")

    # 2 inventory first
    inv, region = inventory_cockpit_scraps(glass, nose)
    with open(os.path.join(LOG, "scrap_inventory_before.json"), "w", encoding="utf-8") as f:
        json.dump({"region": region, "objects": inv}, f, indent=2, ensure_ascii=False)
    log(f"[scrap] inventory n={len(inv)}")

    # delete old cabin + known scraps / previous cockpit helpers
    scrap_names = {
        "CockpitCabin", "WindshieldGapStrip", "CockpitFrames", "GlareShield",
        "PilotSeats", "WindshieldWipers", "CockpitInterior", "CockpitInteriorShell",
        "CockpitGlareShield", "CockpitInstrumentPanel", "CockpitSeals",
    }
    # also delete previous glare wings / seats / pillars / wipers
    deleted = []
    for obj in list(bpy.data.objects):
        n = obj.name
        if n in scrap_names or n.startswith("CockpitGlare") or n.startswith("CockpitSeat") \
                or n.startswith("CockpitPillar") or n.startswith("Wiper_") \
                or n.startswith("CockpitSeal"):
            # don't delete glass/nose
            if n in ("Nose", "CockpitGlass_REF"):
                continue
            deleted.append({
                "name": n,
                "faces": len(obj.data.polygons) if obj.type == "MESH" else 0,
                "verts": len(obj.data.vertices) if obj.type == "MESH" else 0,
            })
            delete_object(obj)
            log(f"[delete] {n}")

    # also delete tiny near-glass unknown meshes (faces < 30, not in KEEP)
    for obj in list(bpy.data.objects):
        if obj.type != "MESH" or obj.name in KEEP:
            continue
        if obj.name.startswith("Cockpit") or obj.name.startswith("Wiper"):
            continue
        bb = world_bbox(obj)
        gb = world_bbox(glass)
        near = (
            bb["ymax"] >= gb["ymin"] - 0.5
            and bb["ymin"] <= gb["ymax"] + 0.5
            and bb["zmax"] >= gb["zmin"] - 0.5
            and abs(bb["dx"] * bb["dy"] * bb["dz"]) < 0.05
            and len(obj.data.polygons) <= 24
        )
        if near and obj.name not in ("RadomePanelLines",):
            deleted.append({"name": obj.name, "faces": len(obj.data.polygons), "reason": "tiny_near_glass"})
            delete_object(obj)
            log(f"[delete tiny] {obj.name}")

    with open(os.path.join(LOG, "scrap_deleted.json"), "w", encoding="utf-8") as f:
        json.dump(deleted, f, indent=2, ensure_ascii=False)

    # 1 interior
    shell, extents = build_interior_shell(nose, glass)
    y0, y1, z0, z1, zc, tip_y, g_ymin, g_ymax, g_zmin, g_zmax = extents
    internals = build_internals(glass, tip_y, g_ymin, g_ymax, g_zmin, g_zmax, zc)

    # 3 frames
    seal_obj, islands = build_frames(glass, nose)

    # 4 wipers
    wipers = build_wipers(glass, islands)

    # 5 glass
    glass_info = update_glass(glass)

    # hide leftovers
    for name in ("PilotSeats", "Fuselage_ORIG", "PanelLines"):
        o = bpy.data.objects.get(name)
        if o:
            o.hide_set(True)
            o.hide_render = True
            o.hide_viewport = True

    # 6 export
    if os.path.isfile(GLB):
        shutil.copy2(GLB, GLB + ".bak-cockpit-int")
        log("backup .bak-cockpit-int")
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    size = os.path.getsize(GLB)
    log(f"GLB {size} ({size/1e6:.2f} MB)")

    paths = render_eevee()

    added = [shell.name] + [o.name for o in internals] + [seal_obj.name] + [o.name for o in wipers]
    added += [o.name for o in bpy.data.objects if o.name.startswith("CockpitPillar")]

    summary = {
        "deleted": deleted,
        "added": added,
        "glass": glass_info,
        "islands": len(islands),
        "glb_bytes": size,
        "previews": paths,
    }
    with open(os.path.join(LOG, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "COCKPIT_INT_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 驾驶舱内饰（cockpit-int）\n\n")
        f.write("## 废料清单（删除前）\n")
        f.write("见 `scripts/_cockpit_int_logs/scrap_inventory_before.json`\n\n")
        f.write("## 已删除\n")
        for d in deleted:
            f.write(f"- `{d['name']}` faces={d.get('faces')}\n")
        f.write("\n## 新增物体\n")
        for n in added:
            f.write(f"- `{n}`\n")
        f.write("\n## 玻璃\n")
        f.write(f"- Base #2E3A3E, Rough 0.03, IOR 1.5, Transmission 1.0, Alpha 0.45, BLENDED\n")
        f.write(f"- 确认: {glass_info}\n\n")
        f.write("## 导出\n")
        f.write(f"- GLB {size/1e6:.2f} MB；备份 `.bak-cockpit-int`\n")
        f.write("- 预览 `public/models/cockpit-int/{front,oblique45,side}.png`\n\n")
        f.write("## 诚实差距\n")
        f.write("- 内壳由 Nose 面片内缩翻面，接缝处可能有小洞\n")
        f.write("- 座椅/遮光罩为低模方盒，仅剪影\n")
        f.write("- 窗框密封条沿玻璃边界生成，曲率复杂处可能略不平\n")
    log(f"notes -> {notes}")
    log("=== DONE ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise

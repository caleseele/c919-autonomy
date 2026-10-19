# -*- coding: utf-8 -*-
"""Nose finish pass: materials, floaters, gap strip, door dedupe, radome lines, EEVEE renders.

Does NOT reshape Nose / glass silhouette / radome form.

  blender -b --factory-startup -P scripts/nose_finish_pass.py
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
LOG = os.path.join(ROOT, "scripts", "_nose_finish_logs")
PREV = os.path.join(OUT, "nose-finish")
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


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
    me = obj.data if getattr(obj, "type", None) == "MESH" else None
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    return name


def hide_object(obj):
    obj.hide_set(True)
    obj.hide_render = True
    obj.hide_viewport = True


# ---------- inventory ----------
def inventory_near_nose(nose_ymin=12.0):
    """List mesh objects that intersect nose region or are edge-only / very thin."""
    rows = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            # also note empties/curves near nose
            if obj.type in {"CURVE", "EMPTY", "GPENCIL"}:
                try:
                    loc = obj.matrix_world.translation
                    if loc.y >= nose_ymin - 2:
                        rows.append({
                            "name": obj.name, "type": obj.type,
                            "verts": 0, "edges": 0, "faces": 0,
                            "hide": obj.hide_render, "bbox": None,
                            "flags": ["non_mesh", f"y={loc.y:.2f}"],
                        })
                except Exception:
                    pass
            continue
        me = obj.data
        nv, ne, nf = len(me.vertices), len(me.edges), len(me.polygons)
        bb = world_bbox(obj)
        flags = []
        if nf == 0 and ne > 0:
            flags.append("edges_only")
        if nf == 0 and nv > 0 and ne == 0:
            flags.append("verts_only")
        # very thin: any dimension < 2mm or two dims tiny
        thin_dims = sum(1 for d in (bb["dx"], bb["dy"], bb["dz"]) if d < 0.005)
        if thin_dims >= 1 and nf > 0 and max(bb["dx"], bb["dy"], bb["dz"]) > 0.05:
            flags.append("thin_sheet")
        if thin_dims >= 2:
            flags.append("wire_like")
        # near nose?
        near = bb["ymax"] >= nose_ymin
        if not near and not flags:
            continue
        if near:
            flags.append("near_nose")
        rows.append({
            "name": obj.name,
            "type": obj.type,
            "verts": nv, "edges": ne, "faces": nf,
            "hide": bool(obj.hide_render),
            "bbox": bb,
            "mats": [m.name if m else None for m in me.materials],
            "flags": flags,
        })
    rows.sort(key=lambda r: (0 if "edges_only" in r["flags"] else 1, r["name"]))
    return rows


# ---------- materials ----------
def ensure_glass_mat(obj):
    mat = None
    if obj.data.materials:
        mat = obj.data.materials[0]
    if mat is None:
        mat = bpy.data.materials.new("REF_CockpitGlass")
        obj.data.materials.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    col = (0xDD / 255.0, 0xEE / 255.0, 0xEB / 255.0)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    for key, val in (
        ("Transmission Weight", 1.0),
        ("Transmission", 1.0),
        ("Alpha", 0.30),
        ("IOR", 1.5),
        ("Roughness", 0.02),
        ("Metallic", 0.0),
    ):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val
    for attr, val in (("blend_method", "BLEND"), ("use_backface_culling", False)):
        try:
            setattr(mat, attr, val)
        except Exception:
            pass
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    try:
        mat.shadow_method = "NONE"
    except Exception:
        pass
    return {
        "name": mat.name,
        "alpha": bsdf.inputs["Alpha"].default_value if "Alpha" in bsdf.inputs else None,
        "ior": bsdf.inputs["IOR"].default_value if "IOR" in bsdf.inputs else None,
        "rough": bsdf.inputs["Roughness"].default_value,
        "trans": (
            bsdf.inputs["Transmission Weight"].default_value
            if "Transmission Weight" in bsdf.inputs
            else (bsdf.inputs["Transmission"].default_value if "Transmission" in bsdf.inputs else None)
        ),
        "blend": getattr(mat, "blend_method", None),
        "surface_render": getattr(mat, "surface_render_method", None),
    }


def ensure_cabin(obj):
    if obj is None:
        return {"exists": False}
    mat = obj.data.materials[0] if obj.data.materials else None
    if mat is None:
        mat = bpy.data.materials.new("REF_CabinDark")
        obj.data.materials.append(mat)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.06, 0.065, 0.07, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return {"exists": True, "name": obj.name, "verts": len(obj.data.vertices), "mat": mat.name}


# ---------- floaters ----------
def find_and_delete_floaters(inv_rows):
    """Delete edges-only / wire-like objects near nose. Keep Nose panel geometry."""
    deleted = []
    keep_names = {
        "Nose", "CockpitGlass_REF", "CockpitCabin", "Fuselage",
        "Doors", "DoorFrames", "DoorWindows", "Windows", "WindowFrames",
    }
    suspects = []
    for r in inv_rows:
        name = r["name"]
        if name in keep_names or name.endswith("_ORIG"):
            continue
        flags = set(r["flags"])
        if flags & {"edges_only", "verts_only", "wire_like"}:
            suspects.append(r)
            continue
        # thin_sheet with almost no volume and tiny face count, near nose tip
        bb = r.get("bbox") or {}
        if "thin_sheet" in flags and r["faces"] < 30 and bb.get("dy", 0) > 0.5:
            # long thin strip — possible floater line extruded
            if min(bb.get("dx", 1), bb.get("dz", 1)) < 0.01:
                suspects.append(r)

    # Also scan Nose mesh for loose edges? We won't delete Nose.
    # Extra: objects whose name suggests outlines
    for obj in list(bpy.data.objects):
        n = obj.name.lower()
        if any(k in n for k in ("outline", "wire", "floater", "helper", "knife", "windowoutline")):
            if obj.name not in keep_names and obj.name not in [s["name"] for s in suspects]:
                suspects.append({
                    "name": obj.name, "type": obj.type,
                    "verts": len(obj.data.vertices) if obj.type == "MESH" else 0,
                    "edges": len(obj.data.edges) if obj.type == "MESH" else 0,
                    "faces": len(obj.data.polygons) if obj.type == "MESH" else 0,
                    "flags": ["name_match"],
                    "bbox": world_bbox(obj) if obj.type == "MESH" else None,
                })

    for s in suspects:
        obj = bpy.data.objects.get(s["name"])
        if obj is None:
            continue
        deleted.append({
            "name": s["name"],
            "faces": s.get("faces"),
            "edges": s.get("edges"),
            "flags": s.get("flags"),
        })
        delete_object(obj)
        log(f"[delete floater] {s['name']} flags={s.get('flags')}")
    return suspects, deleted


def clean_loose_edges_on_nose(nose):
    """Remove loose edges (no faces) on Nose mesh — can look like floating lines.

    Keep manifold edges that belong to faces (including radome panel grooves if they are face edges).
    Only delete edges with no linked faces AND verts that become unused.
    """
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.edges.ensure_lookup_table()
    loose = [e for e in bm.edges if len(e.link_faces) == 0]
    n_loose = len(loose)
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="EDGES")
        # remove orphan verts
        dead = [v for v in bm.verts if not v.link_edges]
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bm.to_mesh(nose.data)
    nose.data.update()
    bm.free()
    log(f"[Nose] removed loose edges={n_loose}")
    return n_loose


def find_bright_line_strips_on_nose(nose):
    """Detect very thin long face strips that look like floating lines (not radome panel).

    Heuristic: faces with area very small that form a chain sticking past tip or through window.
    We only REPORT candidates here; deletion of face strips is risky for panel lines.
    Return list of face indices that are isolated thin spikes past tip — optional delete.
    """
    # For item 2 user wants floaters deleted; radome panel lines kept (item 5).
    # Panel lines are usually inset edges on the surface, not separate objects.
    # Tip "horizontal line sticking out" might be a separate mesh or loose geometry.
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    tip_y = max(v.co.y for v in bm.verts)
    # verts beyond tip ring by > 2cm with valence 1-2 could be spikes
    spikes = []
    for v in bm.verts:
        if v.co.y > tip_y - 0.001:
            continue
        # actually find verts with y > tip_y - epsilon that stick out in X
        pass
    # Find edges with no faces that extend past tip (already cleaned)
    # Find faces that are extremely thin and whose centroid is forward of tip-0.05
    # and far from surface centerline in a line-like way
    candidates = []
    for f in bm.faces:
        if f.calc_area() > 0.002:
            continue
        c = f.calc_center_median()
        # very elongated face near tip
        if c.y > tip_y - 0.15 and f.calc_area() < 0.0005:
            candidates.append({"face": f.index, "y": c.y, "area": f.calc_area()})
    bm.free()
    return candidates


# ---------- glass gap strip ----------
def add_gap_fill_strip(glass, nose):
    """Add a thin dark strip just behind the upper glass rim to hide black gap.

    Prefer not expanding glass silhouette: build a rim band inset 2mm behind glass,
    expanded ~4mm outward in screen/surface sense by scaling from cabin center.
    """
    # Remove prior strip if re-run
    old = bpy.data.objects.get("WindshieldGapStrip")
    if old:
        delete_object(old)

    gv = mesh_world_verts(glass)
    # Upper rim: verts in top 20% of glass Z
    zs = [v.z for v in gv]
    z_hi = max(zs)
    z_lo = min(zs)
    z_cut = z_lo + 0.72 * (z_hi - z_lo)
    upper = [v for v in gv if v.z >= z_cut]
    if len(upper) < 8:
        upper = gv

    # Build a flat-ish ribbon: take convex-ish bbox of upper verts, inset toward -radial
    xs = [v.x for v in upper]
    ys = [v.y for v in upper]
    zs_u = [v.z for v in upper]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    cz = 0.5 * (min(zs_u) + max(zs_u))

    # Create a thin curved-ish strip as a scaled copy of upper glass faces via bmesh
    # Simpler: duplicate glass mesh, keep only upper faces, scale slightly outward from centerline, push inward 3mm
    bm = bmesh.new()
    bm.from_mesh(glass.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    # world matrix is identity after previous passes typically; use matrix_world
    mw = glass.matrix_world.copy()
    # transform to world
    bmesh.ops.transform(bm, matrix=mw, verts=list(bm.verts))

    z_cut_w = z_cut
    keep = []
    for f in bm.faces:
        c = f.calc_center_median()
        if c.z >= z_cut_w - 0.02:
            keep.append(f)
    # delete other faces
    kill = [f for f in bm.faces if f not in keep]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Push slightly inward (toward X=0, Z slightly down from crown) and expand rim ~4mm
    # Inward: move along -normal by 0.003
    for f in list(bm.faces):
        pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for v in bm.verts:
        # average of linked face normals
        n = Vector((0, 0, 0))
        for f in v.link_faces:
            n += f.normal
        if n.length > 1e-8:
            n.normalize()
            v.co -= n * 0.003  # 3mm behind glass
        # expand from aircraft centerline in XZ a bit (4mm)
        radial = Vector((v.co.x, 0.0, v.co.z - 0.1))
        if radial.length > 1e-6:
            v.co += radial.normalized() * 0.004

    # Solidify-ish: extrude along -normal 2mm so strip has thickness
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    extruded = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in extruded:
        n = Vector((0, 0, 0))
        for f in v.link_faces:
            n += f.normal
        if n.length > 1e-8:
            v.co -= n.normalized() * 0.002

    me = bpy.data.meshes.new("WindshieldGapStrip")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("WindshieldGapStrip", me)
    bpy.context.scene.collection.objects.link(obj)
    # dark seal material
    mat = bpy.data.materials.get("GapSeal") or bpy.data.materials.new("GapSeal")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    log(f"[gap strip] faces={len(me.polygons)} verts={len(me.vertices)}")
    return obj


# ---------- doors ----------
def handle_doors(nose):
    """If fuselage Doors duplicates a forward door that REF nose already has, remove fuse forward door.

    REF nose may include a door as part of the Nose mesh (not a separate object).
    Original build has separate Doors object. Strategy:
    - Inspect Doors mesh for door panels with center Y > 10 (forward)
    - If Nose mesh has a door-like rectangular feature in similar Y, delete those faces from Doors
    - Or if two door objects, keep nose-related
    """
    doors = bpy.data.objects.get("Doors")
    frames = bpy.data.objects.get("DoorFrames")
    dwar = bpy.data.objects.get("DoorWindows")
    report = {"action": "none", "details": []}

    # Detect door-like inset on Nose: look for faces with roughly door proportions in Y 12-16
    nose_has_door = False
    if nose:
        nv = mesh_world_verts(nose)
        # sample: count verts in a side patch typical for crew door
        # REF C919 nose often includes L1 door around y~12-15
        side = [v for v in nv if abs(v.x) > 1.5 and 11.0 < v.y < 16.5 and -0.5 < v.z < 1.8]
        if len(side) > 80:
            # check for local concavity / material slots — weak heuristic
            # Better: bbox holes — if Nose has a rectangular rim of edges
            nose_has_door = True
            report["details"].append(f"Nose side patch verts={len(side)} (possible door geom)")

    # Inspect Doors object components by disconnect islands
    if doors is None:
        report["action"] = "no_Doors_object"
        report["nose_has_door_hint"] = nose_has_door
        return report

    bm = bmesh.new()
    bm.from_mesh(doors.data)
    bm.verts.ensure_lookup_table()
    # islands
    remaining = set(bm.verts)
    islands = []
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        isl = {seed}
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o in remaining:
                    remaining.remove(o)
                    isl.add(o)
                    stack.append(o)
        islands.append(isl)

    island_info = []
    for i, isl in enumerate(islands):
        ys = [(doors.matrix_world @ v.co).y for v in isl]
        xs = [(doors.matrix_world @ v.co).x for v in isl]
        zs = [(doors.matrix_world @ v.co).z for v in isl]
        info = {
            "i": i,
            "n": len(isl),
            "ymin": min(ys), "ymax": max(ys),
            "yc": 0.5 * (min(ys) + max(ys)),
            "xc": 0.5 * (min(xs) + max(xs)),
            "zc": 0.5 * (min(zs) + max(zs)),
        }
        island_info.append(info)
    island_info.sort(key=lambda d: d["yc"], reverse=True)
    report["door_islands"] = island_info
    log(f"[doors] islands={json.dumps(island_info)}")

    # Forward boarding doors typically yc > 10
    forward = [d for d in island_info if d["yc"] > 10.0]
    report["forward_islands"] = forward

    # Does Nose already show a door? Check for a rectangular panel line region on Nose
    # More reliable: if Nose bbox has a door cut or painted door — REF skin often includes door outline.
    # User said: keep door on REF nose; delete original fuselage one if duplicated.
    # If we have forward islands on Doors AND nose_has_door, delete forward islands from Doors (+ frames/windows).

    # Stronger nose door detection: look for faces on Nose with normals ~±X and forming a vertical rectangle
    nose_door_yc = None
    if nose:
        nbm = bmesh.new()
        nbm.from_mesh(nose.data)
        nbm.faces.ensure_lookup_table()
        # collect face centers with |nx|>0.7, z in [0, 1.7], y in [11,16]
        centers = []
        for f in nbm.faces:
            c = nose.matrix_world @ f.calc_center_median()
            nrm = (nose.matrix_world.to_3x3() @ f.normal).normalized()
            if abs(nrm.x) > 0.75 and 11.0 < c.y < 16.5 and -0.2 < c.z < 1.9:
                centers.append(c)
        nbm.free()
        if len(centers) > 40:
            nose_has_door = True
            nose_door_yc = sum(c.y for c in centers) / len(centers)
            report["details"].append(f"Nose side-facing faces={len(centers)} yc≈{nose_door_yc:.2f}")

    deleted_islands = []
    if forward and nose_has_door:
        # delete by Y-range (stable vs island re-index)
        y_ranges = [(d["ymin"] - 0.05, d["ymax"] + 0.05) for d in forward]
        kill_verts = []
        for v in list(bm.verts):
            wy = (doors.matrix_world @ v.co).y
            if any(a <= wy <= b for a, b in y_ranges):
                kill_verts.append(v)
        deleted_islands = list(forward)
        if kill_verts:
            # also delete linked faces
            kill_faces = set()
            for v in kill_verts:
                for f in v.link_faces:
                    kill_faces.add(f)
            bmesh.ops.delete(bm, geom=list(kill_faces), context="FACES")
            # orphan verts
            dead = [v for v in bm.verts if not v.link_edges]
            if dead:
                bmesh.ops.delete(bm, geom=dead, context="VERTS")
            bm.to_mesh(doors.data)
            doors.data.update()
            report["action"] = "deleted_forward_Doors_islands"
            report["deleted"] = deleted_islands
            log(f"[doors] deleted forward islands from Doors: {deleted_islands}")

            # similarly trim DoorFrames / DoorWindows by Y range of deleted
            for companion_name in ("DoorFrames", "DoorWindows"):
                companion = bpy.data.objects.get(companion_name)
                if companion is None:
                    continue
                cbm = bmesh.new()
                cbm.from_mesh(companion.data)
                cbm.faces.ensure_lookup_table()
                y_ranges = [(d["ymin"] - 0.15, d["ymax"] + 0.15) for d in forward]
                kill_f = []
                for f in cbm.faces:
                    c = companion.matrix_world @ f.calc_center_median()
                    if any(a <= c.y <= b for a, b in y_ranges):
                        kill_f.append(f)
                if kill_f:
                    bmesh.ops.delete(cbm, geom=kill_f, context="FACES")
                    dead = [v for v in cbm.verts if not v.link_edges]
                    if dead:
                        bmesh.ops.delete(cbm, geom=dead, context="VERTS")
                    cbm.to_mesh(companion.data)
                    companion.data.update()
                    log(f"[doors] trimmed {companion_name} faces={len(kill_f)}")
                cbm.free()
        else:
            bm.to_mesh(doors.data)
    else:
        if not forward:
            report["action"] = "no_forward_fuse_door"
        elif not nose_has_door:
            report["action"] = "keep_fuse_door_nose_unclear"
        bm.free()
        bm = None

    if bm is not None:
        bm.free()
    report["nose_has_door"] = nose_has_door
    report["nose_door_yc"] = nose_door_yc
    return report


# ---------- radome panel color ----------
def tint_radome_panel_lines(nose):
    """Assign light grey #C8CACD to sharp/crease-like edges on radome tip region via a material slot.

    Approach: detect faces near tip with high curvature / long thin triangles forming panel rays,
    OR paint verts near known panel edges. Practical approach for baked mesh:
    - Find edges that are marked sharp OR have face angle > threshold near tip
    - Create thin inset strip faces? Too invasive.
    Simpler: add a second material slot and assign faces that are long radial wedges at tip.

    Even simpler for "white rays": they may be *UV/texture free* specular highlights on hard edges.
    Or separate edges showing as white in EEVEE due to auto-smooth.
    Set Edge crease / clear sharp and use a slightly darker material on tip faces? 

    Best low-risk: create material RadomePanel #C8CACD and assign to faces within tip that have
    very small area OR that form the 'star' by being adjacent to tip pole.
    Also enable and color custom edge split visualization — won't export.

    For GLB export, panel lines must be actual faces or a texture. If they are just sharp edges,
    change them by beveling a tiny panel groove with grey material — heavy.

    Check: if Nose has multiple material slots already for panel.
    """
    me = nose.data
    info = {"slots_before": [m.name if m else None for m in me.materials]}

    # Create panel material
    mat = bpy.data.materials.get("RadomePanel") or bpy.data.materials.new("RadomePanel")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    # #C8CACD
    col = (0xC8 / 255.0, 0xCA / 255.0, 0xCD / 255.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.45
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.05
    # Ensure Skin is slot 0, panel is slot 1
    if not me.materials:
        skin = bpy.data.materials.get("Skin") or bpy.data.materials.new("Skin")
        me.materials.append(skin)
    # append panel if not present
    panel_idx = None
    for i, m in enumerate(me.materials):
        if m and m.name == "RadomePanel":
            panel_idx = i
            break
    if panel_idx is None:
        me.materials.append(mat)
        panel_idx = len(me.materials) - 1
    else:
        me.materials[panel_idx] = mat

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    tip_y = max(v.co.y for v in bm.verts)
    # Region: forward 1.2m of tip
    tip_zone = tip_y - 1.2

    # Mark edges with significant angle (panel lines) near tip
    panel_faces = set()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        a, b = e.link_faces
        ang = a.normal.angle(b.normal)
        if ang < math.radians(8):
            continue
        mid = 0.5 * (e.verts[0].co + e.verts[1].co)
        if mid.y < tip_zone:
            continue
        # thin strip along this edge: assign adjacent faces that are elongated
        for f in (a, b):
            # face aspect: if area small relative to perimeter, likely a panel strip
            area = f.calc_area()
            per = sum(ed.calc_length() for ed in f.edges)
            if per < 1e-8:
                continue
            # thinness proxy
            if area < 0.015 and mid.y > tip_zone:
                panel_faces.add(f)
            # also include faces very close to tip pole with crease
            if mid.y > tip_y - 0.55 and ang > math.radians(12):
                panel_faces.add(f)

    # If too few, also take faces near tip with one very short edge (star wedges)
    if len(panel_faces) < 8:
        for f in bm.faces:
            c = f.calc_center_median()
            if c.y < tip_y - 0.7:
                continue
            lengths = sorted(e.calc_length() for e in f.edges)
            if lengths and lengths[0] < 0.08 and f.calc_area() < 0.02:
                panel_faces.add(f)

    # Assign material index
    for f in bm.faces:
        f.material_index = 0
    for f in panel_faces:
        f.material_index = panel_idx

    n_assigned = len(panel_faces)
    bm.to_mesh(me)
    me.update()
    bm.free()
    info.update({
        "panel_idx": panel_idx,
        "faces_assigned": n_assigned,
        "color": "#C8CACD",
        "slots_after": [m.name if m else None for m in me.materials],
    })
    log(f"[radome] assigned panel mat to {n_assigned} faces color=#C8CACD")
    return info


# ---------- render ----------
def setup_eevee():
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    # world soft grey so glass reads
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.13, 0.15, 1.0)
        bg.inputs[1].default_value = 0.6
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        ld = bpy.data.lights.new("FinishSun", "SUN")
        ld.energy = 4.5
        lo = bpy.data.objects.new("FinishSun", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(48), math.radians(15), math.radians(35))
    # area fill
    if not bpy.data.objects.get("FinishFill"):
        ad = bpy.data.lights.new("FinishFill", "AREA")
        ad.energy = 200
        ad.size = 8
        ao = bpy.data.objects.new("FinishFill", ad)
        bpy.context.scene.collection.objects.link(ao)
        ao.location = (6, 10, 5)


def cam_at(loc, look, name, lens=50):
    for o in list(bpy.data.objects):
        if o.name == name:
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    return cam


def render_views():
    setup_eevee()
    scene = bpy.context.scene
    # aircraft center / nose look
    fuse = bpy.data.objects.get("Fuselage")
    nose = bpy.data.objects.get("Nose")
    verts = []
    for o in (fuse, nose):
        if o:
            verts.extend(mesh_world_verts(o))
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    y_mid = 0.5 * (min(ys) + max(ys))
    z_mid = 0.5 * (min(zs) + max(zs))
    nose_look = Vector((0.0, 17.5, 0.6))
    full_look = Vector((0.0, y_mid, z_mid + 0.3))
    span = max(ys) - min(ys)

    views = {
        "oblique45": (Vector((9.0, nose_look.y + 9.0, 2.2)), nose_look, 45),
        "front": (Vector((0.0, nose_look.y + 14.0, 1.0)), nose_look, 45),
        "full_side": (Vector((span * 0.95, y_mid, z_mid + 1.0)), full_look, 40),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        cam = cam_at(loc, look, f"FinCam_{name}", lens=lens)
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
    log("=== NOSE FINISH PASS ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    nose = bpy.data.objects.get("Nose")
    glass = bpy.data.objects.get("CockpitGlass_REF")
    cabin = bpy.data.objects.get("CockpitCabin")
    if nose is None or glass is None:
        raise RuntimeError(f"missing Nose/glass nose={nose} glass={glass}")

    # 1 materials
    glass_info = ensure_glass_mat(glass)
    cabin_info = ensure_cabin(cabin)
    log(f"[1] glass {json.dumps(glass_info)}")
    log(f"[1] cabin {json.dumps(cabin_info)}")

    # 2 inventory then delete floaters
    inv = inventory_near_nose()
    with open(os.path.join(LOG, "floater_inventory_before.json"), "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, ensure_ascii=False)
    log(f"[2] inventory rows={len(inv)}")
    for r in inv:
        if set(r["flags"]) & {"edges_only", "verts_only", "wire_like", "name_match"} or (
            "thin_sheet" in r["flags"] and r["faces"] < 40
        ):
            log(f"  SUSPECT {r['name']} faces={r['faces']} edges={r['edges']} flags={r['flags']}")

    suspects, deleted = find_and_delete_floaters(inv)
    loose = clean_loose_edges_on_nose(nose)
    tip_cands = find_bright_line_strips_on_nose(nose)
    log(f"[2] tip thin-face candidates={len(tip_cands)}")

    inv_after = inventory_near_nose()
    with open(os.path.join(LOG, "floater_inventory_after.json"), "w", encoding="utf-8") as f:
        json.dump(inv_after, f, indent=2, ensure_ascii=False)

    # 3 gap strip
    strip = add_gap_fill_strip(glass, nose)

    # 4 doors
    door_report = handle_doors(nose)
    with open(os.path.join(LOG, "door_report.json"), "w", encoding="utf-8") as f:
        json.dump(door_report, f, indent=2, ensure_ascii=False, default=str)
    log(f"[4] doors {door_report.get('action')}")

    # 5 radome panel tint
    radome_info = tint_radome_panel_lines(nose)

    # hide leftovers
    for name in ("PilotSeats", "Fuselage_ORIG", "PanelLines"):
        o = bpy.data.objects.get(name)
        if o:
            hide_object(o)

    # 6 export
    if os.path.isfile(GLB):
        bak = GLB + ".bak-nose-finish"
        shutil.copy2(GLB, bak)
        log(f"backup {bak}")
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    size = os.path.getsize(GLB)
    log(f"GLB {size} ({size/1e6:.2f} MB)")

    paths = render_views()

    summary = {
        "glass": glass_info,
        "cabin": cabin_info,
        "floaters_deleted": deleted,
        "suspects": suspects,
        "loose_edges_removed": loose,
        "tip_candidates": tip_cands[:20],
        "doors": door_report,
        "radome": radome_info,
        "glb_bytes": size,
        "previews": paths,
        "gap_strip": strip.name if strip else None,
    }
    with open(os.path.join(LOG, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "NOSE_FINISH_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 机头收尾（finish）\n\n")
        f.write("## 1. 玻璃 / 驾驶舱\n")
        f.write(f"- Glass: Transmission={glass_info.get('trans')} Alpha={glass_info.get('alpha')} "
                f"IOR={glass_info.get('ior')} Rough={glass_info.get('rough')} "
                f"blend={glass_info.get('blend')} surface={glass_info.get('surface_render')}\n")
        f.write(f"- Base #DDEEEB；Cabin: {cabin_info}\n\n")
        f.write("## 2. 漂浮细线清单（删除前嫌疑）\n")
        if not suspects:
            f.write("- 未发现独立 edges-only / wire-like 物体\n")
        for s in suspects:
            f.write(f"- `{s['name']}` faces={s.get('faces')} edges={s.get('edges')} flags={s.get('flags')}\n")
        f.write(f"\n已删除: {[d['name'] for d in deleted] or '（无独立物体）'}\n")
        f.write(f"- Nose 上松散边（无面）删除: {loose}\n\n")
        f.write("## 3. 风挡上沿黑缝\n")
        f.write("- 增加 `WindshieldGapStrip`：玻璃上沿内侧暗色薄条（~3mm 内缩 + 4mm 外扩），不改玻璃外形轮廓\n\n")
        f.write("## 4. 登机门\n")
        f.write(f"- action: `{door_report.get('action')}`\n")
        f.write(f"- nose_has_door: {door_report.get('nose_has_door')} yc={door_report.get('nose_door_yc')}\n")
        f.write(f"- forward islands: {door_report.get('forward_islands')}\n")
        if door_report.get("deleted"):
            f.write(f"- 已删机身 Doors 前舱门岛: {door_report['deleted']}\n")
        f.write("\n## 5. 雷达罩板线颜色\n")
        f.write(f"- #C8CACD，赋给尖端折面 {radome_info.get('faces_assigned')} 个 faces（保留十字板线）\n\n")
        f.write("## 6. 导出\n")
        f.write(f"- GLB {size/1e6:.2f} MB；备份 `.bak-nose-finish`\n")
        f.write("- 预览 `public/models/nose-finish/{oblique45,front,full_side}.png`（EEVEE 材质）\n\n")
        f.write("## 诚实差距\n")
        f.write("- 若白线是高光/硬边而非独立网格，删除松散边后可能仍剩一点高光\n")
        f.write("- 雷达罩板线靠折面选材，不一定覆盖全部射线\n")
        f.write("- 上沿黑缝用遮挡条，不是改玻璃外形\n")
    log(f"notes -> {notes}")
    log("=== DONE ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise

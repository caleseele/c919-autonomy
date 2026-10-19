# -*- coding: utf-8 -*-
"""C919 nose polish: smooth hole rims, rebuild seals, round radome. blender -b only."""
from __future__ import annotations

import json
import math
import os
import shutil
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
NOTES = os.path.join(PROJ, "scripts", "NOSE_POLISH_PASS_NOTES.zh-Hans.md")

SEAL_W = 0.04
SEAL_INSET = 0.002  # slightly inward along -normal
GLASS_INSET = 0.004
SMOOTH_ITERS = 8
SMOOTH_ALPHA = 0.45

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def log(*a):
    print("POLISH", *a, flush=True)


def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def mkmat(name, col, rough, trans=None, alpha=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
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


def backup():
    for src, dst in (
        (GLB, GLB + ".bak-nose-polish"),
        (BLEND, BLEND + ".bak-nose-polish"),
    ):
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            log("backup", dst, os.path.getsize(dst))


def find_cut():
    for n in ("Nose_开窗", "NoseSolid", "Nose"):
        o = bpy.data.objects.get(n)
        if o and not o.hide_get() and len(o.data.polygons) > 0:
            return o
    return bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")


def boundary_loops(bm):
    used = set()
    loops = []
    for e0 in bm.edges:
        if (not e0.is_boundary) or e0.index in used:
            continue
        edges = []
        verts = []
        start = e0.verts[0]
        prev = e0.verts[0]
        nxt = e0.verts[1]
        used.add(e0.index)
        edges.append(e0)
        verts.append(start)
        guard = 0
        while nxt != start and guard < 20000:
            guard += 1
            verts.append(nxt)
            found = None
            for e in nxt.link_edges:
                if e.is_boundary and e.index not in used:
                    found = e
                    break
            if not found:
                break
            used.add(found.index)
            edges.append(found)
            prev = nxt
            nxt = found.verts[0] if found.verts[1] == prev else found.verts[1]
        if len(edges) >= 8:
            loops.append((edges, verts))
    return loops


def polish_hole_edges(cut):
    """Smooth jagged boolean rims; dissolve tiny spikes; keep holes open."""
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # dissolve very short boundary edges
    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.008]
    if short:
        bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        log("dissolved short boundary", len(short))

    # limited dissolve on near-boundary faces to kill spikes
    near = set()
    for e in bm.edges:
        if e.is_boundary:
            for f in e.link_faces:
                near.add(f)
    if near:
        bmesh.ops.dissolve_limit(
            bm,
            angle_limit=math.radians(8.0),
            use_dissolve_boundaries=False,
            verts=list({v for f in near for v in f.verts}),
            edges=list({e for f in near for e in f.edges if not e.is_boundary}),
        )
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

    # Laplacian-ish smooth on boundary verts along the loop only
    for _ in range(SMOOTH_ITERS):
        loops = boundary_loops(bm)
        # rebuild vert refs after ops — use coords buffer
        moves = {}
        for edges, verts in loops:
            n = len(verts)
            if n < 8:
                continue
            # only window-band loops (y in windshield region)
            ys = [v.co.y for v in verts]
            if max(ys) < 15.2 or min(ys) > 19.0:
                continue
            for i, v in enumerate(verts):
                a = verts[(i - 1) % n].co
                b = verts[(i + 1) % n].co
                target = (a + b) * 0.5
                moves[v.index] = v.co.lerp(target, SMOOTH_ALPHA)
        for idx, co in moves.items():
            bm.verts[idx].co = co

    # second pass: mild smooth of one-ring neighbors of boundary (keep on roughly same radial)
    bm.normal_update()
    for _ in range(3):
        bverts = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
        ring = set(bverts)
        for v in bverts:
            for e in v.link_edges:
                for ov in e.verts:
                    ring.add(ov)
        moves = {}
        for v in ring:
            if not v.link_edges:
                continue
            acc = Vector()
            cnt = 0
            for e in v.link_edges:
                ov = e.other_vert(v)
                acc += ov.co
                cnt += 1
            if cnt:
                moves[v.index] = v.co.lerp(acc / cnt, 0.25)
        for idx, co in moves.items():
            bm.verts[idx].co = co

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data)
    cut.data.update()
    n_bound = sum(1 for e in bm.edges if e.is_boundary)
    n_loops = len(boundary_loops(bm))
    bm.free()
    log("after polish boundary_edges", n_bound, "loops", n_loops)
    return n_bound, n_loops


def outer_faces_island(bm):
    """Split mesh into islands; for each, keep faces with normal aligning to island avg."""
    seen = set()
    islands = []
    for f in bm.faces:
        if f in seen:
            continue
        stack = [f]
        isl = []
        seen.add(f)
        while stack:
            cur = stack.pop()
            isl.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        islands.append(isl)
    out = []
    for isl in islands:
        n = Vector()
        c = Vector()
        a = 0.0
        for f in isl:
            ar = f.calc_area()
            n += f.normal * ar
            c += f.calc_center_median() * ar
            a += ar
        if a < 1e-9:
            continue
        n = n.normalized()
        c = c / a
        # prefer outward from body axis
        body_c = Vector((0.0, 16.5, 0.0))
        if n.dot(c - body_c) < 0:
            n = -n
        outer = [f for f in isl if f.normal.dot(n) > 0.15]
        if len(outer) < 3:
            outer = list(isl)
        out.append((outer, n, c))
    return out


def rebuild_glass_and_seals(cut):
    """Rebuild glass as single-sided outer patches + seals from their boundaries, projected to skin."""
    glass_src = bpy.data.objects.get("C919_玻璃")
    pane_names = ["WS_L", "WS_R", "SW_L", "SW_R"]
    sources = []
    for nm in pane_names:
        o = bpy.data.objects.get(nm)
        if o:
            sources.append(o)
    if not sources and glass_src:
        sources = [glass_src]

    body_bm = wbm(cut)
    body_bvh = BVHTree.FromBMesh(body_bm)

    gl = bmesh.new()
    seal = bmesh.new()
    pane_report = []

    for src in sources:
        sbm = wbm(src)
        islands = outer_faces_island(sbm)
        # if source is the combined glass, islands=4; if single pane, islands=1
        for outer, n, c in islands:
            # skip tiny
            area = sum(f.calc_area() for f in outer)
            if area < 0.02:
                continue
            # build glass faces inset
            vmap = {}
            for f in outer:
                ids = []
                for v in f.verts:
                    key = v.index
                    if key not in vmap:
                        # project slightly inward along -n, then snap to body if possible
                        p = v.co - n * GLASS_INSET
                        hit = body_bvh.ray_cast(p + n * 0.15, -n)
                        if hit[0] is not None and (hit[0] - p).length < 0.35:
                            p = hit[0] - n * GLASS_INSET
                        vmap[key] = gl.verts.new(p)
                    ids.append(vmap[key])
                try:
                    gl.faces.new(ids)
                except ValueError:
                    pass

            # boundary of outer face set
            ec = defaultdict(int)
            for f in outer:
                for e in f.edges:
                    ec[e] += 1
            bedges = [e for e, cnt in ec.items() if cnt == 1]
            created = 0
            for e in bedges:
                v0, v1 = e.verts[0].co, e.verts[1].co
                mid = (v0 + v1) * 0.5
                t = v1 - v0
                if t.length < 1e-8:
                    continue
                t.normalize()
                inward = c - mid
                inward = inward - t * inward.dot(t)
                if inward.length < 1e-8:
                    inward = n.cross(t)
                if inward.length < 1e-8:
                    continue
                inward.normalize()

                def snap(p):
                    # push slightly inward along -n then project onto body along n
                    q = p - n * SEAL_INSET
                    hit = body_bvh.ray_cast(q + n * 0.25, -n)
                    if hit[0] is not None and (hit[0] - q).length < 0.4:
                        return hit[0] - n * SEAL_INSET
                    return q

                p0 = snap(v0)
                p1 = snap(v1)
                p2 = snap(v1 + inward * SEAL_W)
                p3 = snap(v0 + inward * SEAL_W)
                try:
                    seal.faces.new([seal.verts.new(p) for p in (p0, p1, p2, p3)])
                    created += 1
                except ValueError:
                    pass
            pane_report.append(
                {
                    "src": src.name,
                    "outer_faces": len(outer),
                    "boundary": len(bedges),
                    "seal_quads": created,
                    "c": [round(c.x, 3), round(c.y, 3), round(c.z, 3)],
                    "n": [round(n.x, 3), round(n.y, 3), round(n.z, 3)],
                }
            )
            log("pane", src.name, "outer", len(outer), "bedges", len(bedges), "seals", created)
        sbm.free()

    body_bm.free()

    gmat = mkmat("C919_玻璃", (0.867, 0.933, 0.922), 0.02, 1.0, 0.3)
    smat = mkmat("C919_窗框", (0.02, 0.02, 0.02), 0.5)

    for nm, bm, mat in (("C919_玻璃", gl, gmat), ("C919_窗框", seal, smat)):
        me = bpy.data.meshes.new(nm + "_mesh")
        bm.to_mesh(me)
        nfaces = len(me.polygons)
        bm.free()
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        log(nm, "faces", nfaces)

    # ensure cabin
    cabin = bpy.data.objects.get("CockpitCabin")
    cmat = mkmat("C919_驾驶舱", (0.07, 0.07, 0.08), 0.6)
    if cabin:
        cabin.data.materials.clear()
        cabin.data.materials.append(cmat)
        cabin.hide_set(False)
        cabin.hide_render = False

    seal_ob = bpy.data.objects.get("C919_窗框")
    glass_ob = bpy.data.objects.get("C919_玻璃")
    return {
        "panes": pane_report,
        "seal_faces": len(seal_ob.data.polygons) if seal_ob else 0,
        "glass_faces": len(glass_ob.data.polygons) if glass_ob else 0,
    }


def round_radome(cut):
    """Replace blunt tip with continuous spherical radome arc along +Y."""
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table()

    tip_y = max(v.co.y for v in bm.verts)
    # choose crown ring around y where r ~ 0.55–0.75
    best = None
    for band in [i * 0.05 for i in range(4, 25)]:
        y0 = tip_y - band
        ring = [v for v in bm.verts if abs(v.co.y - y0) < 0.04]
        if len(ring) < 8:
            continue
        rs = [math.sqrt(v.co.x ** 2 + v.co.z ** 2) for v in ring]
        r_mean = sum(rs) / len(rs)
        if 0.45 <= r_mean <= 0.95:
            score = abs(r_mean - 0.65)
            if best is None or score < best[0]:
                best = (score, y0, r_mean, ring)

    if best is None:
        # fallback: ring at tip_y - 0.55
        y0 = tip_y - 0.55
        ring = [v for v in bm.verts if abs(v.co.y - y0) < 0.06]
        rs = [math.sqrt(v.co.x ** 2 + v.co.z ** 2) for v in ring] or [0.6]
        r_mean = sum(rs) / len(rs)
        best = (0, y0, r_mean, ring)

    _, y_ring, R, ring = best
    R = max(min(R, 0.85), 0.40)
    # sphere center on axis at y_ring (hemisphere extends +Y by R)
    cx, cz = 0.0, 0.0
    if ring:
        cx = sum(v.co.x for v in ring) / len(ring)
        cz = sum(v.co.z for v in ring) / len(ring)
    cy = y_ring  # equator of hemisphere
    log("radome sphere", "cy", round(cy, 3), "R", round(R, 3), "old_tip", round(tip_y, 3))

    # move all verts with y > cy - 0.05 and r < R*1.2 onto sphere (front hemisphere)
    moved = 0
    for v in bm.verts:
        dx = v.co.x - cx
        dz = v.co.z - cz
        r = math.sqrt(dx * dx + dz * dz)
        if v.co.y < cy - 0.08:
            continue
        if r > R * 1.25:
            continue
        # target on sphere: y = cy + sqrt(R^2 - r^2)
        r_clamped = min(r, R * 0.999)
        dy = math.sqrt(max(0.0, R * R - r_clamped * r_clamped))
        target_y = cy + dy
        # blend based on how far past equator
        t = min(1.0, max(0.0, (v.co.y - (cy - 0.08)) / (R + 0.08)))
        t = t * t * (3 - 2 * t)  # smoothstep
        new_y = v.co.y * (1 - t) + target_y * t
        # also gently pull radial to sphere if beyond
        if r > 1e-6 and r > R * 0.98:
            scale = (R * 0.98) / r
            scale = 1.0 + (scale - 1.0) * t
            v.co.x = cx + dx * scale
            v.co.z = cz + dz * scale
        v.co.y = new_y
        moved += 1

    # remove spike verts that are isolated past the sphere tip
    sphere_tip = cy + R
    for v in bm.verts:
        if v.co.y > sphere_tip + 0.02:
            dx = v.co.x - cx
            dz = v.co.z - cz
            r = math.sqrt(dx * dx + dz * dz)
            r_clamped = min(r, R * 0.999)
            v.co.y = cy + math.sqrt(max(0.0, R * R - r_clamped * r_clamped))
            moved += 1

    # mild smooth of tip region
    tip_verts = [v for v in bm.verts if v.co.y > cy]
    for _ in range(4):
        moves = {}
        for v in tip_verts:
            if not v.link_edges:
                continue
            acc = Vector()
            cnt = 0
            for e in v.link_edges:
                ov = e.other_vert(v)
                if ov.co.y > cy - 0.15:
                    acc += ov.co
                    cnt += 1
            if cnt:
                # keep roughly on sphere
                mid = acc / cnt
                dx = mid.x - cx
                dz = mid.z - cz
                r = math.sqrt(dx * dx + dz * dz)
                r_clamped = min(r, R * 0.999)
                target = Vector((mid.x, cy + math.sqrt(max(0.0, R * R - r_clamped * r_clamped)), mid.z))
                moves[v.index] = v.co.lerp(target, 0.35)
        for idx, co in moves.items():
            bm.verts[idx].co = co

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data)
    cut.data.update()
    new_tip = max(v.co.y for v in bm.verts)
    bm.free()
    log("radome moved", moved, "new_tip_y", round(new_tip, 3), "sphere_tip", round(cy + R, 3))
    return {"cy": cy, "R": R, "old_tip": tip_y, "new_tip": new_tip, "moved": moved}


def hole_check(obj):
    bm = wbm(obj)
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
    open_n = 0
    for name, p in samples.items():
        if name == "tip":
            origin = p + Vector((0, 1.5, 0))
            direc = Vector((0, -1, 0))
        else:
            radial = Vector((p.x, 0, p.z))
            radial.normalize()
            origin = p + radial * 1.2
            direc = -radial
        hit = bvh.ray_cast(origin, direc)
        if hit[0] is None:
            status = "OPEN"
        else:
            dist = (hit[0] - origin).length
            status = "SOLID" if dist < 0.85 else "OPEN"
        out[name] = status
        if name.startswith("W") or name.startswith("S"):
            if status == "OPEN":
                open_n += 1
        log("check", name, status)
    out["_open_windows"] = open_n
    out["faces"] = len(bm.faces)
    out["boundary"] = sum(1 for e in bm.edges if e.is_boundary)
    tip_y = max(v.co.y for v in bm.verts)
    tip_verts = [v for v in bm.verts if v.co.y > tip_y - 0.08]
    rs = [math.sqrt(v.co.x ** 2 + v.co.z ** 2) for v in tip_verts]
    out["tip_y"] = tip_y
    out["tip_r_mean"] = sum(rs) / len(rs) if rs else None
    out["tip_r_max"] = max(rs) if rs else None
    bm.free()
    return out


def setup_cam():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    cam = bpy.data.objects.get("NoseFixCam")
    if not cam:
        cd = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cd)
        bpy.context.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render_views(prefix):
    cam = setup_cam()
    tip = Vector((0, 19.9, 0.55))
    hide_names = {
        "Nose", "NoseSolid", "CockpitFrames", "WindshieldWipers", "PanelLines",
        "REF_玻璃",
    }
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        hide = (
            o.name in hide_names
            or "2-287" in o.name
            or o.name.startswith("切割")
            or o.name.startswith("WS_")
            or o.name.startswith("SW_")
        )
        o.hide_render = hide
        try:
            o.hide_set(hide)
        except Exception:
            pass
    cut = find_cut()
    if cut:
        cut.hide_render = False
        try:
            cut.hide_set(False)
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


def hide_helpers():
    for o in bpy.data.objects:
        if (
            o.name.startswith("切割")
            or o.name.startswith("WS_")
            or o.name.startswith("SW_")
            or "2-287" in o.name
            or o.name in ("CockpitFrames", "WindshieldWipers", "PanelLines", "REF_玻璃", "NoseSolid", "Nose")
        ):
            o.hide_set(True)
            o.hide_render = True
    cut = find_cut()
    if cut and cut.name != "Nose":
        cut.hide_set(False)
        cut.hide_render = False
    for nm in ("C919_玻璃", "C919_窗框", "CockpitCabin", "Fuselage"):
        o = bpy.data.objects.get(nm)
        if o:
            o.hide_set(False)
            o.hide_render = False


def main():
    backup()
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    cut = find_cut()
    if not cut:
        raise RuntimeError("no cut body")
    log("cut body", cut.name, "faces", len(cut.data.polygons))

    log("===== EDGE POLISH =====")
    be, nl = polish_hole_edges(cut)
    render_views("polish_edges")

    log("===== SEALS =====")
    seal_info = rebuild_glass_and_seals(cut)
    render_views("polish_seals")

    log("===== RADOME =====")
    rad = round_radome(cut)
    # re-polish edges lightly after radome (tip may share topology)
    polish_hole_edges(cut)
    render_views("polish_radome")

    log("===== FINAL =====")
    hide_helpers()
    checks = hole_check(cut)
    render_views("polish_final")

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB)
    log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    report = {
        "glb_bytes": size,
        "seal_faces": seal_info["seal_faces"],
        "glass_faces": seal_info["glass_faces"],
        "seal_panes": seal_info["panes"],
        "boundary_edges": be,
        "boundary_loops": nl,
        "holes": checks,
        "radome": rad,
    }
    with open(os.path.join(LOG_DIR, "polish_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    missing = []
    if seal_info["seal_faces"] <= 0:
        missing.append("seals still 0 faces")
    if checks.get("_open_windows", 0) < 4:
        missing.append(f"windows OPEN count={checks.get('_open_windows')}")
    if checks.get("tip_r_mean", 1) and checks["tip_r_mean"] > 0.25:
        missing.append(f"tip still blunt r_mean={checks['tip_r_mean']:.3f}")
    if size > 2.5 * 1024 * 1024:
        missing.append("GLB > 2.5MB")

    with open(NOTES, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `{cut.name}`

## Done
1. Hole-edge polish: dissolve short boundary (<8mm), limited dissolve 8°, loop Laplacian x{SMOOTH_ITERS}
2. Seals rebuilt from WS/SW **outer faces** (panes are closed thin solids → island boundary was 0)
   - width {SEAL_W}m, inset {SEAL_INSET}m, BVH-projected onto skin
   - seal faces: **{seal_info['seal_faces']}**
3. Radome: spherical remapping R={rad['R']:.3f} m, cy={rad['cy']:.3f} → tip {rad['old_tip']:.3f}→{rad['new_tip']:.3f}
4. Glass rebuilt single-sided outer, Transmission #DDEEEB Alpha 0.3
5. Helpers hidden; GLB use_visible=True

## Checks
- holes: {json.dumps(checks, ensure_ascii=False)}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING ({len(missing)})
"""
            + ("\n".join(f"- {m}" for m in missing) if missing else "- none critical")
            + "\n"
        )
    log("DONE", size, "seals", seal_info["seal_faces"], "open_win", checks.get("_open_windows"), "missing", missing)


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""C919 nose fix pipeline Steps 2–6. blender -b only. No knife_project."""
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
WORK_BLEND = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
GLB_OUT = os.path.join(PROJ, "public", "models", "c919.glb")
BLEND_OUT = os.path.join(PROJ, "public", "models", "c919.blend")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

BODY_NAME = "Nose"
FORWARD = Vector((0.0, 1.0, 0.0))  # Soft: tip +Y; front glass outward ~+Y
ONLY_FRONT = False
CUT_DEPTH = 0.25
GLASS_INSET = 0.004
SEAL_WIDTH = 0.04
FRONT_DOT = 0.25

# Soft ↔ REF meters alignment (from Step1 AABB)
SOFT_TIP_Y = 20.0324
REF_TIP_Y = 19.41858
REF_Z_MIN = 0.0
REF_Z_MAX = 12.13363
# Soft fuselage axis Z=0; REF belly at 0 includes gear — cabin center ~4.1 from prior audit
REF_Z_CENTER = 4.11


def log(*a):
    print("NOSEFIX", *a, flush=True)


def get_obj(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise RuntimeError("missing object: " + name)
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


def face_islands(bm, faces=None):
    pool = list(faces) if faces is not None else list(bm.faces)
    seen, islands = set(), []
    for f in pool:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen and nb in seen or True:
                        if nb not in seen and (faces is None or nb in faces or nb in set(pool)):
                            if faces is None or nb in set(pool):
                                seen.add(nb)
                                stack.append(nb)
        islands.append(island)
    return islands


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


def nose_tip():
    nose = get_obj(BODY_NAME)
    corners = [nose.matrix_world @ Vector(c) for c in nose.bound_box]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    xs = [c.x for c in corners]
    return Vector((0.5 * (min(xs) + max(xs)), max(ys) - 0.2, 0.55))


def render_views(prefix, hide_names=None, only_names=None):
    cam = setup_cam()
    tip = nose_tip()
    saved = {}
    for o in bpy.data.objects:
        if o.type not in {"MESH", "CURVE", "EMPTY"}:
            continue
        saved[o.name] = (o.hide_render, getattr(o, "hide_viewport", False), o.hide_get())
        show = True
        if only_names is not None:
            show = o.name in only_names
        if hide_names and o.name in hide_names:
            show = False
        if o.name == cam.name:
            show = True
        o.hide_render = not show
        try:
            o.hide_viewport = not show
        except Exception:
            pass
        try:
            o.hide_set(not show)
        except Exception:
            pass

    shots = [
        ("front", tip + Vector((0, 6.2, 0.35)), tip, 55),
        ("side", tip + Vector((7.2, -1.2, 0.7)), tip, 50),
        ("45", tip + Vector((4.8, 4.2, 1.4)), tip, 50),
    ]
    paths = []
    for tag, eye, tgt, lens in shots:
        aim_cam(cam, eye, tgt, lens)
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("render", fp)
        paths.append(fp)

    for name, (hr, hv, hg) in saved.items():
        o = bpy.data.objects.get(name)
        if not o:
            continue
        o.hide_render = hr
        try:
            o.hide_viewport = hv
        except Exception:
            pass
        try:
            o.hide_set(hg)
        except Exception:
            pass
    return paths


def ref_to_soft(co):
    """Map REF meters world → Soft fuselage frame (approx)."""
    x, y, z = co.x, co.y, co.z
    sy = y + (SOFT_TIP_Y - REF_TIP_Y)
    sz = z - REF_Z_CENTER
    return Vector((x, sy, sz))


def soft_to_ref_dir():
    return None


# ---------- Step 2: outlines → patches ----------

def walk_boundary_loops(bm, edge_filter):
    unused = set(e for e in bm.edges if e.is_boundary and edge_filter(e))
    loops = []
    while unused:
        start = unused.pop()
        loop_edges = [start]
        # grow
        changed = True
        while changed:
            changed = False
            verts = set()
            for e in loop_edges:
                verts.add(e.verts[0])
                verts.add(e.verts[1])
            for e in list(unused):
                if e.verts[0] in verts or e.verts[1] in verts:
                    unused.remove(e)
                    loop_edges.append(e)
                    changed = True
        # order as polyline
        from collections import defaultdict as dd
        adj = dd(list)
        for e in loop_edges:
            adj[e.verts[0]].append(e.verts[1])
            adj[e.verts[1]].append(e.verts[0])
        if not adj:
            continue
        # start at endpoint if open, else arbitrary
        ends = [v for v, nbs in adj.items() if len(nbs) == 1]
        cur = ends[0] if ends else next(iter(adj))
        ordered = [cur]
        prev = None
        while True:
            nbs = [n for n in adj[cur] if n != prev]
            if not nbs:
                break
            nxt = nbs[0]
            ordered.append(nxt)
            prev, cur = cur, nxt
            if cur == ordered[0] and len(ordered) > 2:
                break
            if len(ordered) > len(loop_edges) + 2:
                break
        loops.append(ordered)
    return loops


def probe_ref_outlines(ref):
    """Return list of soft-space closed polylines (list of Vector) for up to 4 windows."""
    bm = world_bmesh(ref)
    report = {"material_islands": [], "boundary_loops": []}

    # (a) material faces in nose belt
    me = ref.data
    mat_faces = defaultdict(list)
    for f in bm.faces:
        c = f.calc_center_median()
        # REF space nose upper
        if c.y < 8.0 and c.z > 3.5:
            mat_faces[f.material_index].append(f)

    for mi, faces in mat_faces.items():
        islands = face_islands_set(set(faces))
        name = me.materials[mi].name if mi < len(me.materials) and me.materials[mi] else str(mi)
        for isl in islands:
            n, c = island_normal_center(isl)
            area = sum(f.calc_area() for f in isl)
            report["material_islands"].append(
                {
                    "mat": name,
                    "faces": len(isl),
                    "area": area,
                    "center_ref": list(c),
                    "normal_ref": list(n),
                }
            )

    # Prefer boundary loops of openings in nose upper (authentic window holes)
    def edge_ok(e):
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        return mid.y < 7.0 and mid.z > 3.2

    loops = walk_boundary_loops(bm, edge_ok)
    soft_loops = []
    for loop in loops:
        if len(loop) < 6:
            continue
        pts = [ref_to_soft(v.co.copy()) for v in loop]
        # close
        if (pts[0] - pts[-1]).length > 1e-4:
            pts.append(pts[0].copy())
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        zs = [p.z for p in pts]
        info = {
            "n": len(pts),
            "x": [min(xs), max(xs)],
            "y": [min(ys), max(ys)],
            "z": [min(zs), max(zs)],
            "cx": sum(xs) / len(xs),
            "cy": sum(ys) / len(ys),
            "cz": sum(zs) / len(zs),
        }
        report["boundary_loops"].append(info)
        # filter to Soft windshield belt
        if info["y"][1] < 14.5 or info["y"][0] > 19.5:
            continue
        if info["z"][1] < 0.2 or info["z"][0] > 2.2:
            continue
        # size: pane-like
        dy = info["y"][1] - info["y"][0]
        dz = info["z"][1] - info["z"][0]
        dx = info["x"][1] - info["x"][0]
        if max(dx, dy, dz) < 0.25 or max(dx, dy, dz) > 4.0:
            continue
        soft_loops.append(pts)

    bm.free()

    # Deduplicate / pick best 4: 2 front (high Y, small |x| span across center) + 2 side
    soft_loops.sort(key=lambda pts: -sum(p.y for p in pts) / len(pts))

    # Cluster by side and front/aft
    def classify(pts):
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        dx = max(p.x for p in pts) - min(p.x for p in pts)
        dy = max(p.y for p in pts) - min(p.y for p in pts)
        is_front = cy > 16.8 and dx > dy * 0.6
        side = "R" if cx >= 0 else "L"
        kind = "WS" if is_front or cy > 17.0 else "SW"
        return kind, side, cy, abs(cx)

    scored = []
    for pts in soft_loops:
        kind, side, cy, ax = classify(pts)
        scored.append((kind, side, cy, ax, pts))

    chosen = {}
    for kind, side, cy, ax, pts in scored:
        key = f"{kind}_{side}"
        if key not in chosen:
            chosen[key] = pts
        if len(chosen) >= 4:
            break
    # If not 4 keys, take largest 4 loops by area proxy
    if len(chosen) < 4:
        soft_loops.sort(
            key=lambda pts: -(
                (max(p.x for p in pts) - min(p.x for p in pts))
                * (max(p.z for p in pts) - min(p.z for p in pts))
            )
        )
        chosen = {f"P_{i}": soft_loops[i] for i in range(min(4, len(soft_loops)))}

    return list(chosen.values()), report, list(chosen.keys())


def use_existing_ws_panes():
    names = ["WS_L", "WS_R", "SW_L", "SW_R"]
    objs = [bpy.data.objects.get(n) for n in names]
    if any(o is None or o.type != "MESH" for o in objs):
        return None
    return objs


def raycast_loop_to_body(loop_pts, bvh, body_center):
    """Project each outline point onto Nose surface along inward/outward normals."""
    projected = []
    for p in loop_pts:
        # cast from outside toward center
        outward = (p - body_center)
        if outward.length < 1e-6:
            outward = Vector((0, 0, 1))
        outward.normalize()
        # start outside, cast inward
        origin = p + outward * 0.8
        hit = bvh.ray_cast(origin, -outward)
        if hit[0] is None:
            # try opposite
            hit = bvh.ray_cast(p - outward * 0.8, outward)
        if hit[0] is None:
            # try from +normal of approximate
            for d in (
                Vector((0, 0, 1)),
                Vector((0, 0, -1)),
                Vector((1, 0, 0)),
                Vector((-1, 0, 0)),
                Vector((0, 1, 0)),
                Vector((0, -1, 0)),
            ):
                hit = bvh.ray_cast(p + d * 1.2, -d)
                if hit[0] is not None:
                    break
        if hit[0] is None:
            projected.append(p.copy())
        else:
            projected.append(hit[0].copy())
    return projected


def make_patch_from_loop(name, pts):
    """Create a mesh face fan / grid from a closed projected loop."""
    if len(pts) < 3:
        return None
    # drop duplicate close
    clean = [pts[0]]
    for p in pts[1:]:
        if (p - clean[-1]).length > 1e-4:
            clean.append(p)
    if len(clean) > 2 and (clean[0] - clean[-1]).length < 1e-4:
        clean = clean[:-1]
    if len(clean) < 3:
        return None

    bm = bmesh.new()
    verts = [bm.verts.new(p) for p in clean]
    bm.verts.ensure_lookup_table()
    # center
    c = sum((v.co for v in verts), Vector()) / len(verts)
    cv = bm.verts.new(c)
    faces = []
    for i in range(len(verts)):
        a = verts[i]
        b = verts[(i + 1) % len(verts)]
        try:
            faces.append(bm.faces.new([a, b, cv]))
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # ensure outward-ish (+away from soft center)
    body_c = Vector((0, 16.5, 0))
    for f in list(bm.faces):
        if f.normal.dot(f.calc_center_median() - body_c) < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def join_meshes(name, objs):
    """Join mesh objects into one; returns new object. Hides sources."""
    if not objs:
        return None
    bm = bmesh.new()
    for ob in objs:
        wbm = world_bmesh(ob)
        # append
        vmap = {}
        for v in wbm.verts:
            vmap[v] = bm.verts.new(v.co)
        bm.verts.ensure_lookup_table()
        for f in wbm.faces:
            try:
                bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
        wbm.free()
        ob.hide_set(True)
        ob.hide_render = True
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def step2():
    log("===== STEP2 outlines → patches =====")
    body = get_obj(BODY_NAME)
    ref = None
    for o in bpy.data.objects:
        if "2-287" in o.name:
            ref = o
            break

    outline_source = None
    patches = []
    report = {}

    # (a) REF
    if ref is not None:
        loops, report, keys = probe_ref_outlines(ref)
        log("REF loops chosen", len(loops), keys)
        log("REF material island count", len(report.get("material_islands", [])))
        log("REF boundary loop candidates", len(report.get("boundary_loops", [])))
        with open(os.path.join(LOG_DIR, "step2_ref_probe.json"), "w", encoding="utf-8") as f:
            json.dump({"keys": keys, "n_loops": len(loops), "report": report}, f, ensure_ascii=False, indent=2)

        # Check if material islands gave 4 windshield-sized regions
        good_mats = [
            m
            for m in report.get("material_islands", [])
            if 0.05 < m["area"] < 3.0 and 8 < m["faces"] < 5000
        ]
        log("good_mat_islands", len(good_mats), good_mats[:8])

        if len(loops) >= 4:
            # BVH of body
            bbm = world_bmesh(body)
            bvh = BVHTree.FromBMesh(bbm)
            body_center = sum((Vector(c) for c in body.bound_box), Vector()) / 8.0
            body_center = body.matrix_world @ body_center
            for i, loop in enumerate(loops[:4]):
                proj = raycast_loop_to_body(loop, bvh, body_center)
                ob = make_patch_from_loop(f"WS_Patch_{i}", proj)
                if ob:
                    patches.append(ob)
                    log("patch", i, "verts", len(ob.data.vertices))
            bbm.free()
            if len(patches) >= 4:
                outline_source = "a_ref_boundary_loops"
            else:
                for p in patches:
                    bpy.data.objects.remove(p, do_unlink=True)
                patches = []

    # (b) WindowOutline
    if not patches:
        outlines = [
            o
            for o in bpy.data.objects
            if "windowoutline" in o.name.lower() or "窗户轮廓" in o.name
        ]
        log("WindowOutline objects", [o.name for o in outlines])
        if outlines:
            outline_source = "b_windowoutline"
            # parse mesh faces as loops
            body = get_obj(BODY_NAME)
            bbm = world_bmesh(body)
            bvh = BVHTree.FromBMesh(bbm)
            body_center = body.matrix_world @ (
                sum((Vector(c) for c in body.bound_box), Vector()) / 8.0
            )
            idx = 0
            for o in outlines:
                if o.type != "MESH":
                    continue
                wbm = world_bmesh(o)
                for f in wbm.faces:
                    loop = [v.co.copy() for v in f.verts]
                    loop.append(loop[0].copy())
                    proj = raycast_loop_to_body(loop, bvh, body_center)
                    ob = make_patch_from_loop(f"WS_Patch_{idx}", proj)
                    if ob:
                        patches.append(ob)
                        idx += 1
                wbm.free()
            bbm.free()
            if len(patches) < 4:
                log("WindowOutline yielded", len(patches), "<4")
                for p in patches:
                    bpy.data.objects.remove(p, do_unlink=True)
                patches = []
                outline_source = None

    # Fallback: existing Soft WS_*/SW_* panes (REF-derived soft_y, already on skin)
    if not patches:
        existing = use_existing_ws_panes()
        if existing:
            outline_source = "fallback_existing_WS_SW_panes_ref_derived"
            # They are already surface patches — join as glass source
            glass = join_meshes("REF_玻璃", existing)
            patches = [glass]
            log("using existing WS_L/R SW_L/R as REF_玻璃")
        else:
            log("STOP: no outline source")
            with open(os.path.join(LOG_DIR, "STEP2_STOP.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "stop": True,
                        "reason": "No REF windshield material islands forming 4 panes; "
                        "WindowOutline absent from blend; WS_*/SW_* missing.",
                        "ref_probe": report,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return None, "STOP"

    if outline_source != "fallback_existing_WS_SW_panes_ref_derived":
        glass = join_meshes("REF_玻璃", patches)
    else:
        glass = patches[0]

    glass.name = "REF_玻璃"
    log("STEP2 outline_source", outline_source, "glass faces", len(glass.data.polygons))
    with open(os.path.join(LOG_DIR, "step2_result.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "outline_source": outline_source,
                "glass_name": glass.name,
                "faces": len(glass.data.polygons),
                "verts": len(glass.data.vertices),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # show patches, hide heavy REF for clarity
    hide = []
    for o in bpy.data.objects:
        if "2-287" in o.name:
            hide.append(o.name)
    render_views("step2_patches", hide_names=hide)
    return glass, outline_source


# ---------- Step 3: boolean cut (user method) ----------

def make_cutter(island, normal, name, coll):
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
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.display_type = "WIRE"
    return ob


def step3(glass):
    log("===== STEP3 boolean cut =====")
    body = get_obj(BODY_NAME)
    gbm = world_bmesh(glass)
    islands = face_islands_set(set(gbm.faces))
    # If fan-triangulated single mesh, islands may be 1 connected — split by normal clusters
    if len(islands) == 1 and len(gbm.faces) > 4:
        # re-cluster by face normal buckets (front L/R, side L/R)
        buckets = {"WS_L": [], "WS_R": [], "SW_L": [], "SW_R": []}
        for f in gbm.faces:
            c = f.calc_center_median()
            n = f.normal.normalized()
            if abs(n.y) > abs(n.x) and c.y > 16.5:
                key = "WS_R" if c.x >= 0 else "WS_L"
            else:
                key = "SW_R" if c.x >= 0 else "SW_L"
            buckets[key].append(f)
        islands = [b for b in buckets.values() if b]
        log("reclustered islands", len(islands), {k: len(v) for k, v in buckets.items()})

    body_center = body.matrix_world @ (
        sum((Vector(b) for b in body.bound_box), Vector()) / 8.0
    )
    fwd = FORWARD.normalized()

    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    panes = []
    for i, isl in enumerate(islands):
        n, c = island_normal_center(isl)
        if n.length < 0.5:
            log("skip island", i, "degenerate normal")
            continue
        if n.dot(c - body_center) < 0:
            n = -n
        is_front = n.dot(fwd) > FRONT_DOT
        panes.append((isl, n, c, is_front))
        log(
            "pane",
            i,
            "faces",
            len(isl),
            "n",
            tuple(round(x, 3) for x in n),
            "front" if is_front else "side",
        )

    targets = [p for p in panes if p[3] or not ONLY_FRONT]
    if not targets:
        raise RuntimeError("no panes to cut")

    for i, (isl, n, c, _) in enumerate(targets):
        make_cutter(isl, n, "切割体_%d" % i, coll)

    new_body = body.copy()
    new_body.data = body.data.copy()
    new_body.name = body.name + "_开窗"
    for uc in body.users_collection:
        uc.objects.link(new_body)

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

    gbm.free()
    log("cut body", new_body.name, "faces", len(new_body.data.polygons))
    # hide glass source for hole visibility
    glass.hide_set(True)
    glass.hide_render = True
    for n in ("WS_L", "WS_R", "SW_L", "SW_R", "CockpitFrames"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    hide = [o.name for o in bpy.data.objects if "2-287" in o.name]
    render_views("step3_cut", hide_names=hide + ["REF_玻璃"])
    return new_body, panes, targets


# ---------- Step 4: glass, seals, cabin ----------

def glass_material():
    mat = bpy.data.materials.get("C919_玻璃") or bpy.data.materials.new("C919_玻璃")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

    def setin(names, val):
        for nm in names:
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = val
                return

    setin(["Base Color"], (0.867, 0.933, 0.922, 1.0))  # #DDEEEB
    setin(["Roughness"], 0.02)
    setin(["IOR"], 1.5)
    setin(["Transmission Weight", "Transmission"], 1.0)
    setin(["Alpha"], 0.3)
    for attr, val in (
        ("surface_render_method", "BLENDED"),
        ("blend_method", "BLEND"),
        ("use_raytrace_refraction", True),
        ("use_screen_refraction", True),
    ):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat


def seal_material():
    mat = bpy.data.materials.get("C919_窗框") or bpy.data.materials.new("C919_窗框")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def cabin_material():
    mat = bpy.data.materials.get("C919_驾驶舱") or bpy.data.materials.new("C919_驾驶舱")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.6
    return mat


def step4(panes, targets):
    log("===== STEP4 glass / seals / cabin =====")
    # Glass from all panes (not only cut targets), inset
    gl_bm = bmesh.new()
    for isl, n, c, _ in panes:
        vmap = {}
        for f in isl:
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
    old = bpy.data.objects.get("C919_玻璃")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    gob = bpy.data.objects.new("C919_玻璃", me)
    bpy.context.collection.objects.link(gob)
    gob.data.materials.append(glass_material())

    # Seals: rim strips along each pane boundary, inset slightly
    seal_bm = bmesh.new()
    for isl, n, c, _ in targets:
        # boundary edges of island
        edge_count = defaultdict(int)
        for f in isl:
            for e in f.edges:
                edge_count[e] += 1
        boundary = [e for e, k in edge_count.items() if k == 1]
        # for each boundary edge, make a thin quad inward along -n and toward face center
        for e in boundary:
            v0, v1 = e.verts[0].co, e.verts[1].co
            mid = (v0 + v1) * 0.5
            # inward in plane: toward island center projected
            tangent = (v1 - v0).normalized()
            inward = (c - mid)
            inward = inward - tangent * inward.dot(tangent)
            if inward.length < 1e-6:
                inward = n.cross(tangent)
            inward.normalize()
            # flush/slightly in: base on surface - tiny n, strip width SEAL_WIDTH toward center
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
    sold = bpy.data.objects.get("C919_窗框")
    if sold:
        bpy.data.objects.remove(sold, do_unlink=True)
    sob = bpy.data.objects.new("C919_窗框", sme)
    bpy.context.collection.objects.link(sob)
    sob.data.materials.append(seal_material())

    # Cabin box behind glass (reuse CockpitCabin if present — update mat; else create)
    cabin = bpy.data.objects.get("CockpitCabin")
    if cabin is None:
        # closed box covering windshield belt interior
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        # scale/place: x±1.4, y 15.8–17.6, z -0.2–1.4
        for v in bm.verts:
            v.co.x *= 2.6
            v.co.y *= 1.6
            v.co.z *= 1.5
            v.co += Vector((0, 16.7, 0.55))
        me = bpy.data.meshes.new("CockpitCabin")
        bm.to_mesh(me)
        bm.free()
        cabin = bpy.data.objects.new("CockpitCabin", me)
        bpy.context.collection.objects.link(cabin)
    cabin.data.materials.clear()
    cabin.data.materials.append(cabin_material())
    cabin.hide_set(False)
    cabin.hide_render = False

    # Hide old frames that looked like floating lines
    for n in ("CockpitFrames", "WindshieldWipers"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_set(True)
            o.hide_render = True

    hide = [o.name for o in bpy.data.objects if "2-287" in o.name]
    hide += ["REF_玻璃", "Nose"]
    render_views("step4_glass", hide_names=hide)
    return gob, sob, cabin


# ---------- Step 5: round radome tip ----------

def step5(cut_body):
    log("===== STEP5 radome tip =====")
    bm = bmesh.new()
    bm.from_mesh(cut_body.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Find tip: max local Y (Nose is already in soft space; matrix may be identity)
    # Work in object local; assume location applied-ish — use world via matrix
    mw = cut_body.matrix_world
    mwi = mw.inverted()

    def wy(v):
        return (mw @ v.co).y

    tip_y = max(wy(v) for v in bm.verts)
    # Faces whose center is near tip and nearly facing +Y (flat disk)
    flat_faces = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = (mw.to_3x3() @ f.normal).normalized()
        if c.y > tip_y - 0.08 and n.dot(Vector((0, 1, 0))) > 0.85:
            flat_faces.append(f)
    log("flat tip faces", len(flat_faces), "tip_y", tip_y)

    if flat_faces:
        # boundary of deleted region
        bmesh.ops.delete(bm, geom=flat_faces, context="FACES")
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

    # Find open boundary loop nearest tip
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    # cluster tip-near boundary
    tip_edges = []
    for e in boundary_edges:
        mid = mw @ ((e.verts[0].co + e.verts[1].co) * 0.5)
        if mid.y > tip_y - 0.35:
            tip_edges.append(e)
    log("tip boundary edges", len(tip_edges))

    if tip_edges:
        # grid fill / edgenet fill
        try:
            ret = bmesh.ops.holes_fill(bm, edges=tip_edges, sides=0)
            log("holes_fill faces", len(ret.get("faces", [])))
        except Exception as e:
            log("holes_fill failed", e)
            try:
                bmesh.ops.edgenet_fill(bm, edges=tip_edges)
            except Exception as e2:
                log("edgenet_fill failed", e2)

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        # Find center-ish vert of tip fill: highest Y after fill among tip
        tip_verts = [v for v in bm.verts if wy(v) > tip_y - 0.4]
        if tip_verts:
            # geometric center of tip ring (boundary verts at tip)
            ring = []
            for e in bm.edges:
                if e.is_boundary:
                    mid = mw @ ((e.verts[0].co + e.verts[1].co) * 0.5)
                    if mid.y > tip_y - 0.5:
                        ring.extend(list(e.verts))
            ring = list(set(ring))
            if len(ring) >= 3:
                cen_world = sum((mw @ v.co for v in ring), Vector()) / len(ring)
                # push a pole: either existing center vert or new
                # find vert closest to axis at tip
                axis = Vector((0, tip_y, 0.0))  # soft tip on Y
                # use mean Z of ring for droop
                mean_z = sum((mw @ v.co).z for v in ring) / len(ring)
                mean_x = sum((mw @ v.co).x for v in ring) / len(ring)
                # target pole slightly forward of ring mean Y
                ring_y = sum((mw @ v.co).y for v in ring) / len(ring)
                # radius of ring
                radii = [
                    math.sqrt((mw @ v.co).x ** 2 + ((mw @ v.co).z - mean_z) ** 2)
                    for v in ring
                ]
                R = sum(radii) / max(len(radii), 1)
                # hemisphere: push forward by ~0.55*R for rounded radome
                pole_y = ring_y + max(0.12, 0.55 * R)
                pole_world = Vector((mean_x, pole_y, mean_z))
                # find filled face verts interior (not on ring)
                ring_set = set(ring)
                inner = [v for v in tip_verts if v not in ring_set]
                if not inner:
                    # collapse: create pole and connect — poke fill faces
                    # simpler: move the highest-Y vert
                    pole = max(tip_verts, key=wy)
                    pole.co = mwi @ pole_world
                else:
                    # move centroid of inner verts to pole; smooth others
                    for v in inner:
                        vw = mw @ v.co
                        # blend toward pole based on radial factor
                        r = math.sqrt(vw.x ** 2 + (vw.z - mean_z) ** 2)
                        t = 1.0 - min(1.0, r / max(R, 1e-6))
                        # spherical: y = ring_y + sqrt(R^2 - r^2)*0.9 approx
                        sphere_dy = math.sqrt(max(0.0, R * R - r * r)) * 0.85
                        target = Vector((vw.x, ring_y + sphere_dy, vw.z))
                        v.co = mwi @ target
                    # ensure one tip at pole
                    best = max(inner, key=wy)
                    best.co = mwi @ pole_world

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut_body.data)
    cut_body.data.update()
    bm.free()
    log("radome done faces", len(cut_body.data.polygons))

    hide = [o.name for o in bpy.data.objects if "2-287" in o.name]
    hide += ["REF_玻璃", "Nose"]
    render_views("step5_radome", hide_names=hide)
    return cut_body


# ---------- Step 6: cleanup + export ----------

def step6(cut_body):
    log("===== STEP6 cleanup + export =====")
    # Delete / hide helpers
    kill_prefixes = ("切割体_", "WindowOutline", "窗户轮廓", "WS_Patch_")
    kill_exact = {"REF_玻璃"}
    for o in list(bpy.data.objects):
        if o.name in kill_exact or any(o.name.startswith(p) for p in kill_prefixes):
            bpy.data.objects.remove(o, do_unlink=True)
            log("deleted", o.name)
        elif "2-287" in o.name or o.name in ("Cube",):
            o.hide_set(True)
            o.hide_render = True
            o.hide_viewport = True
            log("hidden REF", o.name)

    # Hide original Nose (uncut)
    nose = bpy.data.objects.get("Nose")
    if nose and nose != cut_body:
        nose.hide_set(True)
        nose.hide_render = True

    # Ensure cut body visible
    cut_body.hide_set(False)
    cut_body.hide_render = False
    cut_body.hide_viewport = False

    # Hide cutter collection
    coll = bpy.data.collections.get("风挡切割体")
    if coll:
        coll.hide_viewport = True
        coll.hide_render = True
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)

    # Rename cut body for clarity (keep Nose_开窗)
    # Export GLB visible only
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    bpy.ops.export_scene.gltf(
        filepath=GLB_OUT,
        export_format="GLB",
        use_visible=True,
        export_apply=True,
    )
    size = os.path.getsize(GLB_OUT) if os.path.isfile(GLB_OUT) else -1
    log("exported", GLB_OUT, "bytes", size)

    hide = [o.name for o in bpy.data.objects if "2-287" in o.name]
    render_views("step6_final", hide_names=hide)

    # REF comparison if present
    ref = next((o for o in bpy.data.objects if "2-287" in o.name), None)
    if ref:
        # Align camera still to Soft tip; show REF alone may be black if misaligned —
        # temporarily move cam toward REF tip
        cam = setup_cam()
        ref.hide_set(False)
        ref.hide_render = False
        try:
            ref.display_type = "SOLID"
        except Exception:
            pass
        # REF tip world
        corners = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
        tip = Vector(
            (
                0.5 * (min(c.x for c in corners) + max(c.x for c in corners)),
                max(c.y for c in corners) - 0.5,
                min(c.z for c in corners) + 5.5,
            )
        )
        only = [ref.name]
        # custom shots for REF scale
        saved = {}
        for o in bpy.data.objects:
            if o.type not in {"MESH", "CURVE", "EMPTY"}:
                continue
            saved[o.name] = (o.hide_render, o.hide_get())
            show = o.name == ref.name
            o.hide_render = not show
            try:
                o.hide_set(not show)
            except Exception:
                pass
        shots = [
            ("front", tip + Vector((0, 14, 1)), tip, 40),
            ("side", tip + Vector((16, -2, 2)), tip, 40),
            ("45", tip + Vector((12, 10, 4)), tip, 40),
        ]
        for tag, eye, tgt, lens in shots:
            aim_cam(cam, eye, tgt, lens)
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

    bpy.ops.wm.save_mainfile()
    return size


def main():
    log("open", WORK_BLEND)
    bpy.ops.wm.open_mainfile(filepath=WORK_BLEND)

    glass, source = step2()
    if source == "STOP" or glass is None:
        log("STOPPED at step2")
        return

    cut_body, panes, targets = step3(glass)
    # Rebuild panes from glass object for step4 (gbm was freed) — re-read REF_玻璃 or C919
    # panes still hold bmesh faces from freed mesh — DANGEROUS. Recompute from REF_玻璃.
    g = bpy.data.objects.get("REF_玻璃")
    if g is None:
        # recreate from cut targets stored? use C919 panes from step3 islands already invalid
        raise RuntimeError("REF_玻璃 missing after step3")
    gbm = world_bmesh(g)
    islands = face_islands_set(set(gbm.faces))
    if len(islands) == 1 and len(gbm.faces) > 4:
        buckets = {"WS_L": [], "WS_R": [], "SW_L": [], "SW_R": []}
        for f in gbm.faces:
            c = f.calc_center_median()
            n = f.normal.normalized()
            if abs(n.y) > abs(n.x) and c.y > 16.5:
                key = "WS_R" if c.x >= 0 else "WS_L"
            else:
                key = "SW_R" if c.x >= 0 else "SW_L"
            buckets[key].append(f)
        islands = [b for b in buckets.values() if b]
    body = cut_body
    body_center = body.matrix_world @ (
        sum((Vector(b) for b in body.bound_box), Vector()) / 8.0
    )
    panes2 = []
    for isl in islands:
        n, c = island_normal_center(isl)
        if n.dot(c - body_center) < 0:
            n = -n
        is_front = n.dot(FORWARD.normalized()) > FRONT_DOT
        panes2.append((isl, n, c, is_front))
    targets2 = [p for p in panes2 if p[3] or not ONLY_FRONT]

    step4(panes2, targets2)
    gbm.free()

    step5(cut_body)
    size = step6(cut_body)

    notes = os.path.join(PROJ, "scripts", "NOSE_FIX_PASS_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write(
            f"""# C919 机头修复通过笔记（nose-fix）

- **时间**：2026-10-17（Asia/Shanghai）
- **约束**：blender `-b`；未使用 knife_project；未面选删除开窗；原 `Nose` 隐藏保留，操作副本 `Nose_开窗`。

## Step1
- 机身：**Nose**（另有 Fuselage）
- 机头朝向：Soft tip 在 **+Y**（≈20.03 m）
- WindowOutline：**0**（当前 blend 无残留轮廓物体；漂线来自 CockpitFrames / 旧窗片边缘）
- REF：`Obj3d66-19714258-2-287` 已导入；材质全 Transmission=0；011/013/017 为深色但非独立风挡岛

## Step2
- 轮廓来源：**{source}**
- 玻璃物体：`REF_玻璃`

## Step3–6
- 布尔：EXACT + hole_tolerant，ONLY_FRONT=False，CUT_DEPTH=0.25
- 玻璃 inset 4 mm；窗框 ~4 cm；驾驶舱暗盒
- 雷达罩：尝试删除平头 + holes_fill + 球面推尖
- GLB：`public/models/c919.glb` size={size} bytes
- 备份：`c919.glb.bak-nose-fix` / `c919.blend.bak-nose-fix`

## 诚实缺口
见控制台与 step*_*.png 自查。
"""
        )
    log("notes", notes)
    log("DONE glb_bytes", size)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

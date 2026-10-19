"""Sample REF windshield openings → Soft (a_deg, y) pane curves. Measure only."""
import bpy
import json
import math
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
import bmesh

FBX = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919.fbx")
OUT = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_WS_SILHOUETTE.json")

SOFT_TIP_Y = 19.88
SOFT_TAIL_Y = -19.58
SOFT_LEN = SOFT_TIP_Y - SOFT_TAIL_Y  # 39.46

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

bpy.ops.import_scene.fbx(filepath=str(FBX), global_scale=1.0, use_image_search=False)
primary = max(
    (o for o in bpy.context.scene.objects if o.type == "MESH" and "2-287" in o.name),
    key=lambda o: len(o.data.vertices),
)
# delete other meshes
for o in list(bpy.context.scene.objects):
    if o != primary and o.type == "MESH":
        bpy.data.objects.remove(o, do_unlink=True)

# Unrot -30deg Z, scale cm→m, apply ALL including location
primary.rotation_euler[2] = 0.0
primary.scale = (0.01, 0.01, 0.01)
bpy.ops.object.select_all(action="DESELECT")
primary.select_set(True)
bpy.context.view_layer.objects.active = primary
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Now mesh is in world with nose at some Y. Shift so nose tip Y=0, X center=0, belly Z=0-ish
coords = [v.co.copy() for v in primary.data.vertices]
ymin = min(c.y for c in coords)
ymax = max(c.y for c in coords)
xmin, xmax = min(c.x for c in coords), max(c.x for c in coords)
zmin, zmax = min(c.z for c in coords), max(c.z for c in coords)
cx = 0.5 * (xmin + xmax)
# Shift
for v in primary.data.vertices:
    v.co.x -= cx
    v.co.y -= ymin  # nose at Y=0
    v.co.z -= zmin  # belly at Z=0
primary.data.update()

coords = [v.co.copy() for v in primary.data.vertices]
ymin = min(c.y for c in coords)
ymax = max(c.y for c in coords)
zmin = min(c.z for c in coords)
zmax = max(c.z for c in coords)
print("normalized REF: Y", ymin, ymax, "len", ymax - ymin, "Z", zmin, zmax, "X", min(c.x for c in coords), max(c.x for c in coords))

REF_LEN = ymax - ymin
assert abs(REF_LEN - 38.84) < 1.0 or abs(REF_LEN - 36.0) < 5.0, REF_LEN

def to_soft_y(ref_y_from_nose):
    return SOFT_TIP_Y - ref_y_from_nose * (SOFT_LEN / REF_LEN)

def az_from_crown(x, z, z_center):
    # a=0 at crown (+Z), positive toward +X (right)
    return math.atan2(x, z - z_center)

# Build bmesh, find boundary loops in nose (openings)
bm = bmesh.new()
bm.from_mesh(primary.data)
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

boundary_edges = [e for e in bm.edges if e.is_boundary]
print("boundary edges total", len(boundary_edges))

# Cluster boundary edges by nose proximity
nose_be = []
for e in boundary_edges:
    mid = (e.verts[0].co + e.verts[1].co) * 0.5
    if mid.y < 6.0 and mid.z > 2.0:  # nose upper
        nose_be.append(e)
print("nose upper boundary edges", len(nose_be))

# Walk loops
def walk_loops(edges):
    unused = set(edges)
    loops = []
    while unused:
        start = unused.pop()
        loop = [start]
        # grow via shared verts
        changed = True
        while changed:
            changed = False
            verts = set()
            for e in loop:
                verts.add(e.verts[0])
                verts.add(e.verts[1])
            add = []
            for e in list(unused):
                if e.verts[0] in verts or e.verts[1] in verts:
                    add.append(e)
            for e in add:
                unused.discard(e)
                loop.append(e)
                changed = True
        loops.append(loop)
    return loops

loops = walk_loops(nose_be)
loops.sort(key=len, reverse=True)
print("nose loops", [(len(L),) for L in loops[:8]])

# For largest loops, collect verts and classify as windshield panes
z_center_est = 4.166 / 2  # ~fuselage half-height mid; refine per station
# Better z_center: at each y, mid of skin. Use global mid of fuselage height at y~3
skin_at_3 = [c for c in coords if 2.5 < c.y < 3.5]
if skin_at_3:
    z_center_est = 0.5 * (min(c.z for c in skin_at_3) + max(c.z for c in skin_at_3))
print("z_center_est", z_center_est)

loop_summaries = []
all_loop_pts = []  # soft samples for pane fitting
for li, loop in enumerate(loops[:6]):
    verts = set()
    for e in loop:
        verts.add(e.verts[0])
        verts.add(e.verts[1])
    pts = [v.co.copy() for v in verts]
    if len(pts) < 8:
        continue
    ys = [p.y for p in pts]
    xs = [p.x for p in pts]
    zs = [p.z for p in pts]
    # azimuths
    adegs = [math.degrees(az_from_crown(p.x, p.z, z_center_est)) for p in pts]
    summary = {
        "loop": li,
        "n_verts": len(pts),
        "y_min": min(ys),
        "y_max": max(ys),
        "z_min": min(zs),
        "z_max": max(zs),
        "x_min": min(xs),
        "x_max": max(xs),
        "a_min": min(adegs),
        "a_max": max(adegs),
        "soft_y_fwd": to_soft_y(min(ys)),  # wait: nose Y=0, fwd tip is smaller Y; windshield sill is LOWER y_from_nose? 
        # Actually nose tip y=0, aft is +Y. Windshield sill (forward edge of glass toward tip) has SMALLER y.
        # Soft: tip is HIGH y (19.88), aft lower. soft_y = tip - ref_y.
        # So sill (toward tip, small ref_y) → high soft_y = y_fwd
        # brow (aft edge, larger ref_y) → lower soft_y = y_aft
        "soft_y_sill": to_soft_y(min(ys)),
        "soft_y_brow": to_soft_y(max(ys)),
        "mean_a": sum(adegs) / len(adegs),
    }
    loop_summaries.append(summary)
    print("LOOP", summary)
    for p, a in zip(pts, adegs):
        all_loop_pts.append(
            {
                "ref_y": p.y,
                "soft_y": to_soft_y(p.y),
                "a_deg": a,
                "x": p.x,
                "z": p.z,
                "loop": li,
            }
        )

# If no openings (closed mesh with painted glass), fall back to dark-mat face centers
# using corrected coordinates
mat_idx_dark = set()
mat_names = {}
for i, s in enumerate(primary.material_slots):
    n = s.material.name if s.material else ""
    mat_names[i] = n
    if s.material and s.material.use_nodes:
        for node in s.material.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bc = node.inputs.get("Base Color")
                if bc:
                    c = bc.default_value
                    lum = c[0] + c[1] + c[2]
                    # dark or blue-dark glass
                    if lum < 0.35 or (c[2] > c[0] and lum < 0.5):
                        mat_idx_dark.add(i)

print("dark mats", {i: mat_names[i] for i in mat_idx_dark})

dark_pts = []
for poly in primary.data.polygons:
    if poly.material_index not in mat_idx_dark:
        continue
    c = poly.center
    if c.y > 6.0 or c.z < z_center_est - 0.3:
        continue
    a = math.degrees(az_from_crown(c.x, c.z, z_center_est))
    if abs(a) > 125:
        continue
    dark_pts.append({"ref_y": c.y, "soft_y": to_soft_y(c.y), "a_deg": a, "z": c.z, "mat": mat_names[poly.material_index]})

print("dark_pts", len(dark_pts))

# Bin dark pts by azimuth → y_fwd/y_aft
az_bins = defaultdict(list)
for p in dark_pts:
    bi = int(round(p["a_deg"] / 2.0)) * 2
    az_bins[bi].append(p["soft_y"])

curve = []
for bi in sorted(az_bins.keys()):
    ys = az_bins[bi]
    if len(ys) < 3:
        continue
    curve.append({"a_deg": bi, "y_fwd": max(ys), "y_aft": min(ys), "n": len(ys)})

print("curve bins", len(curve))
for row in curve:
    if abs(row["a_deg"]) <= 120:
        print(row)

# Prefer boundary-loop based if we have 4 windshield-sized loops
ws_loops = [
    s
    for s in loop_summaries
    if s["n_verts"] >= 12
    and s["y_max"] - s["y_min"] > 0.4
    and s["y_max"] - s["y_min"] < 3.5
    and s["z_max"] > z_center_est
]
print("ws_loops candidate", len(ws_loops), ws_loops)

# Fit recommended panes from curve (dark band) — more robust than loops if painted
def edge_vals(curve, a0, a1):
    pts = [r for r in curve if a0 <= r["a_deg"] <= a1]
    if len(pts) < 2:
        return None
    def at(a):
        return min(pts, key=lambda p: abs(p["a_deg"] - a))
    return {
        "a0": a0,
        "a1": a1,
        "n": len(pts),
        "y_fwd_a0": at(a0)["y_fwd"],
        "y_fwd_a1": at(a1)["y_fwd"],
        "y_aft_a0": at(a0)["y_aft"],
        "y_aft_a1": at(a1)["y_aft"],
        "y_fwd_mean": sum(p["y_fwd"] for p in pts) / len(pts),
        "y_aft_mean": sum(p["y_aft"] for p in pts) / len(pts),
    }

# Detect corner: largest gap in |a| coverage between 35 and 60
covered = sorted(k for k in az_bins.keys() if abs(k) <= 120)
gaps = []
for i in range(len(covered) - 1):
    d = covered[i + 1] - covered[i]
    if d >= 4:
        gaps.append((covered[i], covered[i + 1], d))
print("gaps", gaps)
corner = 47.5
for g0, g1, d in gaps:
    mid = 0.5 * (g0 + g1)
    if 38 <= abs(mid) <= 58:
        corner = abs(mid)
        print("corner←gap", corner)

side_out = 108
if covered:
    side_out = min(115, max(abs(c) for c in covered if abs(c) > 60) if any(abs(c) > 60 for c in covered) else 108)

rec = {
    "gap_deg": 1.15,
    "corner_deg": corner,
    "side_out_deg": side_out,
    "fwd_R": edge_vals(curve, 2, corner - 1),
    "side_R": edge_vals(curve, corner + 1, side_out),
    "fwd_L": edge_vals(curve, -(corner - 1), -2),
    "side_L": edge_vals(curve, -side_out, -(corner + 1)),
}

# If dark-mat band is body paint not glass, use geometric heuristic from nose photos:
# C919 windshield: sill ~1.5-2.5m from tip, brow ~3.5-4.5m from tip, half-angle ~45-50 front
# Map: ref_y sill~2.0 → soft 19.88-2.0*(39.46/38.84) ≈ 17.85
heuristic = {
    "fwd_y_fwd_center": to_soft_y(1.85),
    "fwd_y_aft_center": to_soft_y(3.55),
    "fwd_y_fwd_corner": to_soft_y(2.05),
    "fwd_y_aft_corner": to_soft_y(3.75),
    "side_y_fwd_inner": to_soft_y(2.10),
    "side_y_aft_inner": to_soft_y(3.85),
    "side_y_fwd_outer": to_soft_y(2.85),
    "side_y_aft_outer": to_soft_y(4.55),
    "note": "photo-class distances from tip if dark-mat fit empty",
}

# Merge: use measured when available
def pick(meas_key, edge, field, heur_key):
    if edge and edge.get(field) is not None:
        return edge[field]
    return heuristic[heur_key]

fr = rec["fwd_R"]
sr = rec["side_R"]
fitted = {
    "source": "REF dark-mat bins + tip-distance heuristic fill",
    "gap_deg": 1.15,
    "corner_deg": corner,
    "side_out_deg": side_out,
    "fwd_y_fwd_center": pick("fwd", fr, "y_fwd_a0", "fwd_y_fwd_center"),
    "fwd_y_aft_center": pick("fwd", fr, "y_aft_a0", "fwd_y_aft_center"),
    "fwd_y_fwd_corner": pick("fwd", fr, "y_fwd_a1", "fwd_y_fwd_corner"),
    "fwd_y_aft_corner": pick("fwd", fr, "y_aft_a1", "fwd_y_aft_corner"),
    "side_y_fwd_inner": pick("side", sr, "y_fwd_a0", "side_y_fwd_inner"),
    "side_y_aft_inner": pick("side", sr, "y_aft_a0", "side_y_aft_inner"),
    "side_y_fwd_outer": pick("side", sr, "y_fwd_a1", "side_y_fwd_outer"),
    "side_y_aft_outer": pick("side", sr, "y_aft_a1", "side_y_aft_outer"),
}

# Clamp to Soft windshield belt sanity (tip 19.88, join 14.85)
for k, v in list(fitted.items()):
    if isinstance(v, float):
        fitted[k] = max(15.2, min(18.6, v))

out = {
    "ref_len": REF_LEN,
    "soft_tip": SOFT_TIP_Y,
    "soft_len": SOFT_LEN,
    "z_center_est": z_center_est,
    "boundary_edges_nose": len(nose_be),
    "loop_summaries": loop_summaries,
    "ws_loop_candidates": ws_loops,
    "dark_curve": curve,
    "gaps": gaps,
    "recommended_raw": rec,
    "heuristic_tip_distances": heuristic,
    "fitted_soft_panes": fitted,
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("FITTED", json.dumps(fitted, indent=2))
print("Wrote", OUT)
bm.free()

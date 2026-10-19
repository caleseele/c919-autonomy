"""Confirm local vs world dims and rotation on primary REF mesh."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector, Matrix

FBX = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919.fbx")
OUT = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919_AUDIT_xform.json")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

bpy.ops.import_scene.fbx(filepath=str(FBX), global_scale=1.0, use_image_search=False)

primary = max(
    (o for o in bpy.context.scene.objects if o.type == "MESH"),
    key=lambda o: len(o.data.vertices),
)
print("primary", primary.name, "verts", len(primary.data.vertices))
print("location", list(primary.location))
print("rotation_euler_deg", [math.degrees(a) for a in primary.rotation_euler])
print("rotation_mode", primary.rotation_mode)
print("scale", list(primary.scale))
print("dimensions (local)", list(primary.dimensions))
print("matrix_world:\n", primary.matrix_world)

# Local mesh bounds (no transform)
coords = [v.co for v in primary.data.vertices]
lmin = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
lmax = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
print("local mesh bbox", lmin, lmax, "size", lmax - lmin)

# Apply all transforms then measure
bpy.ops.object.select_all(action="DESELECT")
primary.select_set(True)
bpy.context.view_layer.objects.active = primary
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print("AFTER APPLY dimensions", list(primary.dimensions))
coords = [v.co for v in primary.data.vertices]
lmin = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
lmax = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
size = lmax - lmin
print("after local size", size)

SCALE = 0.01
print("after *0.01 m:", size.x * SCALE, size.y * SCALE, size.z * SCALE)

# Fuselage cross-section: for each Y station, take only verts near centerline in X
# (exclude wing: |x| > fuselage half-width guess). Iteratively estimate.
ys = [c.y for c in coords]
y0, y1 = min(ys), max(ys)
# Nose at min Y (from prior)
n_bins = 60
# First pass: at each bin compute 95th percentile |x| and z range for verts in bin
import statistics

def bins_stats(x_clip=None):
    bins = []
    for i in range(n_bins):
        ya = y0 + i * (y1 - y0) / n_bins
        yb = y0 + (i + 1) * (y1 - y0) / n_bins
        pts = [c for c in coords if ya <= c.y < yb]
        if x_clip is not None:
            pts = [c for c in pts if abs(c.x) <= x_clip]
        if len(pts) < 20:
            bins.append(None)
            continue
        xs = [p.x for p in pts]
        zs = [p.z for p in pts]
        bins.append(
            {
                "i": i,
                "y_m": ((ya + yb) / 2) * SCALE,
                "n": len(pts),
                "width_m": (max(xs) - min(xs)) * SCALE,
                "height_m": (max(zs) - min(zs)) * SCALE,
                "zmin_m": min(zs) * SCALE,
                "zmax_m": max(zs) * SCALE,
            }
        )
    return bins

raw = bins_stats()
# Estimate fuselage half-width from nose region (first 15% of length) where no wings
nose_bins = [b for b in raw[:10] if b]
fuse_w_guess = statistics.median([b["width_m"] for b in nose_bins]) if nose_bins else 4.0
print("nose-region width median m", fuse_w_guess)
# Clip to 1.15 * half that width
clipped = bins_stats(x_clip=(fuse_w_guess * 0.5 * 1.2) / SCALE)  # in raw units
# Mid-body fuselage (bins 20-40)
mid = [b for b in clipped[15:40] if b]
if mid:
    fw = statistics.median([b["width_m"] for b in mid])
    fh = statistics.median([b["height_m"] for b in mid])
    print("mid fuselage clipped W x H m:", fw, fh)
else:
    fw = fh = None
    print("no mid bins")

# Print nose bins and a few mid
print("NOSE BINS:")
for b in raw[:8]:
    if b:
        print(b)
print("MID SAMPLE:")
for b in (raw[20], raw[25], raw[30], raw[35]):
    if b:
        print(b)

# Material 011 faces — likely windshield (dark blue-ish)
# Count faces and bbox of material index for dark mats
mat_map = {i: (s.material.name if s.material else None) for i, s in enumerate(primary.material_slots)}
dark = ["011", "013", "017"]
for key in dark:
    idxs = [i for i, n in mat_map.items() if n and key in n]
    if not idxs:
        continue
    faces = [p for p in primary.data.polygons if p.material_index in idxs]
    if not faces:
        continue
    # bbox of those faces' vertices
    vis = set()
    for f in faces:
        for vi in f.vertices:
            vis.add(vi)
    pts = [primary.data.vertices[i].co for i in vis]
    bb = (
        [min(p.x for p in pts) * SCALE, min(p.y for p in pts) * SCALE, min(p.z for p in pts) * SCALE],
        [max(p.x for p in pts) * SCALE, max(p.y for p in pts) * SCALE, max(p.z for p in pts) * SCALE],
    )
    print(f"MAT *{key}* faces={len(faces)} verts={len(vis)} bbox_m={bb}")

out = {
    "primary": primary.name,
    "local_size_raw_before_apply": None,
    "size_after_apply_raw": [size.x, size.y, size.z],
    "size_after_apply_m_scale_0_01": [size.x * SCALE, size.y * SCALE, size.z * SCALE],
    "nose_width_median_m": fuse_w_guess,
    "mid_fuselage_WxH_m": [fw, fh],
    "targets": {"W": 3.96, "H": 4.166, "L": 38.9, "span": 35.88, "OH": 11.95},
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Wrote", OUT)

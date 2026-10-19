import bpy
from mathutils import Vector
import json, os, shutil, math

SRC = r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919.fbx"
OUT = r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919_meters.fbx"
DESK = r"C:\Users\希儿\Desktop\REF_C919_meters.fbx"
REPORT = r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919_meters_verify.json"
NOSE_JSON = r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_nose_sections.json"

bpy.ops.wm.read_factory_settings(use_empty=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.import_scene.fbx(filepath=SRC, global_scale=1.0, use_image_search=False)

for name in list(bpy.data.objects.keys()):
    o = bpy.data.objects.get(name)
    if o is None:
        continue
    if name == "Obj3d66-19714258-1-818" or name.startswith("Cube"):
        bpy.data.objects.remove(o, do_unlink=True)

main = bpy.data.objects.get("Obj3d66-19714258-2-287")
assert main is not None

bpy.ops.object.select_all(action="DESELECT")
main.select_set(True)
bpy.context.view_layer.objects.active = main

main.scale = (0.01, 0.01, 0.01)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
main.rotation_euler = (0.0, 0.0, 0.0)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

# Apply location so mesh sits in local space, then recenter origin to bounds center
# First apply whatever location exists
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

# Compute world verts
co = [v.co.copy() for v in main.data.vertices]
xs = [c.x for c in co]; ys = [c.y for c in co]; zs = [c.z for c in co]
cx = 0.5 * (min(xs) + max(xs))
cy = 0.5 * (min(ys) + max(ys))
cz = min(zs)  # put ground-ish at z=0? better: center of mass height mid
# Put geometric center at origin for usability; keep Z so belly near 0
cz_mid = 0.5 * (min(zs) + max(zs))
# Shift mesh so center XY at 0, Z belly at 0
shift = Vector((cx, cy, min(zs)))
for v in main.data.vertices:
    v.co -= shift
main.data.update()

co = [v.co.copy() for v in main.data.vertices]
xs = [c.x for c in co]; ys = [c.y for c in co]; zs = [c.z for c in co]
dx = max(xs)-min(xs); dy = max(ys)-min(ys); dz = max(zs)-min(zs)
print(f"RECENTERED x[{min(xs):.3f},{max(xs):.3f}] y[{min(ys):.3f},{max(ys):.3f}] z[{min(zs):.3f},{max(zs):.3f}]")
print(f"DIMS L={dy:.3f} span={dx:.3f} H={dz:.3f}")

# Nose is at min Y (toward -Y per audit)
tip_y = min(ys)
aft_y = max(ys)
print(f"tip_y={tip_y:.3f} aft_y={aft_y:.3f}")

# Sample elliptical-ish sections along length for nose rebuild
# Soft Y like procedural: tip at +19.88 style — map: soft_y = tip_y_proc - (y - tip_y_ref)... 
# Procedural tip ~19.96, we map REF tip (min y) -> soft tip 19.88
SOFT_TIP = 19.88
# distance from tip along +length (aftward): d = y - tip_y (since tip is min y)
# soft_y = SOFT_TIP - d

def soft_y(y):
    return SOFT_TIP - (y - tip_y)

# Sample stations from tip back ~6m (nose region)
stations = []
for d in [0.05, 0.15, 0.30, 0.50, 0.75, 1.00, 1.30, 1.60, 2.00, 2.40, 2.80, 3.20,
          3.60, 4.00, 4.40, 4.80, 5.20, 5.60, 6.00, 6.50, 7.00, 7.50, 8.00, 9.00, 10.0]:
    y0 = tip_y + d
    band = 0.08
    pts = [c for c in co if abs(c.y - y0) < band]
    if len(pts) < 30:
        band = 0.15
        pts = [c for c in co if abs(c.y - y0) < band]
    if len(pts) < 20:
        continue
    px = [p.x for p in pts]; pz = [p.z for p in pts]
    # center of section
    x_c = 0.5 * (min(px)+max(px))
    z_c = 0.5 * (min(pz)+max(pz))
    rx = 0.5 * (max(px)-min(px))
    rz = 0.5 * (max(pz)-min(pz))
    # also crown z max, belly z min relative
    stations.append({
        "d_from_tip": d,
        "soft_y": soft_y(y0),
        "rx": rx,
        "rz": rz,
        "z_center": z_c,
        "z_min": min(pz),
        "z_max": max(pz),
        "n": len(pts),
    })

# Droop: how much z_center drops toward tip vs mid-fuselage
mid = [s for s in stations if 8.0 <= s["d_from_tip"] <= 10.0]
nose = [s for s in stations if s["d_from_tip"] <= 2.0]
z_mid = sum(s["z_center"] for s in mid)/len(mid) if mid else None
z_nose = sum(s["z_center"] for s in nose)/len(nose) if nose else None

with open(NOSE_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "soft_tip": SOFT_TIP,
        "tip_y_ref": tip_y,
        "aft_y_ref": aft_y,
        "z_mid": z_mid,
        "z_nose": z_nose,
        "droop_m": (z_mid - z_nose) if (z_mid and z_nose) else None,
        "stations": stations,
    }, f, indent=2)

print("NOSE stations sample:")
for s in stations[:12]:
    print(f"  d={s['d_from_tip']:.2f} soft_y={s['soft_y']:.2f} rx={s['rx']:.3f} rz={s['rz']:.3f} zc={s['z_center']:.3f}")

bpy.ops.object.select_all(action="DESELECT")
main.select_set(True)
bpy.context.view_layer.objects.active = main

bpy.ops.export_scene.fbx(
    filepath=OUT,
    use_selection=True,
    apply_scale_options='FBX_SCALE_NONE',
    apply_unit_scale=True,
    object_types={'MESH'},
    mesh_smooth_type='FACE',
    use_mesh_modifiers=True,
    path_mode='AUTO',
    embed_textures=False,
    axis_forward='-Y',
    axis_up='Z',
)
shutil.copy2(OUT, DESK)
sz = os.path.getsize(OUT)

# re-verify after export by reading verts again
rep = {
    "out": OUT,
    "desktop": DESK,
    "bytes": sz,
    "length_m": dy,
    "span_m": dx,
    "height_m": dz,
    "x_range": [min(xs), max(xs)],
    "y_range": [min(ys), max(ys)],
    "z_range": [min(zs), max(zs)],
    "tip_y": tip_y,
    "verts": len(main.data.vertices),
    "faces": len(main.data.polygons),
    "target": {"length": 38.8, "span": 35.7, "height": 12.1},
    "ok_dims": abs(dy-38.8)<0.3 and abs(dx-35.7)<0.3 and abs(dz-12.1)<0.3,
}
with open(REPORT, "w", encoding="utf-8") as f:
    json.dump(rep, f, indent=2)
print("REPORT", json.dumps(rep, indent=2))
print("OK")

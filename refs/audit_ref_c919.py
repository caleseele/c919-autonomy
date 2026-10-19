"""Refined REF_C919.fbx audit — ignore factory Cube and helper planes."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

FBX = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs\REF_C919.fbx")
OUT_DIR = Path(r"C:\Users\希儿\Projects\c919-autonomy\refs")
OUT_JSON = OUT_DIR / "REF_C919_AUDIT.json"
OUT_PNG = OUT_DIR / "REF_C919_nose_wireframe.png"

# Purge factory content
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    if mat.name not in ("Dots Stroke",):
        try:
            bpy.data.materials.remove(mat)
        except Exception:
            pass

print("=== IMPORT FBX scale=1.0 ===")
bpy.ops.import_scene.fbx(
    filepath=str(FBX),
    global_scale=1.0,
    use_image_search=False,
)

TARGET_W = 3.96
TARGET_H = 4.166
TARGET_LEN = 38.9
TARGET_SPAN = 35.88
TARGET_OH = 11.95  # overall height approx

def world_bbox(obj):
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs, ys, zs = [v.x for v in bb], [v.y for v in bb], [v.z for v in bb]
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]

meshes = []
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    mn, mx = world_bbox(obj)
    dims = [mx[i] - mn[i] for i in range(3)]
    info = {
        "name": obj.name,
        "verts": len(obj.data.vertices),
        "faces": len(obj.data.polygons),
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
        "bbox_min": mn,
        "bbox_max": mx,
        "dimensions": dims,
        "location": list(obj.location),
        "rotation_euler_deg": [math.degrees(a) for a in obj.rotation_euler],
        "scale": list(obj.scale),
    }
    meshes.append(info)
    print(
        f"MESH {obj.name}: v={info['verts']} f={info['faces']} "
        f"dims=({dims[0]:.4f},{dims[1]:.4f},{dims[2]:.4f}) mats={info['materials']}"
    )

# Pick primary aircraft: most verts
primary = max(meshes, key=lambda m: m["verts"])
helpers = [m for m in meshes if m["name"] != primary["name"]]
print("PRIMARY:", primary["name"], "verts", primary["verts"])
print("HELPERS:", [h["name"] for h in helpers])

pd = primary["dimensions"]
# Rank axes
order = sorted(range(3), key=lambda i: pd[i], reverse=True)
# Expect: length ~3884, span ~3569, height ~1213 at cm scale
print("primary dims XYZ:", pd)
print("sorted axis indices by size:", order, "sizes:", [pd[i] for i in order])

# Scale hypotheses
hypotheses = []
for scale, label in [(1.0, "meters"), (0.01, "cm->m"), (0.001, "mm->m"), (0.1, "dm->m"), (100.0, "*100")]:
    sd = [d * scale for d in pd]
    # Match length to longest, span to mid, height to shortest typically
    longest, mid, short = sorted(sd, reverse=True)
    err_len = abs(longest - TARGET_LEN) / TARGET_LEN
    err_span = abs(mid - TARGET_SPAN) / TARGET_SPAN
    err_oh = abs(short - TARGET_OH) / TARGET_OH
    hypotheses.append(
        {
            "scale": scale,
            "label": label,
            "scaled_xyz": sd,
            "err_len": err_len,
            "err_span": err_span,
            "err_overall_h": err_oh,
            "score": err_len + err_span + err_oh,
        }
    )
hypotheses.sort(key=lambda h: h["score"])
print("=== SCALE HYPOTHESES ===")
for h in hypotheses:
    print(h)

best_scale = hypotheses[0]["scale"]
best_label = hypotheses[0]["label"]

# Axis roles at best scale
scaled = [d * best_scale for d in pd]
# length = max, span = mid, height = min for airliner
len_axis = max(range(3), key=lambda i: scaled[i])
h_axis = min(range(3), key=lambda i: scaled[i])
span_axis = [i for i in range(3) if i not in (len_axis, h_axis)][0]
print(f"axes: length={'XYZ'[len_axis]} span={'XYZ'[span_axis]} height={'XYZ'[h_axis]}")
print("scaled dims:", {"XYZ"[i]: scaled[i] for i in range(3)})

# Nose direction: sample cross-section spans along length axis
obj_prim = bpy.data.objects[primary["name"]]
mw = obj_prim.matrix_world
verts = [mw @ v.co for v in obj_prim.data.vertices]
coords = [v[len_axis] for v in verts]
lo, hi = min(coords), max(coords)
n_bins = 40
bins = [[] for _ in range(n_bins)]
for v in verts:
    t = (v[len_axis] - lo) / (hi - lo + 1e-12)
    bi = min(n_bins - 1, max(0, int(t * n_bins)))
    bins[bi].append(v)

profile = []
for i, b in enumerate(bins):
    if len(b) < 10:
        profile.append({"bin": i, "n": len(b), "span_area": 0, "width": 0, "height": 0})
        continue
    ws = [p[span_axis] for p in b]
    hs = [p[h_axis] for p in b]
    w = max(ws) - min(ws)
    h = max(hs) - min(hs)
    profile.append(
        {
            "bin": i,
            "n": len(b),
            "span_area": w * h,
            "width": w * best_scale,
            "height": h * best_scale,
            "pos_raw": lo + (i + 0.5) * (hi - lo) / n_bins,
            "pos_m": (lo + (i + 0.5) * (hi - lo) / n_bins) * best_scale,
        }
    )

# Nose = smaller end
first = [p for p in profile[:8] if p["n"] >= 10]
last = [p for p in profile[-8:] if p["n"] >= 10]
avg_first = sum(p["span_area"] for p in first) / max(1, len(first)) if first else 0
avg_last = sum(p["span_area"] for p in last) / max(1, len(last)) if last else 0
if avg_first <= avg_last:
    nose_at = "min"  # toward lo
    forward = f"-{'XYZ'[len_axis]}"
else:
    nose_at = "max"
    forward = f"+{'XYZ'[len_axis]}"
print("nose_at:", nose_at, "forward:", forward, "avg_first:", avg_first, "avg_last:", avg_last)

# Fuselage width/height near mid-body (exclude wing stations: where width spikes)
# Find bins where width is near fuselage (not wings) — look for local minimum width in mid third
mid = profile[n_bins // 3 : 2 * n_bins // 3]
# Among mid bins with decent verts, take those with smaller width (fuselage-only stations before wing)
fuselage_bins = sorted([p for p in mid if p["n"] >= 50], key=lambda p: p["width"])
fuse_est = None
if fuselage_bins:
    # take smallest few widths as fuselage estimate (wing roots inflate width)
    sample = fuselage_bins[:5]
    fuse_est = {
        "width_m_median": sorted(p["width"] for p in sample)[len(sample) // 2],
        "height_m_median": sorted(p["height"] for p in sample)[len(sample) // 2],
        "sample_bins": sample,
    }
    print("fuselage estimate:", fuse_est["width_m_median"], "x", fuse_est["height_m_median"])

# Materials / glass
mat_notes = []
glass_candidates = []
for mat in bpy.data.materials:
    entry = {"name": mat.name}
    if mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                for inp_name in ("Transmission Weight", "Transmission", "Alpha", "Roughness", "Base Color", "Metallic"):
                    sock = n.inputs.get(inp_name)
                    if sock is None:
                        continue
                    try:
                        entry[inp_name] = list(sock.default_value) if sock.type == "RGBA" else float(sock.default_value)
                    except Exception:
                        pass
                # dark near-black + low roughness might be glass placeholder after VRay loss
                bc = entry.get("Base Color")
                tw = entry.get("Transmission Weight", 0)
                if tw and tw > 0.1:
                    glass_candidates.append(mat.name)
                elif bc and bc[0] < 0.08 and bc[1] < 0.08 and bc[2] < 0.1:
                    glass_candidates.append(mat.name + " (dark opaque — possible former VRay glass)")
    mat_notes.append(entry)

# Slot usage on primary
slot_face_counts = {}
me = obj_prim.data
for poly in me.polygons:
    mi = poly.material_index
    mat = obj_prim.material_slots[mi].material if mi < len(obj_prim.material_slots) else None
    key = mat.name if mat else f"slot{mi}"
    slot_face_counts[key] = slot_face_counts.get(key, 0) + 1

print("=== FACE COUNTS BY MATERIAL ===")
for k, v in sorted(slot_face_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("=== GLASS CANDIDATES ===", glass_candidates)

# Apply scale for PNG
for obj in list(bpy.context.scene.objects):
    if obj.type != "MESH":
        continue
    # drop helpers from render: keep only primary
    if obj.name != primary["name"]:
        obj.hide_render = True
        obj.hide_viewport = True
        continue
    obj.scale = (best_scale, best_scale, best_scale)
bpy.context.view_layer.update()
# apply scale
bpy.ops.object.select_all(action="DESELECT")
obj_prim.hide_viewport = False
obj_prim.hide_render = False
obj_prim.select_set(True)
bpy.context.view_layer.objects.active = obj_prim
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Recompute tip
verts2 = [obj_prim.matrix_world @ v.co for v in obj_prim.data.vertices]
gmin = Vector((min(v.x for v in verts2), min(v.y for v in verts2), min(v.z for v in verts2)))
gmax = Vector((max(v.x for v in verts2), max(v.y for v in verts2), max(v.z for v in verts2)))
center = (gmin + gmax) / 2
tip = center.copy()
if nose_at == "min":
    tip[len_axis] = gmin[len_axis]
else:
    tip[len_axis] = gmax[len_axis]

dist = max((gmax - gmin)) * 0.28
cam_loc = tip.copy()
# back toward body
if nose_at == "min":
    cam_loc[len_axis] += dist * 0.85
else:
    cam_loc[len_axis] -= dist * 0.85
cam_loc[span_axis] += dist * 0.75
cam_loc[h_axis] += dist * 0.4

cam_data = bpy.data.cameras.new("AuditCam")
cam_obj = bpy.data.objects.new("AuditCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = cam_loc
direction = tip - cam_loc
cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam_obj
cam_data.lens = 45

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
obj_prim.display_type = "WIRE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = str(OUT_PNG)
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("Wrote PNG", OUT_PNG)

# Also save a quick inventory of object hierarchy / collections
collections = []
for c in bpy.data.collections:
    collections.append({"name": c.name, "objects": [o.name for o in c.objects]})

result = {
    "plausible_aircraft_ref": True,
    "fbx": str(FBX),
    "filesize": FBX.stat().st_size,
    "fbx_version": "7400",
    "source_hint": "3d66 / V-Ray materials (3ds Max export)",
    "all_meshes": [
        {
            "name": m["name"],
            "verts": m["verts"],
            "faces": m["faces"],
            "dimensions_raw": m["dimensions"],
            "materials": m["materials"],
        }
        for m in meshes
    ],
    "primary_mesh": primary["name"],
    "helpers": [h["name"] for h in helpers],
    "helper_note": "Obj3d66-...-1-818 is a huge near-flat helper (~110km); ignore for scale. Factory Cube may appear if not purged.",
    "primary_dimensions_raw_xyz": pd,
    "recommended_scale": best_scale,
    "scale_note": best_label,
    "scaled_overall_xyz_m": scaled,
    "axis_roles": {
        "length": "XYZ"[len_axis],
        "span_width": "XYZ"[span_axis],
        "height": "XYZ"[h_axis],
        "forward": forward,
        "nose_at": nose_at,
        "up": "XYZ"[h_axis],
    },
    "c919_targets_m": {
        "length": TARGET_LEN,
        "wingspan": TARGET_SPAN,
        "overall_height": TARGET_OH,
        "fuselage_width": TARGET_W,
        "fuselage_height": TARGET_H,
    },
    "scale_hypotheses": hypotheses,
    "fuselage_section_estimate_m": fuse_est,
    "profile_along_length_sample": [p for p in profile if p["n"] >= 10][::4],
    "materials": mat_notes,
    "face_counts_by_material": slot_face_counts,
    "glass_like_names": [],
    "glass_candidates_heuristic": glass_candidates,
    "gaps": [
        "No objects named windshield/glass/WS_*; glass not separated as named parts.",
        "V-Ray glass lost on FBX import: all Transmission Weight = 0 (opaque Principled).",
        "Helper mesh Obj3d66-19714258-1-818 must be excluded (inflates global bbox).",
        "Fuselage width/height are estimates from binning; wing stations inflate width — use mid-body narrow bins.",
        "No REF_C919 collection yet — user must create after import.",
    ],
    "png": str(OUT_PNG),
}

OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote", OUT_JSON)
print("=== DONE ===")
print(json.dumps({k: result[k] for k in (
    "plausible_aircraft_ref", "primary_mesh", "recommended_scale", "scale_note",
    "scaled_overall_xyz_m", "axis_roles", "fuselage_section_estimate_m",
    "glass_candidates_heuristic", "gaps"
)}, indent=2, ensure_ascii=False))

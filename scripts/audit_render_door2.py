# -*- coding: utf-8 -*-
"""door2 audit + renders."""
import bpy
import math
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# When run from scripts/
if not os.path.isdir(os.path.join(ROOT, "public")):
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")

# Allow override via env
BLEND = os.environ.get("C919_BLEND", BLEND)
OUT = os.environ.get("C919_OUT", OUT)

bpy.ops.wm.open_mainfile(filepath=BLEND)

# --- Audit ---
def world_pts(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]

def section_rx(y):
    # Approximate from fuselage object mid-belt, else 2.08
    return 2.08

for name in ("Doors", "DoorFrames", "DoorWindows", "Fuselage", "Windows"):
    o = bpy.data.objects.get(name)
    if not o:
        print("MISSING_OBJ", name)
        continue
    print(f"MESH {name} verts={len(o.data.vertices)} faces={len(o.data.polygons)}")

df = bpy.data.objects["DoorFrames"]
doors = bpy.data.objects["Doors"]

# Overwing band around y=1.80
ow_f = [p for p in world_pts(df) if abs(p.y - 1.80) < 0.55 and p.x > 1.5]
ow_d = [p for p in world_pts(doors) if abs(p.y - 1.80) < 0.55 and p.x > 1.5]
print("OVERWING_FRAME_PTS", len(ow_f))
print("OVERWING_DOOR_PTS", len(ow_d))
if ow_f:
    xs = [p.x for p in ow_f]
    zs = [p.z for p in ow_f]
    ys = [p.y for p in ow_f]
    print(f"FRAME_R x=[{min(xs):.3f},{max(xs):.3f}] y=[{min(ys):.3f},{max(ys):.3f}] z=[{min(zs):.3f},{max(zs):.3f}]")
    # Radial extent: for elliptical approx, r ~ hypot(x,z) at equator
    rads = [math.hypot(p.x, p.z) for p in ow_f]
    print(f"FRAME_RADIAL [{min(rads):.3f},{max(rads):.3f}] span={max(rads)-min(rads):.3f}")
if ow_d:
    xs = [p.x for p in ow_d]
    zs = [p.z for p in ow_d]
    rads = [math.hypot(p.x, p.z) for p in ow_d]
    print(f"DOOR_R x=[{min(xs):.3f},{max(xs):.3f}] z=[{min(zs):.3f},{max(zs):.3f}]")
    print(f"DOOR_RADIAL [{min(rads):.3f},{max(rads):.3f}] span={max(rads)-min(rads):.3f}")

# Check max |x| of frames near overwing — planar bezel sat at ~rx+0.018 with thickness
# Skin-following should keep x span related to curvature, not a flat slab far out
if ow_f:
    xspan = max(p.x for p in ow_f) - min(p.x for p in ow_f)
    print(f"FRAME_XSPAN {xspan:.3f} (planar bezel historically ~0.03+; skin loft larger due to curve)")

# Wing clearance: door sill z vs wing upper near y=1.8
wing = bpy.data.objects.get("Wing_R")
if wing and ow_d:
    wnear = [wing.matrix_world @ v.co for v in wing.data.vertices if abs((wing.matrix_world @ v.co).y - 1.80) < 1.2 and (wing.matrix_world @ v.co).x < 3.5]
    if wnear:
        wz = max(p.z for p in wnear)
        sill = min(p.z for p in ow_d)
        print(f"WING_UPPER_Z_NEAR {wz:.3f} DOOR_SILL_Z {sill:.3f} CLEARANCE {sill - wz:.3f}")

# Required object keys
keys = [
    "Fuselage", "Nose", "Windows", "WindowFrames", "Doors", "DoorFrames",
    "DoorWindows", "Stripe_R", "Stripe_L", "PanelLines",
    "Wing_R", "Wing_L", "Winglet_R", "WingFairing_R", "WingBodyFairing_R",
    "Engine_R", "Engine_L", "Pylon_R", "Stab_R", "VerticalTail", "Gear_R",
    "Flag_R", "Windshield", "CockpitFrames",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    ok = o is not None
    if not ok:
        missing += 1
        print("OBJ", n, "MISSING")
    else:
        npoly = len(o.data.polygons) if o.type == "MESH" else 0
        print("OBJ", n, "OK", npoly)
print("MISSING_COUNT", missing)

# --- Render ---
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 28
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 800
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W2") if "W2" not in bpy.data.worlds else bpy.data.worlds["W2"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.18, 0.22, 0.32, 1)
    bg.inputs[1].default_value = 0.95

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 5.2, (math.radians(48), 0, math.radians(28)))
add_sun("PrevFill", 1.7, (math.radians(18), math.radians(150), 0))

cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=40):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

render(os.path.join(OUT, "c919-detail-door-overwing.png"), (7.2, 1.4, 1.35), (2.05, 1.4, 0.35), 55)
render(os.path.join(OUT, "c919-detail-door-l1.png"), (8.5, 13.05, 1.1), (2.05, 13.05, 0.15), 50)
render(os.path.join(OUT, "c919-detail-doors-side.png"), (18.0, 4.0, 2.0), (0.5, 4.0, 0.4), 40)
render(os.path.join(OUT, "c919-preview-door2.png"), (26.0, 20.0, 11.0), (2.0, -1.5, 1.0), 38)
print("DOOR2_AUDIT_RENDER_DONE")

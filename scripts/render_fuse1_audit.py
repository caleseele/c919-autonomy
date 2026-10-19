import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 28
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 800
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.50, 0.56, 0.64, 1)
    bg.inputs[1].default_value = 1.05

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)


def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot


add_sun("PrevKey", 5.0, (math.radians(50), 0, math.radians(30)))
add_sun("PrevFill", 1.8, (math.radians(20), math.radians(145), 0))

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


render(f"{OUT_DIR}\\c919-detail-fuse-side.png", (42.0, 0.0, 2.5), (0.0, 0.0, 1.0), 36)
render(f"{OUT_DIR}\\c919-detail-fuse-top.png", (0.0, -1.0, 48.0), (0.0, -1.0, 0.0), 34)
render(f"{OUT_DIR}\\c919-detail-windows.png", (8.5, 6.0, 1.2), (2.1, 6.0, 0.55), 50)
render(f"{OUT_DIR}\\c919-detail-doors.png", (9.0, 13.0, 1.0), (2.1, 13.0, 0.1), 48)
render(f"{OUT_DIR}\\c919-preview-fuse1.png", (26.0, 20.0, 11.0), (2.0, -1.5, 1.0), 38)

keys = [
    "Fuselage", "Nose", "Windows", "WindowFrames", "Doors", "DoorFrames",
    "DoorWindows", "Stripe_R", "Stripe_L", "PanelLines",
    "Wing_R", "Wing_L", "Winglet_R", "WingFairing_R", "WingBodyFairing_R",
    "Engine_R", "Engine_L", "Pylon_R", "Stab_R", "VerticalTail", "Gear_R",
    "Flag_R", "Windshield",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    ok = o is not None
    if not ok:
        missing += 1
    npoly = len(o.data.polygons) if ok and o.type == "MESH" else 0
    print("OBJ", n, "OK" if ok else "MISSING", npoly)
print("MISSING_COUNT", missing)

for name in ("Fuselage", "Nose", "Windows", "Doors", "Wing_R", "Engine_R"):
    obj = bpy.data.objects.get(name)
    if not obj:
        continue
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    print(
        f"BBOX {name} x=[{min(xs):.2f},{max(xs):.2f}] "
        f"y=[{min(ys):.2f},{max(ys):.2f}] z=[{min(zs):.2f},{max(zs):.2f}]"
    )

# Soft ACAP length check from Nose+Fuselage combined Y span
ys_all = []
for name in ("Nose", "Fuselage"):
    obj = bpy.data.objects.get(name)
    if not obj:
        continue
    for c in obj.bound_box:
        ys_all.append((obj.matrix_world @ Vector(c)).y)
if ys_all:
    length = max(ys_all) - min(ys_all)
    print(f"SOFT_LENGTH_M {length:.2f} (ACAP 38.90)")

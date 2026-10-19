import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 800
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
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


# Overwing emergency exit close-up (matches user bug screenshot angle)
render(f"{OUT_DIR}\\c919-detail-door-overwing.png", (7.2, 1.4, 1.35), (2.05, 1.4, 0.35), 55)
# L1 passenger door
render(f"{OUT_DIR}\\c919-detail-door-l1.png", (8.5, 13.05, 1.1), (2.05, 13.05, 0.15), 50)
# Side doors overview
render(f"{OUT_DIR}\\c919-detail-doors-side.png", (18.0, 4.0, 2.0), (0.5, 4.0, 0.4), 40)
# Full preview
render(f"{OUT_DIR}\\c919-preview-door1.png", (26.0, 20.0, 11.0), (2.0, -1.5, 1.0), 38)

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

for name in ("Doors", "DoorFrames", "DoorWindows", "Windows", "Fuselage"):
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

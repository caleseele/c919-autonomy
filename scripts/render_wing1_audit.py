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
    bg.inputs[0].default_value = (0.48, 0.54, 0.62, 1)
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


# Top planform
render(f"{OUT_DIR}\\c919-detail-wing-top.png", (0.0, -1.0, 46.0), (0.0, -1.0, 0.0), 35)
# True side of starboard wing (airfoil thickness)
render(f"{OUT_DIR}\\c919-detail-wing-side.png", (38.0, 0.5, 0.2), (8.0, 0.5, -0.8), 42)
# Winglet close-up starboard tip, slight 3/4
render(f"{OUT_DIR}\\c919-detail-winglet.png", (20.5, -6.5, 3.8), (16.2, -1.0, 0.3), 48)
# Underside TE canoes
render(f"{OUT_DIR}\\c919-detail-flaptrack.png", (9.5, -9.5, -2.8), (7.5, -2.8, -1.0), 40)
# Beauty 3/4
render(f"{OUT_DIR}\\c919-preview-wing1.png", (26.0, 20.0, 11.0), (2.0, -1.5, 1.0), 38)

keys = [
    "Wing_R", "Wing_L", "Winglet_R", "Winglet_L",
    "WingFairing_R", "WingFairing_L", "WingLE_R", "WingLE_L",
    "WingBodyFairing_R", "WingBodyFairing_L",
    "Engine_R", "Engine_L", "Pylon_R", "Pylon_L",
    "Fuselage", "Nose", "Stab_R", "VerticalTail", "Gear_R",
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

for name in ("Wing_R", "Winglet_R", "WingFairing_R", "WingBodyFairing_R", "Engine_R"):
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

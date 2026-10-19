import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.05, 0.09, 0.15, 1)

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 6.0, (math.radians(35), 0, math.radians(15)))
add_sun("PrevFill", 2.5, (math.radians(10), math.radians(160), 0))
for pos, name in [((6.2, 4.0, -1.95), "PrevIn1"), ((6.2, 2.9, -1.2), "PrevIn2")]:
    pl = bpy.data.lights.new(name=name, type="POINT")
    pl.energy = 350
    po = bpy.data.objects.new(name, pl)
    scene.collection.objects.link(po)
    po.location = pos

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

render(f"{OUT_DIR}\\c919-detail-windows.png", (6.8, 5.5, 0.9), (2.08, 5.5, 0.58), 50)
render(f"{OUT_DIR}\\c919-detail-windshield.png", (3.2, 21.0, 2.5), (0.0, 17.1, 0.85), 45)
# Off-axis into intake so blades silhouette against dark core
render(f"{OUT_DIR}\\c919-detail-fan.png", (7.4, 6.2, -1.2), (6.2, 2.78, -1.95), 50)
render(f"{OUT_DIR}\\c919-detail-flag.png", (4.8, -7.4, 1.4), (2.12, -8.2, 0.65), 48)

for n in ["Windows", "WindowFrames", "Windshield", "CockpitFrames", "Fan_R", "EngineLip_R", "Flag_R"]:
    o = bpy.data.objects.get(n)
    print("OBJ", n, "OK" if o else "MISSING", len(o.data.polygons) if o and o.type=="MESH" else 0)

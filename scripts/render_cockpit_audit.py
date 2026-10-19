import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = eng
        break
    except Exception:
        continue
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.55, 0.62, 0.70, 1)

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 5.5, (math.radians(40), 0, math.radians(25)))
add_sun("PrevFill", 2.2, (math.radians(15), math.radians(150), 0))

cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=40):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    # Up = world +Z so side/front views are upright (fuselage along Y)
    cam.rotation_euler = d.to_track_quat("-Z", "Z").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

# True side silhouette (eye-level, look along -X)
render(f"{OUT_DIR}\\c919-detail-nose-side.png", (13.0, 18.6, 0.40), (0.0, 18.6, 0.40), 55)
# Front-¾ windshield matching ref-nose-front angle
render(f"{OUT_DIR}\\c919-detail-windshield.png", (3.2, 24.8, 1.1), (0.0, 17.8, 0.50), 42)

for n in ["Nose", "Windshield", "CockpitFrames", "PitotProbes"]:
    o = bpy.data.objects.get(n)
    print("OBJ", n, "OK" if o else "MISSING",
          len(o.data.polygons) if o and o.type == "MESH" else 0)

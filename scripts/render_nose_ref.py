import bpy
import math
from mathutils import Vector
import os

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"
GLB = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.glb"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.get("W") or bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.55, 0.60, 0.68, 1)
    bg.inputs[1].default_value = 1.1

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 4.8, (math.radians(40), 0, math.radians(25)))
add_sun("PrevFill", 1.8, (math.radians(15), math.radians(160), 0))

cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=40):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Z").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path, os.path.getsize(path) if os.path.exists(path) else 0)

# Aim near drooped windshield belt (z ~ 0.3..0.9 after droop)
render(f"{OUT_DIR}\\c919-detail-nose-side.png", (14.5, 17.4, 0.15), (0.0, 17.4, -0.05), 48)
render(f"{OUT_DIR}\\c919-detail-nose-front.png", (2.8, 27.2, 0.35), (0.0, 17.5, -0.10), 36)
render(f"{OUT_DIR}\\c919-detail-nose-top.png", (0.2, 17.2, 9.5), (0.0, 17.2, 0.0), 42)
render(f"{OUT_DIR}\\c919-detail-windshield.png", (3.4, 22.8, 1.35), (0.0, 17.1, 0.45), 46)
render(f"{OUT_DIR}\\c919-preview-nose-ref.png", (15.5, 24.5, 5.2), (0.0, 14.5, 0.2), 40)

keys = [
    "Nose", "WS_L", "WS_R", "SW_L", "SW_R", "CockpitFrames", "CockpitCabin",
    "PitotProbes", "Doors", "DoorFrames", "Windows", "WindowFrames", "PanelLines",
    "Fuselage", "Engine_R", "Wing_R", "Gear_Nose", "WindshieldWipers", "GlareShield",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    if o is None:
        missing += 1
        print("MISSING", n)
    else:
        print("OK", n, len(o.data.polygons) if o.type == "MESH" else "-")
print("MISSING_COUNT", missing)
print("GLB_BYTES", os.path.getsize(GLB))

nose = bpy.data.objects.get("Nose")
if nose:
    co = [v.co for v in nose.data.vertices]
    ys = [c.y for c in co]; zs = [c.z for c in co]; xs = [c.x for c in co]
    tip = max(ys)
    tip_verts = [c for c in co if c.y > tip - 0.05]
    tip_z = sum(c.z for c in tip_verts) / len(tip_verts)
    join_verts = [c for c in co if abs(c.y - 14.85) < 0.08]
    join_z = sum(c.z for c in join_verts) / len(join_verts) if join_verts else 0
    print(f"NOSE tip_y={tip:.3f} tip_z_mean={tip_z:.3f} join_z_mean={join_z:.3f} droop≈{join_z-tip_z:.3f}")
    print(f"NOSE x[{min(xs):.3f},{max(xs):.3f}] z[{min(zs):.3f},{max(zs):.3f}]")

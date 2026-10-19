# -*- coding: utf-8 -*-
"""EEVEE left-front material shot for §11.6."""
import bpy
import math
from datetime import datetime
from pathlib import Path
from mathutils import Vector, Euler

ROOT = Path(__file__).resolve().parent.parent
BLEND = ROOT / "public" / "models" / "c919.blend"
OUTDIR = ROOT / "public" / "models" / "section11"
OUTDIR.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = OUTDIR / f"comac_left_front_{stamp}.png"

bpy.ops.wm.open_mainfile(filepath=str(BLEND))
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = str(OUT)
scene.render.image_settings.file_format = "PNG"

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.027, 0.078, 0.157, 1.0)
    bg.inputs[1].default_value = 1.0

for o in list(bpy.data.objects):
    if o.type == "LIGHT":
        bpy.data.objects.remove(o, do_unlink=True)

def add_sun(name, energy, loc, rot):
    light = bpy.data.lights.new(name, type="SUN")
    light.energy = energy
    ob = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot

add_sun("Key", 3.2, (22, -16, 28), Euler((math.radians(50), 0, math.radians(35)), "XYZ"))
add_sun("Fill", 1.0, (-10, 30, 14), Euler((math.radians(35), 0, math.radians(-20)), "XYZ"))

fuse = bpy.data.objects["Fuselage_REF"]
vs = [fuse.matrix_world @ v.co for v in fuse.data.vertices]
xs = [p.x for p in vs]; ys = [p.y for p in vs]; zs = [p.z for p in vs]
cx = (min(xs) + max(xs)) / 2
cy = (min(ys) + max(ys)) / 2
cz = (min(zs) + max(zs)) / 2
tip = max(ys)  # nose
# left front-side: camera ahead of nose on the left, looking aft-right at mid body
cam_data = bpy.data.cameras.new("S11Cam")
cam = bpy.data.objects.new("S11Cam", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.location = Vector((cx - 26.0, tip + 8.0, cz + 9.0))
target = Vector((cx, cy + 2.0, cz + 1.0))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
cam_data.lens = 45

bpy.ops.render.render(write_still=True)
print(f"SHOT={OUT} size={OUT.stat().st_size}", flush=True)

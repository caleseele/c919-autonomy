# -*- coding: utf-8 -*-
"""Side-on + 3/4 door2 proof renders (less glancing exaggeration)."""
import bpy, math, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("W3") if "W3" not in bpy.data.worlds else bpy.data.worlds["W3"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
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
add_sun("PrevKey", 4.5, (math.radians(50), 0, math.radians(35)))
add_sun("PrevFill", 1.4, (math.radians(20), math.radians(160), 0))
cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=45):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

# True side-on overwing (camera on +X, looking at door center)
render(os.path.join(OUT, "c919-detail-door-overwing.png"), (9.5, 1.80, 0.95), (0.0, 1.80, 0.95), 70)
# Mild 3/4
render(os.path.join(OUT, "c919-detail-door-overwing-34.png"), (7.5, -0.2, 1.6), (2.0, 1.80, 0.7), 55)
# L1 passenger side-on
render(os.path.join(OUT, "c919-detail-door-l1.png"), (10.0, 13.05, 0.2), (0.0, 13.05, 0.2), 60)
# Preview
render(os.path.join(OUT, "c919-preview-door2.png"), (24.0, 18.0, 10.0), (2.0, -1.0, 1.0), 38)
print("SIDE_RENDERS_DONE")

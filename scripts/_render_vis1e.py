import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))
OUT = os.path.join(ROOT, "public", "models")

for n in ("Windshield", "CockpitFrames", "Nose"):
    o = bpy.data.objects.get(n)
    # keep nose; hide only glass so we look through the canopy hole
if bpy.data.objects.get("Windshield"):
    bpy.data.objects["Windshield"].hide_render = True
if bpy.data.objects.get("CockpitFrames"):
    bpy.data.objects["CockpitFrames"].hide_render = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 800

cam = bpy.data.objects.new("C", bpy.data.cameras.new("Cd"))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 28

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.4, 0.42, 0.45, 1)

L = bpy.data.objects.new("L", bpy.data.lights.new("Ld", "SUN"))
L.data.energy = 3.0
L.rotation_euler = (0.9, 0.2, 0.4)
bpy.context.scene.collection.objects.link(L)

# Elevated front looking down into cockpit cavity
eye = Vector((0.6, 19.8, 2.6))
tgt = Vector((0.0, 16.6, 0.45))
cam.location = eye
cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
scene.render.filepath = os.path.join(OUT, "c919-detail-cockpit-interior.png")
bpy.ops.render.render(write_still=True)
print("COCKPIT_OK", os.path.getsize(scene.render.filepath))

# High 3/4 showing door ABOVE wing (camera above wing plane)
if bpy.data.objects.get("Windshield"):
    bpy.data.objects["Windshield"].hide_render = False
if bpy.data.objects.get("CockpitFrames"):
    bpy.data.objects["CockpitFrames"].hide_render = False
eye = Vector((7.0, 3.5, 5.0))
tgt = Vector((2.0, 1.8, 0.95))
cam.location = eye
cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 40
scene.render.filepath = os.path.join(OUT, "c919-detail-door-overwing.png")
bpy.ops.render.render(write_still=True)
print("DOOR_OK", os.path.getsize(scene.render.filepath))

# Overview
eye = Vector((13, 15, 7))
tgt = Vector((0, 2, 0.5))
cam.location = eye
cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 45
scene.render.filepath = os.path.join(OUT, "c919-preview-vis1.png")
bpy.ops.render.render(write_still=True)
print("PREV_OK", os.path.getsize(scene.render.filepath))

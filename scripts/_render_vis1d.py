import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

# Hide glass/frames so seats+glare+wipers read clearly in workbench
for n in ("Windshield", "CockpitFrames"):
    o = bpy.data.objects.get(n)
    if o:
        o.hide_render = True
        o.hide_viewport = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("CamX")
cam = bpy.data.objects.new("CamX", cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 40

world = bpy.data.worlds.new("Wx")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.45, 0.47, 0.5, 1)

key = bpy.data.objects.new("Kx", bpy.data.lights.new("Kxd", "AREA"))
key.data.energy = 1000
key.data.size = 6
key.location = (3, 19, 4)
bpy.context.scene.collection.objects.link(key)

# Front-into-cockpit: seats red, glare dark, wipers on sill
eye = Vector((0.0, 20.2, 1.15))
target = Vector((0.0, 16.55, 0.55))
cam.location = eye
cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
path = os.path.join(OUT, "c919-detail-cockpit-interior.png")
scene.render.filepath = path
bpy.ops.render.render(write_still=True)
print("COCKPIT", os.path.getsize(path))

# Also side 3/4 with wing+door together (glass back on for overview not needed)
for n in ("Windshield", "CockpitFrames"):
    o = bpy.data.objects.get(n)
    if o:
        o.hide_render = False
        o.hide_viewport = False

eye = Vector((8.5, 8.0, 3.8))
target = Vector((1.8, 1.8, 0.9))
cam.location = eye
cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
path2 = os.path.join(OUT, "c919-detail-door-overwing.png")
scene.render.filepath = path2
bpy.ops.render.render(write_still=True)
print("DOOR", os.path.getsize(path2))
print("OK")

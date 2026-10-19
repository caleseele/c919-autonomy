import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))
OUT = os.path.join(ROOT, "public", "models")

# Soften glass alpha for workbench won't help — hide glass but keep frames, look through punched hole
ws = bpy.data.objects.get("Windshield")
if ws:
    ws.hide_render = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1400
scene.render.resolution_y = 900

cam = bpy.data.objects.new("C", bpy.data.cameras.new("Cd"))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.38, 0.4, 0.43, 1)

sun = bpy.data.objects.new("S", bpy.data.lights.new("Sd", "SUN"))
sun.data.energy = 2.8
sun.rotation_euler = (0.85, 0.15, 0.5)
bpy.context.scene.collection.objects.link(sun)
area = bpy.data.objects.new("A", bpy.data.lights.new("Ad", "AREA"))
area.data.energy = 600
area.data.size = 5
area.location = (2, 18, 3)
bpy.context.scene.collection.objects.link(area)

def shoot(name, eye, tgt, lens=32):
    cam.location = eye
    cam.data.lens = lens
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    print("SHOT", name, os.path.getsize(scene.render.filepath))

# Into punched canopy — seats should be visible
shoot("c919-detail-cockpit-interior.png", (0.4, 19.6, 2.3), (0.0, 16.55, 0.5), 30)
# Wipers with glass back
if ws:
    ws.hide_render = False
shoot("c919-detail-wipers.png", (0.15, 22.2, 1.85), (0.0, 17.05, 1.15), 40)
# Door above wing from high outboard
shoot("c919-detail-door-overwing.png", (6.2, 2.5, 4.8), (2.05, 1.8, 1.0), 42)
# Overview
shoot("c919-preview-vis1.png", (12.5, 14.5, 6.8), (0.5, 1.5, 0.6), 48)

print("GLB", os.path.getsize(os.path.join(OUT, "c919.glb")))
# recount seats
for n in ("PilotSeats", "GlareShield", "WindshieldWipers", "Doors"):
    o = bpy.data.objects.get(n)
    print("OBJ", n, len(o.data.vertices) if o else None)

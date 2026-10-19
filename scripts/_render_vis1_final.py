import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))
OUT = os.path.join(ROOT, "public", "models")
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
cam = bpy.data.objects.new("C", bpy.data.cameras.new("Cd"))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
world = bpy.data.worlds.new("W"); scene.world=world; world.use_nodes=True
world.node_tree.nodes["Background"].inputs[0].default_value=(0.4,0.42,0.45,1)
sun=bpy.data.objects.new("S", bpy.data.lights.new("Sd","SUN")); sun.data.energy=3.0
bpy.context.scene.collection.objects.link(sun)

def shoot(name, eye, tgt, lens=40):
    cam.location=Vector(eye); cam.data.lens=lens
    cam.rotation_euler=(Vector(tgt)-Vector(eye)).to_track_quat("-Z","Y").to_euler()
    scene.render.filepath=os.path.join(OUT,name)
    bpy.ops.render.render(write_still=True)
    print("OK", name, os.path.getsize(scene.render.filepath))

# High 3/4 door + wing
shoot("c919-detail-door-overwing.png", (6.5, 4.0, 4.5), (2.0, 1.8, 1.0), 42)
# Side door
shoot("c919-detail-door-side.png", (9.0, 1.8, 1.05), (0.0, 1.8, 0.95), 50)
# Overview
shoot("c919-preview-vis1.png", (12, 15, 6.5), (0.5, 1.5, 0.6), 48)
# Wipers
shoot("c919-detail-wipers.png", (0.2, 22.0, 1.9), (0.0, 17.0, 1.15), 40)
# Cockpit seats (hide glass)
if bpy.data.objects.get("Windshield"):
    bpy.data.objects["Windshield"].hide_render=True
shoot("c919-detail-cockpit-interior.png", (0.5, 19.5, 2.35), (0.0, 16.25, 0.75), 28)

# sizes
print("GLB_SIZE", os.path.getsize(os.path.join(OUT,"c919.glb")))
wing=bpy.data.objects["Wing_R"]; door=bpy.data.objects["Doors"]
def near(obj,y0):
    mw=obj.matrix_world; pts=[]
    for v in obj.data.vertices:
        w=mw@v.co
        if abs(w.y-y0)<0.55 and abs(w.x)>1.2: pts.append(w)
    return pts
wp=near(wing,1.8); dp=near(door,1.8)
print("CLEARANCE", round(min(p.z for p in dp)-max(p.z for p in wp),3))
print("MISSING_COUNT_NOTE seats_wipers_door_geo_ok; see notes for remaining visual gaps")

import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))
OUT = os.path.join(ROOT, "public", "models")

# Highlight doors: make DoorFrames emissive-bright for audit? instead just render with MATERIAL
# Isolate: hide wing to prove door exists at overwing Y
for n in list(bpy.data.objects.keys()):
    if n.startswith("Wing") or n.startswith("Engine") or n.startswith("Gear") or n.startswith("Winglet") or n.startswith("WingFairing") or n.startswith("WingBody") or n.startswith("WingLE") or n.startswith("Pylon") or n.startswith("Fan"):
        bpy.data.objects[n].hide_render = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
cam = bpy.data.objects.new("C", bpy.data.cameras.new("Cd"))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 40
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.35,0.37,0.4,1)
sun = bpy.data.objects.new("S", bpy.data.lights.new("Sd","SUN")); sun.data.energy=3
bpy.context.scene.collection.objects.link(sun)

# Side view door only
eye = Vector((8.0, 1.80, 1.0)); tgt = Vector((0, 1.80, 0.95))
cam.location = eye
cam.rotation_euler = (tgt-eye).to_track_quat("-Z","Y").to_euler()
scene.render.filepath = os.path.join(OUT, "c919-detail-door-overwing.png")
bpy.ops.render.render(write_still=True)
print("DOOR_NO_WING", os.path.getsize(scene.render.filepath))

# Unhide wings, high camera
for o in bpy.data.objects:
    o.hide_render = False
# hide glass for seats
if bpy.data.objects.get("Windshield"):
    bpy.data.objects["Windshield"].hide_render = True
eye = Vector((0.5, 19.5, 2.4)); tgt = Vector((0.0, 16.3, 0.7))
cam.location = eye
cam.rotation_euler = (tgt-eye).to_track_quat("-Z","Y").to_euler()
cam.data.lens = 28
scene.render.filepath = os.path.join(OUT, "c919-detail-cockpit-interior.png")
bpy.ops.render.render(write_still=True)
print("COCKPIT", os.path.getsize(scene.render.filepath))

# Audit door verts
door = bpy.data.objects["Doors"]
df = bpy.data.objects["DoorFrames"]
pts = []
for v in door.data.vertices:
    w = door.matrix_world @ v.co
    if abs(w.y-1.80)<0.5 and w.x>1.5:
        pts.append(w)
print("DOOR_OVERWING_N", len(pts), "Z", round(min(p.z for p in pts),3), round(max(p.z for p in pts),3) if pts else None)
pts2=[]
for v in df.data.vertices:
    w = df.matrix_world @ v.co
    if abs(w.y-1.80)<0.5 and w.x>1.5:
        pts2.append(w)
print("FRAME_OVERWING_N", len(pts2), "Z", round(min(p.z for p in pts2),3), round(max(p.z for p in pts2),3) if pts2 else None)
seats = bpy.data.objects["PilotSeats"]
zs=[(seats.matrix_world@v.co).z for v in seats.data.vertices]
print("SEAT_Z", round(min(zs),3), round(max(zs),3))
print("GLB", os.path.getsize(os.path.join(OUT,"c919.glb")))

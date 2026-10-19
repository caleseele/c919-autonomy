# -*- coding: utf-8 -*-
import bpy, math, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

# Force debug colors
def force_rgb(obj_name, rgb):
    o = bpy.data.objects.get(obj_name)
    if not o:
        print("NO", obj_name)
        return
    mat = bpy.data.materials.new(name=f"DBG_{obj_name}")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    o.data.materials.clear()
    o.data.materials.append(mat)
    print("COLORED", obj_name, rgb, "verts", len(o.data.vertices), "faces", len(o.data.polygons))

force_rgb("Doors", (0.05, 0.95, 0.15))       # neon green panel
force_rgb("DoorFrames", (0.95, 0.05, 0.05))  # neon red seal
force_rgb("DoorWindows", (0.1, 0.4, 1.0))    # blue glass

# Sample overwing door face centers
doors = bpy.data.objects["Doors"]
ow = []
for p in doors.data.polygons:
    c = doors.matrix_world @ p.center
    if abs(c.y - 1.80) < 0.4 and c.x > 1.5:
        ow.append(c)
print("OVERWING_DOOR_FACES", len(ow))
if ow:
    print("face_x", round(min(c.x for c in ow),3), round(max(c.x for c in ow),3))
    print("face_z", round(min(c.z for c in ow),3), round(max(c.z for c in ow),3))

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 20
scene.render.resolution_x = 1100
scene.render.resolution_y = 700
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("WD") if "WD" not in bpy.data.worlds else bpy.data.worlds["WD"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.4, 0.45, 0.55, 1)
    bg.inputs[1].default_value = 1.0
for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
ld = bpy.data.lights.new(name="PrevKey", type="SUN")
ld.energy = 5.0
o = bpy.data.objects.new("PrevKey", ld)
scene.collection.objects.link(o)
o.rotation_euler = (math.radians(48), 0, math.radians(30))
cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=60):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

render(os.path.join(OUT, "c919-debug-doors-door2.png"), (9.5, 1.80, 0.95), (0.0, 1.80, 0.95), 70)
render(os.path.join(OUT, "c919-debug-doors-l1.png"), (10.0, 13.05, 0.2), (0.0, 13.05, 0.2), 60)
print("DEBUG_DONE")

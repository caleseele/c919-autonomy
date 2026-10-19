import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919-debug-doors.png"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
scene.render.resolution_x = 1400
scene.render.resolution_y = 800
scene.render.image_settings.file_format = "PNG"

for name, col in (
    ("Doors", (1, 0, 0, 1)),
    ("DoorFrames", (0, 1, 0, 1)),
    ("DoorWindows", (0, 0, 1, 1)),
):
    obj = bpy.data.objects.get(name)
    if not obj:
        print("MISSING", name)
        continue
    mat = bpy.data.materials.new(name + "_DBG")
    mat.use_nodes = True
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = col
    em.inputs[1].default_value = 8.0
    nt.links.new(em.outputs[0], out.inputs[0])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    print(name, "verts", len(obj.data.vertices), "faces", len(obj.data.polygons))

for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 50
cam.location = Vector((7.5, 1.4, 1.2))
d = Vector((2.05, 1.4, 0.25)) - cam.location
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

world = scene.world or bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.15, 0.15, 0.18, 1)
    bg.inputs[1].default_value = 0.5

scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("WROTE", OUT)

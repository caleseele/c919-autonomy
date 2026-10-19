import os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

needed = ["WindshieldWipers", "PilotSeats", "GlareShield", "Windshield", "Doors", "PitotProbes"]
for n in needed:
    o = bpy.data.objects.get(n)
    print("HAS", n, o is not None, "verts", len(o.data.vertices) if o and o.type=="MESH" else 0)

# Make windshield nearly clear for audit shot
ws = bpy.data.objects.get("Windshield")
if ws and ws.data.materials:
    mat = ws.data.materials[0]
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
    if bsdf:
        for k,v in (("Alpha", 0.12), ("Transmission Weight", 0.95), ("Transmission", 0.95)):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = v

scene = bpy.context.scene
engines = list(bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys())
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else ("BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_WORKBENCH")
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("CockCam")
cam = bpy.data.objects.new("CockCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 35

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.5, 0.52, 0.55, 1)
    bg.inputs[1].default_value = 1.2

for loc, name, e in (((6, 18, 8), "L1", 900), ((-4, 12, 5), "L2", 400)):
    ob = bpy.data.objects.new(name, bpy.data.lights.new(name+"d", "AREA"))
    ob.data.energy = e
    ob.data.size = 8
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)

def shoot(fname, eye, target):
    cam.location = eye
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    path = os.path.join(OUT, fname)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("SHOT", fname, os.path.getsize(path))

# Look into cockpit through windshield
shoot("c919-detail-cockpit-interior.png", (0.35, 20.6, 1.55), (0.0, 16.6, 0.55))
# Wipers front-on
shoot("c919-detail-wipers.png", (0.2, 22.0, 1.9), (0.0, 17.0, 1.2))
# 3/4 overview with door above wing
shoot("c919-preview-vis1.png", (11.0, 16.0, 5.5), (1.0, 1.5, 0.6))
# door high 3/4 including wing
shoot("c919-detail-door-overwing.png", (5.8, 4.2, 3.5), (2.0, 1.8, 0.9))
print("DONE")

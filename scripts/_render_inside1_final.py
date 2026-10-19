"""Final INSIDE1 previews: EEVEE with glass + workbench no-glass interior."""
import bpy
from mathutils import Vector
ROOT = r"C:\Users\希儿\Projects\c919-autonomy\public\models"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\c919.blend")

# Ensure glass blend
mat = bpy.data.materials.get("CockpitGlass")
if mat:
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = 0.30
            if "Transmission Weight" in bsdf.inputs:
                bsdf.inputs["Transmission Weight"].default_value = 0.90

world = bpy.context.scene.world or bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.60, 0.68, 1)
ld = bpy.data.lights.new("K", "SUN"); ld.energy = 3.5
lo = bpy.data.objects.new("K", ld); bpy.context.collection.objects.link(lo)
lo.rotation_euler = (0.9, 0.2, 0.4)
la = bpy.data.lights.new("F", "AREA"); la.energy = 400; la.size = 8
fa = bpy.data.objects.new("F", la); bpy.context.collection.objects.link(fa); fa.location = (0, 22, 3)

def cam(loc, tgt, lens=48):
    cd = bpy.data.cameras.new("C"); cd.lens = lens
    c = bpy.data.objects.new("C", cd); bpy.context.collection.objects.link(c)
    c.location = loc
    c.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = c
    return c

def render(path, engine="BLENDER_EEVEE"):
    sc = bpy.context.scene
    try:
        sc.render.engine = engine
    except Exception:
        sc.render.engine = "BLENDER_WORKBENCH"
    if "EEVEE" in sc.render.engine:
        pass
    else:
        sc.display.shading.light = "STUDIO"
        sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("WROTE", path, sc.render.engine)

# Exterior with glass (EEVEE)
cam((0.2, 24.0, 1.55), (0, 16.7, 1.05), 52)
render(ROOT + r"\c919-detail-windshield-front.png", "BLENDER_EEVEE")
cam((5.0, 20.2, 1.55), (0, 16.85, 1.05), 48)
render(ROOT + r"\c919-detail-windshield-side.png", "BLENDER_EEVEE")
cam((7.0, 21.5, 3.2), (0, 16.5, 0.9), 42)
render(ROOT + r"\c919-preview-inside1.png", "BLENDER_EEVEE")

# Interior peek: hide glass, look down (Workbench material)
ws = bpy.data.objects.get("Windshield")
if ws:
    ws.hide_render = True
cam((0.0, 20.2, 2.5), (0.0, 16.55, 0.75), 44)
render(ROOT + r"\c919-detail-cockpit-interior.png", "BLENDER_WORKBENCH")
print("FINAL_DONE")

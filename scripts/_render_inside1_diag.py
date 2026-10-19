import bpy
from mathutils import Vector
ROOT = r"C:\Users\希儿\Projects\c919-autonomy\public\models"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\c919.blend")
ws = bpy.data.objects.get("Windshield")
if ws:
    ws.hide_render = True
# tint seats bright so they read in clay
mat = bpy.data.materials.get("PilotSeat")
if mat and mat.use_nodes:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.85, 0.05, 0.05, 1)
world = bpy.context.scene.world or bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.5,0.55,0.6,1)
ld = bpy.data.lights.new("K","AREA"); ld.energy=2000; ld.size=12
lo = bpy.data.objects.new("K", ld); bpy.context.collection.objects.link(lo); lo.location=(2,18,5)
def shot(path, loc, tgt, lens=50):
    cd=bpy.data.cameras.new("C"); cd.lens=lens
    c=bpy.data.objects.new("C",cd); bpy.context.collection.objects.link(c)
    c.location=loc
    c.rotation_euler=(Vector(tgt)-Vector(loc)).to_track_quat("-Z","Y").to_euler()
    sc=bpy.context.scene; sc.camera=c
    sc.render.engine="BLENDER_WORKBENCH"
    sc.display.shading.light="STUDIO"; sc.display.shading.color_type="MATERIAL"
    sc.render.resolution_x=1280; sc.render.resolution_y=720
    sc.render.filepath=path; sc.render.image_settings.file_format="PNG"
    bpy.ops.render.render(write_still=True); print("WROTE", path)
# look down through openings toward seats
shot(ROOT+r"\c919-detail-cockpit-interior.png", (0.0, 20.5, 2.4), (0.0, 16.5, 0.7), 45)
shot(ROOT+r"\c919-detail-windshield-front.png", (0.15, 23.5, 1.8), (0.0, 16.55, 1.0), 48)
# with glass back for exterior check
if ws: ws.hide_render=False
shot(ROOT+r"\c919-detail-windshield-side.png", (4.8, 20.0, 1.6), (0.0, 16.8, 1.05), 48)
shot(ROOT+r"\c919-preview-inside1.png", (6.5, 21.5, 3.0), (0.0, 16.5, 0.8), 40)
print("DONE")

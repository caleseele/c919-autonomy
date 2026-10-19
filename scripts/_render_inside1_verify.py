"""INSIDE1 verify: hide glass, render through punched openings; also EEVEE alpha peek."""
import math
import os
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

# Count Nose boundary edges in windshield band (proxy for openings)
nose = bpy.data.objects.get("Nose")
bound = 0
if nose:
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    for e in bm.edges:
        if not e.is_boundary:
            continue
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        if 15.4 <= mid.y <= 17.8:
            bound += 1
    bm.free()
print("NOSE_BOUNDARY_EDGES_WS_BAND", bound)

# Hide glass for cavity check (should reveal seats through holes)
ws = bpy.data.objects.get("Windshield")
if ws:
    ws.hide_render = True
    ws.hide_viewport = True

world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.60, 0.68, 1)

light_data = bpy.data.lights.new("Key", "AREA")
light_data.energy = 1200
light_data.size = 10
light = bpy.data.objects.new("Key", light_data)
bpy.context.collection.objects.link(light)
light.location = (4, 14, 6)

def shot(path, loc, target, lens=55):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

shot(os.path.join(OUT, "c919-detail-cockpit-interior.png"), (0.2, 23.5, 1.55), (0, 16.55, 0.9), 58)
shot(os.path.join(OUT, "c919-detail-windshield-front.png"), (0.15, 24.8, 1.55), (0, 16.7, 1.05), 52)

# Unhide glass; try EEVEE for transparency
if ws:
    ws.hide_render = False
    ws.hide_viewport = False
sc = bpy.context.scene
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except Exception:
        sc.render.engine = "BLENDER_WORKBENCH"
sc.eevee.use_raytracing = True if hasattr(sc, "eevee") else None
# ensure film transparent off
cam_data = bpy.data.cameras.new("CamE")
cam_data.lens = 50
cam = bpy.data.objects.new("CamE", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0.25, 24.2, 1.5)
cam.rotation_euler = (Vector((0, 16.6, 1.0)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sc.render.filepath = os.path.join(OUT, "c919-preview-inside1.png")
bpy.ops.render.render(write_still=True)
print("WROTE", sc.render.filepath, "engine", sc.render.engine)
print("INSIDE1_VERIFY_DONE")

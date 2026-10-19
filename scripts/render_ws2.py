# -*- coding: utf-8 -*-
import bpy, math, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

keys = [
    "Fuselage", "Nose", "Windshield", "CockpitFrames", "CockpitMask",
    "Doors", "DoorFrames", "Windows", "Wing_R", "Wing_L", "VerticalTail",
    "Engine_R", "Stab_R",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    if not o:
        missing += 1
        print("MISSING", n)
    else:
        print("OK", n, len(o.data.polygons) if o.type == "MESH" else 0)
print("MISSING_COUNT", missing)

# Confirm no giant hole: Nose verts near windshield belt should exist on crown
nose = bpy.data.objects.get("Nose")
if nose:
    crown = 0
    for v in nose.data.vertices:
        w = nose.matrix_world @ v.co
        if 16.0 < w.y < 17.5 and w.z > 1.2:
            crown += 1
    print("NOSE_CROWN_VERTS_IN_WS_BELT", crown)

ps = bpy.data.objects.get("PilotSeats")
if ps:
    print("PilotSeats hide_render", ps.hide_render, "hide_viewport", ps.hide_viewport)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 36
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("WWS2") if "WWS2" not in bpy.data.worlds else bpy.data.worlds["WWS2"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.45, 0.52, 0.60, 1)
    bg.inputs[1].default_value = 1.05
for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 5.5, (math.radians(48), 0, math.radians(32)))
add_sun("PrevFill", 1.8, (math.radians(20), math.radians(150), 0))
cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=42):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

# Match user fail angle (high 3/4 into cockpit)
render(os.path.join(OUT, "c919-detail-windshield-34.png"), (7.5, 21.5, 5.2), (0.3, 16.8, 1.0), 42)
render(os.path.join(OUT, "c919-detail-windshield-side.png"), (12.5, 17.2, 1.5), (0.0, 17.0, 0.9), 50)
render(os.path.join(OUT, "c919-detail-nose-top.png"), (0.0, 16.9, 13.5), (0.0, 16.9, 0.4), 48)
render(os.path.join(OUT, "c919-preview-ws2.png"), (20.0, 26.0, 9.5), (1.0, 6.0, 1.0), 38)
print("WS2_RENDER_DONE")

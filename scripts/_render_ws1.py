# -*- coding: utf-8 -*-
"""WS1 windshield exterior audit renders."""
import os
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "c919.blend"))

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("WS1Cam")
cam = bpy.data.objects.new("WS1CamObj", cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam

world = bpy.data.worlds.new("WS1W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.44, 0.47, 1)

sun = bpy.data.objects.new("WS1Sun", bpy.data.lights.new("WS1SunL", "SUN"))
sun.data.energy = 3.2
sun.rotation_euler = (0.9, 0.2, 0.4)
bpy.context.scene.collection.objects.link(sun)


def shoot(name, eye, tgt, lens=40):
    cam.location = Vector(eye)
    cam.data.lens = lens
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    final = scene.render.filepath
    if not final.lower().endswith(".png"):
        guess = final + ".png"
        final = guess if os.path.exists(guess) else final
    print("OK", name, os.path.getsize(final) if os.path.exists(final) else "?")


# Overview
shoot("c919-preview-ws1.png", (10.5, 20.0, 5.5), (0.0, 15.5, 0.9), 42)
# Front-on windshield (frames / 4 panes / center post)
shoot("c919-detail-windshield-front.png", (0.05, 23.5, 2.15), (0.0, 16.9, 1.25), 35)
# Side / 3/4 nose-roof blend
shoot("c919-detail-windshield-side.png", (6.8, 21.0, 2.6), (0.0, 16.6, 1.15), 34)
# Wipers close-up
shoot("c919-detail-wipers.png", (0.35, 22.0, 1.95), (0.0, 17.05, 1.25), 32)

needed = [
    "Nose",
    "Windshield",
    "WindshieldWipers",
    "CockpitFrames",
    "GlareShield",
    "PilotSeats",
]
missing = [n for n in needed if bpy.data.objects.get(n) is None]
print("MISSING_OBJECTS", missing)
print("MISSING_COUNT", len(missing))
print("GLB_SIZE", os.path.getsize(os.path.join(OUT, "c919.glb")))

# Quick frame thickness heuristic: bbox of CockpitFrames
cf = bpy.data.objects.get("CockpitFrames")
if cf is not None:
    dims = cf.dimensions
    print("FRAMES_DIMS", tuple(round(v, 4) for v in dims))
wp = bpy.data.objects.get("WindshieldWipers")
if wp is not None:
    print("WIPERS_DIMS", tuple(round(v, 4) for v in wp.dimensions))
    print("WIPERS_VERTS", len(wp.data.vertices))

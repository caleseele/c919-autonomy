# -*- coding: utf-8 -*-
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

cam = bpy.data.objects.new("C", bpy.data.cameras.new("Cd"))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.42, 0.45, 1)

sun = bpy.data.objects.new("S", bpy.data.lights.new("Sd", "SUN"))
sun.data.energy = 3.0
bpy.context.scene.collection.objects.link(sun)


def shoot(name, eye, tgt, lens=40):
    cam.location = Vector(eye)
    cam.data.lens = lens
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    path = scene.render.filepath
    if not path.lower().endswith(".png"):
        path = path + ".png" if not os.path.exists(path) else path
    # Blender may append extension
    final = scene.render.filepath
    if not final.lower().endswith((".png", ".jpg")):
        guess = final + ".png"
        final = guess if os.path.exists(guess) else final
    print("OK", name, os.path.getsize(final) if os.path.exists(final) else "?")


# Overview 3/4 nose
shoot("c919-preview-cockpit3.png", (10.5, 20.0, 5.5), (0.0, 15.5, 0.9), 42)
# Wipers close-up
shoot("c919-detail-wipers.png", (0.15, 22.2, 1.85), (0.0, 17.0, 1.20), 38)
# Windshield / frames / openings
shoot("c919-detail-windshield.png", (3.2, 21.5, 2.8), (0.0, 16.8, 1.1), 36)
# Cockpit interior (hide glass for clearer seat/dash read)
ws = bpy.data.objects.get("Windshield")
if ws is not None:
    ws.hide_render = True
shoot("c919-detail-cockpit-interior.png", (0.55, 19.6, 2.40), (0.0, 16.30, 0.70), 28)

# Object presence audit
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
print("HAS_WIPERS", bpy.data.objects.get("WindshieldWipers") is not None)
print("HAS_SEATS", bpy.data.objects.get("PilotSeats") is not None)
print("HAS_GLARE", bpy.data.objects.get("GlareShield") is not None)

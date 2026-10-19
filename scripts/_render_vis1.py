# -*- coding: utf-8 -*-
"""Render vis1 audit previews + door/wing Z check."""
import math
import os
import bpy
from mathutils import Vector, Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)

# Geometry audit: door vs wing upper at overwing Y
door = bpy.data.objects.get("Doors")
wing_r = bpy.data.objects.get("Wing_R")
wipers = bpy.data.objects.get("WindshieldWipers")
seats = bpy.data.objects.get("PilotSeats")
glare = bpy.data.objects.get("GlareShield")
ws = bpy.data.objects.get("Windshield")

def world_bbox(obj):
    if obj is None:
        return None
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

def verts_near_y(obj, y0, tol=0.35, x_min=1.5):
    if obj is None:
        return []
    out = []
    mw = obj.matrix_world
    mesh = obj.data
    for v in mesh.vertices:
        w = mw @ v.co
        if abs(w.y - y0) <= tol and w.x >= x_min:
            out.append(w)
    return out

print("OBJ_CHECK doors", door is not None, "wipers", wipers is not None,
      "seats", seats is not None, "glare", glare is not None, "ws", ws is not None)

db = world_bbox(door)
wb = world_bbox(wing_r)
print("DOOR_BBOX", db)
print("WING_R_BBOX", wb)

# Sample wing upper Z near fuselage at y~1.65
wing_pts = verts_near_y(wing_r, 1.65, tol=0.5, x_min=1.2)
if wing_pts:
    zmax = max(p.z for p in wing_pts)
    zmin = min(p.z for p in wing_pts)
    print("WING_NEAR_OVERWING_Z", round(zmin, 3), round(zmax, 3), "n", len(wing_pts))
else:
    print("WING_NEAR_OVERWING_Z none")

# Door verts near overwing (y~1.65, +X)
door_pts = []
if door:
    mw = door.matrix_world
    for v in door.data.vertices:
        w = mw @ v.co
        if abs(w.y - 1.65) < 0.6 and w.x > 1.5:
            door_pts.append(w)
if door_pts:
    print("DOOR_OVERWING_Z", round(min(p.z for p in door_pts), 3),
          round(max(p.z for p in door_pts), 3), "n", len(door_pts))
else:
    print("DOOR_OVERWING_Z none")

# Setup EEVEE-ish quick viewport render via Cycles/Workbench
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

# Ensure camera
cam_data = bpy.data.cameras.new("Vis1Cam")
cam = bpy.data.objects.new("Vis1Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 50

# World gray
world = bpy.data.worlds.new("Vis1World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.35, 0.37, 0.40, 1)
    bg.inputs[1].default_value = 1.0

# Soft light
for name in ("Vis1Key", "Vis1Fill"):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
key = bpy.data.objects.new("Vis1Key", bpy.data.lights.new("Vis1KeyL", "AREA"))
key.data.energy = 800
key.data.size = 8
key.location = (8, 12, 10)
bpy.context.scene.collection.objects.link(key)
fill = bpy.data.objects.new("Vis1Fill", bpy.data.lights.new("Vis1FillL", "AREA"))
fill.data.energy = 300
fill.data.size = 10
fill.location = (-6, -4, 6)
bpy.context.scene.collection.objects.link(fill)

def look_at(cam_obj, eye, target):
    cam_obj.location = eye
    direction = Vector(target) - Vector(eye)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

shots = [
    ("c919-preview-vis1.png", (14.0, 18.0, 7.5), (0.0, 2.0, 0.5)),
    ("c919-detail-door-overwing.png", (7.5, 6.0, 2.8), (2.0, 1.65, 0.7)),
    ("c919-detail-wipers.png", (1.2, 22.5, 2.2), (0.0, 17.0, 1.2)),
    ("c919-detail-cockpit-interior.png", (0.15, 21.8, 1.6), (0.0, 16.7, 0.7)),
]

for fname, eye, target in shots:
    look_at(cam, eye, target)
    out_path = os.path.join(OUT, fname)
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", out_path, os.path.getsize(out_path) if os.path.exists(out_path) else 0)

glb = os.path.join(OUT, "c919.glb")
print("GLB_SIZE", os.path.getsize(glb))
print("VIS1_AUDIT_DONE")

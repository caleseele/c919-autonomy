# -*- coding: utf-8 -*-
import math, os
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

door = bpy.data.objects.get("Doors")
wing_r = bpy.data.objects.get("Wing_R")

def verts_near(obj, y0, tol, x_min):
    mw = obj.matrix_world
    pts = []
    for v in obj.data.vertices:
        w = mw @ v.co
        if abs(w.y - y0) <= tol and w.x >= x_min:
            pts.append(w)
    return pts

wing_pts = verts_near(wing_r, 1.80, 0.55, 1.2)
door_pts = verts_near(door, 1.80, 0.55, 1.5)
print("WING_Z", round(min(p.z for p in wing_pts),3), round(max(p.z for p in wing_pts),3) if wing_pts else None)
print("DOOR_Z", round(min(p.z for p in door_pts),3), round(max(p.z for p in door_pts),3) if door_pts else None)
print("CLEARANCE", round(min(p.z for p in door_pts) - max(p.z for p in wing_pts), 3) if wing_pts and door_pts else None)

scene = bpy.context.scene
# Prefer EEVEE for glass alpha
engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
if "BLENDER_EEVEE_NEXT" in engines:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
elif "BLENDER_EEVEE" in engines:
    scene.render.engine = "BLENDER_EEVEE"
else:
    scene.render.engine = "BLENDER_WORKBENCH"

scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

# Force material alpha for glass-like mats
for mat in bpy.data.materials:
    name = mat.name.lower()
    if "glass" in name or "cockpit" in name:
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
        try:
            mat.surface_render_method = "BLENDED"
        except Exception:
            pass

cam_data = bpy.data.cameras.new("Vis1Cam2")
cam = bpy.data.objects.new("Vis1Cam2", cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 45

world = bpy.data.worlds.new("Vis1World2")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.42, 0.44, 0.47, 1)
    bg.inputs[1].default_value = 0.9

key = bpy.data.objects.new("K2", bpy.data.lights.new("K2L", "AREA"))
key.data.energy = 1200
key.data.size = 10
key.location = (10, 14, 9)
bpy.context.scene.collection.objects.link(key)
fill = bpy.data.objects.new("F2", bpy.data.lights.new("F2L", "AREA"))
fill.data.energy = 450
fill.data.size = 12
fill.location = (-8, -2, 7)
bpy.context.scene.collection.objects.link(fill)

def look_at(eye, target):
    cam.location = eye
    direction = Vector(target) - Vector(eye)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

shots = [
    # high 3/4: door should clear wing
    ("c919-preview-vis1.png", (12.0, 14.0, 6.5), (0.5, 2.0, 0.8)),
    # door detail from ABOVE-outboard so wing doesn't foreground-clip
    ("c919-detail-door-overwing.png", (6.5, 5.5, 4.2), (2.05, 1.80, 0.95)),
    # side orthographic-ish
    ("c919-detail-door-side.png", (9.5, 1.80, 1.0), (0.0, 1.80, 0.9)),
    ("c919-detail-wipers.png", (0.9, 23.0, 2.0), (0.0, 17.1, 1.15)),
    ("c919-detail-cockpit-interior.png", (0.05, 21.2, 1.35), (0.0, 16.7, 0.65)),
]

for fname, eye, target in shots:
    look_at(eye, target)
    path = os.path.join(OUT, fname)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", fname, os.path.getsize(path))

print("GLB_SIZE", os.path.getsize(os.path.join(OUT, "c919.glb")))

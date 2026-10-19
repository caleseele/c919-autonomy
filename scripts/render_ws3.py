# -*- coding: utf-8 -*-
"""ws3 audit renders: transparent 4-pane see-through + MISSING_COUNT."""
import bpy, math, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

keys = [
    "Fuselage", "Nose", "WS_L", "WS_R", "SW_L", "SW_R",
    "CockpitFrames", "CockpitCabin", "GlareShield", "PilotSeats",
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

# CockpitMask must be gone
if bpy.data.objects.get("CockpitMask"):
    print("FAIL CockpitMask still present")
    missing += 1
else:
    print("OK CockpitMask absent")

# Glass transmission check
mat = bpy.data.materials.get("CockpitGlass")
if mat and mat.use_nodes:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tw = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
    print("CockpitGlass Transmission", tw.default_value if tw else None)
    print("CockpitGlass blend", getattr(mat, "blend_method", None))

# Openings: Nose should have fewer crown verts in kill region than continuous skin
nose = bpy.data.objects.get("Nose")
if nose:
    crown = 0
    holeish = 0
    for v in nose.data.vertices:
        w = nose.matrix_world @ v.co
        if 16.2 < w.y < 17.4 and abs(w.x) < 1.2 and w.z > 1.3:
            crown += 1
    print("NOSE_VERTS_IN_WS_BELT_CENTER", crown)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 48
scene.cycles.use_denoising = False
scene.render.film_transparent = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("WWS3") if "WWS3" not in bpy.data.worlds else bpy.data.worlds["WWS3"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.55, 0.62, 0.70, 1)
    bg.inputs[1].default_value = 1.2
for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 6.0, (math.radians(50), 0, math.radians(35)))
add_sun("PrevFill", 2.2, (math.radians(25), math.radians(155), 0))
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

# 45° see-through into cockpit
render(os.path.join(OUT, "c919-detail-windshield-34.png"), (7.2, 21.2, 4.6), (0.2, 16.9, 1.05), 40)
render(os.path.join(OUT, "c919-detail-windshield-side.png"), (11.5, 17.0, 1.4), (0.0, 17.0, 0.95), 48)
render(os.path.join(OUT, "c919-detail-nose-top.png"), (0.0, 16.9, 12.5), (0.0, 16.9, 0.5), 48)
render(os.path.join(OUT, "c919-preview-ws3.png"), (19.5, 25.5, 9.0), (1.0, 6.0, 1.0), 38)
print("WS3_RENDER_DONE MISSING_COUNT", missing)

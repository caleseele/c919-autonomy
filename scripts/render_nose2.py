# -*- coding: utf-8 -*-
"""nose2 audit renders: top-down + 3/4 windshield + preview."""
import bpy, math, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
OUT = os.path.join(ROOT, "public", "models")
bpy.ops.wm.open_mainfile(filepath=BLEND)

keys = [
    "Fuselage", "Nose", "Windshield", "CockpitFrames", "Doors", "DoorFrames",
    "Windows", "Wing_R", "Wing_L", "VerticalTail", "Stab_R", "Engine_R",
    "CockpitSeats", "GlareShield", "WindshieldWipers",
]
# seats may be named differently
extra = [n for n in bpy.data.objects.keys() if "Seat" in n or "Pilot" in n or "Glare" in n]
print("SEAT_LIKE", extra)
missing = 0
for n in ["Fuselage", "Nose", "Windshield", "CockpitFrames", "Doors", "DoorFrames",
          "Windows", "Wing_R", "Wing_L", "VerticalTail", "Engine_R"]:
    o = bpy.data.objects.get(n)
    if not o:
        missing += 1
        print("MISSING", n)
    else:
        print("OK", n, len(o.data.polygons) if o.type == "MESH" else 0)
print("MISSING_COUNT", missing)

# Sample top-down outline: max |x| of Nose+Windshield along y bins
nose = bpy.data.objects.get("Nose")
ws = bpy.data.objects.get("Windshield")

def sample_halfwidth(obj, y0, y1, bins=24):
    if not obj:
        return
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    for i in range(bins):
        ya = y0 + (y1 - y0) * i / bins
        yb = y0 + (y1 - y0) * (i + 1) / bins
        band = [p for p in pts if ya <= p.y < yb and p.z > -0.2]
        if not band:
            continue
        # crown-ish: high z
        crown = [p for p in band if p.z > 0.5 * max(q.z for q in band)]
        use = crown or band
        mx = max(abs(p.x) for p in use)
        mz = max(p.z for p in use)
        print(f"OUTLINE {obj.name} y={0.5*(ya+yb):.2f} half_x={mx:.3f} max_z={mz:.3f}")

sample_halfwidth(nose, 14.8, 20.0, 18)
sample_halfwidth(ws, 15.4, 17.8, 10)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 28
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("WN2") if "WN2" not in bpy.data.worlds else bpy.data.worlds["WN2"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.16, 0.20, 0.30, 1)
    bg.inputs[1].default_value = 1.0
for name in list(bpy.data.objects.keys()):
    if name.startswith("Prev"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    ld = bpy.data.lights.new(name=name, type="SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.rotation_euler = rot

add_sun("PrevKey", 5.0, (math.radians(55), 0, math.radians(25)))
add_sun("PrevFill", 1.6, (math.radians(15), math.radians(155), 0))
cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=40):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

# Top-down cockpit (matches user failure screenshot angle)
render(os.path.join(OUT, "c919-detail-nose-top.png"), (0.0, 16.8, 14.0), (0.0, 16.8, 0.5), 50)
# 3/4 windshield
render(os.path.join(OUT, "c919-detail-windshield-34.png"), (8.5, 22.0, 4.5), (0.2, 17.0, 1.2), 45)
# Side nose
render(os.path.join(OUT, "c919-detail-nose-side.png"), (14.0, 17.5, 1.2), (0.0, 17.5, 0.8), 55)
# Preview
render(os.path.join(OUT, "c919-preview-nose2.png"), (22.0, 28.0, 10.0), (1.0, 8.0, 1.0), 38)
print("NOSE2_RENDER_DONE")

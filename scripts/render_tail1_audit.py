import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.render.resolution_x = 1400
scene.render.resolution_y = 800
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.48, 0.54, 0.62, 1)
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


add_sun("PrevKey", 5.0, (math.radians(50), 0, math.radians(30)))
add_sun("PrevFill", 1.8, (math.radians(20), math.radians(145), 0))

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


# Side view of whole tail (fin profile + HT)
render(f"{OUT_DIR}\\c919-detail-tail-side.png", (28.0, -16.5, 3.5), (0.0, -16.5, 3.5), 42)
# Low rear 3/4 like the reference photo
render(f"{OUT_DIR}\\c919-detail-tail-rear.png", (12.0, -32.0, 2.2), (0.0, -17.0, 3.0), 40)
# Top view of horizontal stabs
render(f"{OUT_DIR}\\c919-detail-htail-top.png", (0.0, -16.5, 28.0), (0.0, -16.5, 0.0), 38)
# Beauty 3/4 of whole aircraft focusing aft
render(f"{OUT_DIR}\\c919-preview-tail1.png", (22.0, -28.0, 10.0), (0.0, -10.0, 2.0), 36)

keys = [
    "VerticalTail", "Rudder", "Stab_R", "Stab_L", "TailCone",
    "Fuselage", "Nose", "Wing_R", "Wing_L", "Engine_R", "Engine_L",
    "Doors", "Windshield", "Gear_R", "AntennasAPU",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    ok = o is not None
    if not ok:
        missing += 1
    npoly = len(o.data.polygons) if ok and o.type == "MESH" else 0
    print("OBJ", n, "OK" if ok else "MISSING", npoly)
print("MISSING_COUNT", missing)

for name in ("VerticalTail", "Stab_R", "Stab_L", "TailCone", "Fuselage", "Rudder", "Wing_R", "Nose"):
    obj = bpy.data.objects.get(name)
    if not obj:
        continue
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    print(
        f"BBOX {name} x=[{min(xs):.2f},{max(xs):.2f}] "
        f"y=[{min(ys):.2f},{max(ys):.2f}] z=[{min(zs):.2f},{max(zs):.2f}]"
    )

# Soft ACAP checks
nose = bpy.data.objects.get("Nose")
fuse = bpy.data.objects.get("Fuselage")
vt = bpy.data.objects.get("VerticalTail")
ht = bpy.data.objects.get("Stab_R")
if nose and fuse:
    nb = [nose.matrix_world @ Vector(c) for c in nose.bound_box]
    fb = [fuse.matrix_world @ Vector(c) for c in fuse.bound_box]
    y_max = max(v.y for v in nb)
    y_min = min(v.y for v in fb)
    print(f"SOFT_LEN approx={y_max - y_min:.2f}m (ACAP 38.90)")
if vt:
    zb = [vt.matrix_world @ Vector(c) for c in vt.bound_box]
    print(f"SOFT_FIN_TIP_Z={max(v.z for v in zb):.2f}")
if ht:
    xb = [ht.matrix_world @ Vector(c) for c in ht.bound_box]
    print(f"SOFT_HT_HALFSPAN={max(abs(v.x) for v in xb):.2f} (span~{2*max(abs(v.x) for v in xb):.2f})")

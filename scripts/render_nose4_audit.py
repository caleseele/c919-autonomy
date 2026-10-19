import bpy
import math
from mathutils import Vector

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUT_DIR = r"C:\Users\希儿\Projects\c919-autonomy\public\models"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("W") if "W" not in bpy.data.worlds else bpy.data.worlds["W"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.52, 0.58, 0.66, 1)
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

add_sun("PrevKey", 4.5, (math.radians(42), 0, math.radians(20)))
add_sun("PrevFill", 1.6, (math.radians(12), math.radians(155), 0))

cam_data = bpy.data.cameras.new("PrevCam")
cam = bpy.data.objects.new("PrevCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, loc, look, lens=40):
    cam_data.lens = lens
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Z").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

render(f"{OUT_DIR}\\c919-detail-nose-side.png", (16.5, 17.6, 0.55), (0.0, 17.6, 0.55), 50)
render(f"{OUT_DIR}\\c919-detail-nose-front.png", (3.2, 26.8, 0.85), (0.0, 17.3, 0.40), 38)
render(f"{OUT_DIR}\\c919-detail-windshield.png", (3.6, 22.5, 1.55), (0.0, 17.0, 0.70), 46)
render(f"{OUT_DIR}\\c919-detail-door-window.png", (7.2, 12.9, 0.55), (2.08, 12.95, 0.20), 48)
render(f"{OUT_DIR}\\c919-preview-nose4.png", (16.5, 24.0, 5.8), (0.0, 14.0, 0.6), 40)

keys = [
    "Nose", "Windshield", "CockpitFrames", "PitotProbes",
    "Doors", "DoorFrames", "Windows", "WindowFrames", "PanelLines",
    "Fuselage", "Engine_R", "Wing_R", "Gear_Nose",
]
missing = 0
for n in keys:
    o = bpy.data.objects.get(n)
    ok = o is not None
    if not ok:
        missing += 1
    npoly = len(o.data.polygons) if ok and o.type == "MESH" else 0
    print("OBJ", n, "OK" if ok else "MISSING", npoly)

nose = bpy.data.objects.get("Nose")
if nose:
    buckets = {}
    for v in nose.data.vertices:
        yk = round(v.co.y, 1)
        buckets.setdefault(yk, []).append(v.co)
    for yk in sorted(buckets.keys(), reverse=True):
        if yk < 14.5:
            continue
        pts = buckets[yk]
        xs = [abs(p.x) for p in pts]
        zs = [p.z for p in pts]
        print(f"CROWN y={yk:.1f} max|x|={max(xs):.3f} maxz={max(zs):.3f} minz={min(zs):.3f}")
    # tip extremes
    ys = [v.co.y for v in nose.data.vertices]
    tip_y = max(ys)
    tip_verts = [v.co for v in nose.data.vertices if abs(v.co.y - tip_y) < 0.05]
    tip_r = max(math.hypot(v.x, v.z) for v in tip_verts) if tip_verts else 0
    print(f"TIP_Y={tip_y:.3f} TIP_NEAR_R={tip_r:.3f}")
print("MISSING_COUNT", missing)

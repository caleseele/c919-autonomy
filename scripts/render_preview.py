import bpy
import math
from mathutils import Vector
import bmesh

BLEND = r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend"
OUTS = {
    "side": r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919-preview-side.png",
    "rear": r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919-preview-rear.png",
    "top": r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919-preview-top.png",
    "main": r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919-preview.png",
}

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("PreviewWorld") if "PreviewWorld" not in bpy.data.worlds else bpy.data.worlds["PreviewWorld"]
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.015, 0.04, 0.10, 1)
    bg.inputs[1].default_value = 0.8

for name in list(bpy.data.objects.keys()):
    if name.startswith("PreviewLight") or name in ("PreviewCam", "Ground"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

def add_sun(name, energy, rot):
    light_data = bpy.data.lights.new(name=name, type="SUN")
    light_data.energy = energy
    obj = bpy.data.objects.new(name, light_data)
    scene.collection.objects.link(obj)
    obj.rotation_euler = rot

add_sun("PreviewLight_Key", 4.0, (math.radians(50), math.radians(15), math.radians(35)))
add_sun("PreviewLight_Fill", 1.4, (math.radians(70), math.radians(-40), math.radians(-20)))

bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=16, y_segments=16, size=45)
me = bpy.data.meshes.new("GroundMesh")
bm.to_mesh(me); bm.free()
ground = bpy.data.objects.new("Ground", me)
scene.collection.objects.link(ground)
ground.location = (0, 0, -4.2)
gmat = bpy.data.materials.new("GroundMat")
gmat.use_nodes = True
gbsdf = gmat.node_tree.nodes.get("Principled BSDF")
if gbsdf:
    gbsdf.inputs["Base Color"].default_value = (0.03, 0.08, 0.16, 1)
    gbsdf.inputs["Roughness"].default_value = 0.9
me.materials.append(gmat)

cam_data = bpy.data.cameras.new("PreviewCam")
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(path, location, look_at, lens=40):
    cam_data.lens = lens
    cam.location = Vector(location)
    direction = Vector(look_at) - Vector(location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)

# True side profile (camera on +X)
render(OUTS["side"], (48, -1, 5), (0, -1, 2.5), lens=38)
# Rear 3/4
render(OUTS["rear"], (16, -34, 9), (0, -14, 3.5), lens=40)
# Top
render(OUTS["top"], (0, -2, 52), (0, -2, 0), lens=35)
# Beauty front 3/4
render(OUTS["main"], (30, 24, 11), (0, -2, 2.5), lens=40)

for name in ("VerticalTail", "Wing_R", "Stab_R", "Rudder", "Fuselage"):
    obj = bpy.data.objects.get(name)
    if not obj:
        print("MISSING", name); continue
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]; ys = [v.y for v in bbox]; zs = [v.z for v in bbox]
    print(f"BBOX {name} x=[{min(xs):.2f},{max(xs):.2f}] y=[{min(ys):.2f},{max(ys):.2f}] z=[{min(zs):.2f},{max(zs):.2f}]")

# Verify fin root is below crown at several Y stations
vt = bpy.data.objects.get("VerticalTail")
if vt:
    root_candidates = [vt.matrix_world @ Vector(c) for c in vt.bound_box]
    # sample mesh verts with low z
    mw = vt.matrix_world
    zs_by_y = {}
    for v in vt.data.vertices:
        w = mw @ v.co
        key = round(w.y, 1)
        zs_by_y.setdefault(key, []).append(w.z)
    for y in sorted(zs_by_y.keys()):
        if -19.0 <= y <= -14.0:
            zmin = min(zs_by_y[y])
            # compare to approx crown
            print(f"FIN_ROOT_SAMPLE y={y:.1f} zmin={zmin:.2f}")

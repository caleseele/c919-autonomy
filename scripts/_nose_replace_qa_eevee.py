import bpy, json, os, math
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
PREV = os.path.join(ROOT, "public", "models", "nose-replace")
bpy.ops.wm.open_mainfile(filepath=BLEND)

objs = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs=[p.x for p in bb]; ys=[p.y for p in bb]; zs=[p.z for p in bb]
    objs.append({
        "name": o.name,
        "hide": o.hide_render,
        "verts": len(o.data.vertices),
        "mats": [m.name if m else None for m in o.data.materials],
        "bbox": [min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)],
    })
print("OBJECTS", json.dumps(objs, ensure_ascii=False, indent=2))

# EEVEE renders of nose
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

# find nose look-at
nose = bpy.data.objects.get("Nose") or bpy.data.objects.get("REF_机头蒙皮")
glass = bpy.data.objects.get("CockpitGlass_REF") or bpy.data.objects.get("REF_风挡玻璃")
pts = []
for o in (nose, glass):
    if not o: continue
    for c in o.bound_box:
        pts.append(o.matrix_world @ Vector(c))
cy = sum(p.y for p in pts)/len(pts)
cz = sum(p.z for p in pts)/len(pts)
cx = sum(p.x for p in pts)/len(pts)
look = Vector((cx, cy, cz))

if not any(o.type=="LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("QA_Sun2", "SUN"); ld.energy=4
    lo = bpy.data.objects.new("QA_Sun2", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(50), math.radians(15), math.radians(25))

def cam_at(loc, name):
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(look)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    cd.lens = 50
    return cam

views = {
    "eevee_side": Vector((12, look.y, look.z+0.2)),
    "eevee_front": Vector((0, look.y+12, look.z+0.4)),
    "eevee_oblique45": Vector((8.5, look.y+8.5, look.z+1.0)),
}
for n, loc in views.items():
    cam = cam_at(loc, "C_"+n)
    scene.camera = cam
    out = os.path.join(PREV, f"{n}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("WROTE", out)
    bpy.data.objects.remove(cam, do_unlink=True)

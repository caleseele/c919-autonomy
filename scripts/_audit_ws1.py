import bpy, math
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
for name in ("Windshield","CockpitFrames","WindshieldWipers","Nose"):
    ob = bpy.data.objects.get(name)
    if not ob:
        print("MISSING", name); continue
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs=[v.x for v in bb]; ys=[v.y for v in bb]; zs=[v.z for v in bb]
    print(name, "verts", len(ob.data.vertices), "bbox",
          (round(min(xs),3),round(max(xs),3)),
          (round(min(ys),3),round(max(ys),3)),
          (round(min(zs),3),round(max(zs),3)))
    mats=[m.name if m else None for m in ob.data.materials]
    print("  mats", mats)
wp=bpy.data.objects["WindshieldWipers"]
# sample a few verts
coords=sorted([(round(v.co.x,3),round(v.co.y,3),round(v.co.z,3)) for v in wp.data.vertices], key=lambda t:t[1])
print("WIPER_Y_SPAN", coords[0], coords[-1])
print("WIPER_sample", coords[::max(1,len(coords)//8)])

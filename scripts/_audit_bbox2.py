import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
for n in ("PilotSeats","GlareShield","Windshield","Nose"):
    o = bpy.data.objects.get(n)
    pts = [o.matrix_world @ Vector(corner) for corner in o.bound_box]
    ys = [p.y for p in pts]; zs = [p.z for p in pts]; xs = [p.x for p in pts]
    print(n, "X", round(min(xs),3), round(max(xs),3), "Y", round(min(ys),3), round(max(ys),3), "Z", round(min(zs),3), round(max(zs),3))
    print(" ", "verts", len(o.data.vertices), "faces", len(o.data.polygons))
# sample seat vertex colors / materials
seats = bpy.data.objects["PilotSeats"]
print("SEAT_MATS", [m.name if m else None for m in seats.data.materials])
gs = bpy.data.objects["GlareShield"]
print("GLARE_MATS", [m.name if m else None for m in gs.data.materials])

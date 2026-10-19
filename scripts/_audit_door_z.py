import bpy, math
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
obj = bpy.data.objects["DoorFrames"]
verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
# overwing +X
cand = [v for v in verts if abs(v.y-1.4)<0.55 and v.x>0]
zs = [v.z for v in cand]
ys = [v.y for v in cand]
print(f"overwing+X frames: n={len(cand)} z=[{min(zs):.3f},{max(zs):.3f}] y=[{min(ys):.3f},{max(ys):.3f}]")
# histogram z
bins = {}
for v in cand:
    b = round(v.z*4)/4
    bins[b] = bins.get(b,0)+1
for b in sorted(bins):
    print(f"  z~{b:+.2f}: {bins[b]}")
# L1
cand = [v for v in verts if abs(v.y-13.05)<0.6 and v.x>0]
zs = [v.z for v in cand]
print(f"L1+X frames: n={len(cand)} z=[{min(zs):.3f},{max(zs):.3f}]")

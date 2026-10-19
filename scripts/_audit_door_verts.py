import bpy
from mathutils import Vector
import math

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")

def sample(name, n=8):
    obj = bpy.data.objects[name]
    me = obj.data
    verts = [obj.matrix_world @ v.co for v in me.vertices]
    # pick verts near overwing y~1.4, +X
    cand = [v for v in verts if abs(v.y - 1.4) < 0.5 and v.x > 0]
    cand.sort(key=lambda v: -v.z)
    print(f"=== {name} total={len(verts)} near_overwing+={len(cand)}")
    for v in cand[:n]:
        # expected radius ~2.06
        r = math.hypot(v.x, v.z)  # rough if circular at mid
        print(f"  p=({v.x:.3f},{v.y:.3f},{v.z:.3f}) hypot_xz={r:.3f}")

sample("Doors")
sample("DoorFrames")
sample("Fuselage")
# fuselage verts near same
obj = bpy.data.objects["Fuselage"]
verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
cand = [v for v in verts if abs(v.y - 1.4) < 0.15 and v.x > 1.5]
cand.sort(key=lambda v: abs(v.z - 0.5))
print("=== Fuselage near y=1.4 x>1.5")
for v in cand[:6]:
    print(f"  p=({v.x:.3f},{v.y:.3f},{v.z:.3f}) hypot={math.hypot(v.x,v.z):.3f}")

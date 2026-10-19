# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BAK = ROOT + r"\public\models\c919.bak-length-s2.blend"
bpy.ops.wm.open_mainfile(filepath=BAK)

def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs

def bb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)

tip = max(v.y for v in mwv(bpy.data.objects["Nose"]))
print(f"tip={tip:.4f}")

for n in ["Engine_R","Engine_L","EngineLip_R","Fan_R","Pylon_R","Pylon_L",
          "Wing_R","Gear_R","Gear_L","Gear_Nose","Gear_N"]:
    ob = bpy.data.objects.get(n)
    if not ob:
        print(f"[{n}] MISSING")
        continue
    x0,x1,y0,y1,z0,z1 = bb(ob)
    cx = 0.5*(x0+x1)
    print(f"[{n}] x=[{x0:.3f},{x1:.3f}] cx={cx:.3f} y=[{y0:.3f},{y1:.3f}] z=[{z0:.3f},{z1:.3f}] tipLE={tip-y1:.3f} tipTE={tip-y0:.3f} tipC={tip-0.5*(y0+y1):.3f}")

# wing LE at x≈6.07
wv = mwv(bpy.data.objects["Wing_R"])
band = [v for v in wv if abs(v.x - 6.07) < 0.35]
if band:
    print(f"Wing_R @x≈6.07 y=[{min(v.y for v in band):.3f},{max(v.y for v in band):.3f}] LE={tip-max(v.y for v in band):.3f} z=[{min(v.z for v in band):.3f},{max(v.z for v in band):.3f}]")
else:
    # nearest span
    for x0 in [5.0,5.5,6.0,6.5,7.0]:
        b=[v for v in wv if abs(v.x-x0)<0.3]
        if b:
            print(f"Wing_R @x≈{x0} yLE={max(v.y for v in b):.3f} tipLE={tip-max(v.y for v in b):.3f} z=[{min(v.z for v in b):.3f},{max(v.z for v in b):.3f}]")

# ground = main wheel bottom
for gn in ["Gear_R","Gear_L"]:
    g=bpy.data.objects.get(gn)
    if g:
        print(f"ground_candidate {gn} zmin={bb(g)[4]:.4f}")

# list gear-like names
print("gear-ish:", [o.name for o in bpy.data.objects if "Gear" in o.name or "gear" in o.name])
print("engine-ish:", [o.name for o in bpy.data.objects if any(k in o.name for k in ("Engine","Pylon","Fan","Lip"))])

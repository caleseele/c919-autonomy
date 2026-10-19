# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector

def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    mat = ob.matrix_world
    vs = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\public\models\c919.blend")
wv = mwv(bpy.data.objects["Wing_R"])
# wing LE (max Y) vs x
xs = sorted(set(round(v.x, 2) for v in wv))
for x0 in [1.5, 2.0, 3.0, 4.0, 4.2, 4.5, 5.0, 6.0]:
    band = [v for v in wv if abs(v.x - x0) < 0.25]
    if not band:
        print(f"x≈{x0}: no verts")
        continue
    print(f"x≈{x0}: y=[{min(v.y for v in band):.3f},{max(v.y for v in band):.3f}] z=[{min(v.z for v in band):.3f},{max(v.z for v in band):.3f}] n={len(band)}")

pv = mwv(bpy.data.objects["Pylon_R"])
print("Pylon_R full", f"x=[{min(v.x for v in pv):.2f},{max(v.x for v in pv):.2f}] y=[{min(v.y for v in pv):.2f},{max(v.y for v in pv):.2f}] z=[{min(v.z for v in pv):.2f},{max(v.z for v in pv):.2f}]")
# closest wing vert to each pylon top vert
top = [v for v in pv if v.z >= max(p.z for p in pv) - 0.08]
for t in top[::3]:
    best = min(wv, key=lambda w: (w.x - t.x) ** 2 + (w.y - t.y) ** 2 + (w.z - t.z) ** 2)
    dxy = ((best.x - t.x) ** 2 + (best.y - t.y) ** 2) ** 0.5
    print(f"  top({t.x:.2f},{t.y:.2f},{t.z:.2f}) -> wing({best.x:.2f},{best.y:.2f},{best.z:.2f}) dxy={dxy:.3f} dz={t.z-best.z:.3f}")

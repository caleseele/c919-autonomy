# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\public\models\c919.blend")

def mwv(o):
    d = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(d)
    m = e.to_mesh()
    vs = [o.matrix_world @ v.co.copy() for v in m.vertices]
    e.to_mesh_clear()
    return vs

def bb(o):
    p = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [q.x for q in p]; ys = [q.y for q in p]; zs = [q.z for q in p]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

tip = max(v.y for v in mwv(bpy.data.objects["Nose"]))
print("tip", round(tip, 4))
for n in ["Fuselage", "VerticalTail", "Rudder", "Stab_L", "Stab_R", "TailCone", "TailMark", "TailMark_L", "Fuselage_ORIG"]:
    o = bpy.data.objects.get(n)
    if not o:
        print(n, "MISSING")
        continue
    x0, x1, y0, y1, z0, z1 = bb(o)
    nv = len(o.data.vertices) if o.type == "MESH" else 0
    print(f"{n} y=[{y0:.3f},{y1:.3f}] tipLE={tip-y1:.3f} tipTE={tip-y0:.3f} z=[{z0:.3f},{z1:.3f}] verts={nv}")

vt = mwv(bpy.data.objects["VerticalTail"])
zmin = min(p.z for p in vt)
low = [v for v in vt if v.z < zmin + 1.8]
yle = max(v.y for v in low)
print("VT_root_LE_y", round(yle, 4), "tip", round(tip - yle, 4))
st = mwv(bpy.data.objects["Stab_R"])
htle = max(v.y for v in st)
print("HT_LE_y", round(htle, 4), "tip", round(tip - htle, 4), "HT-VT", round((tip - htle) - (tip - yle), 4))
tc = mwv(bpy.data.objects["TailCone"])
tc_end = min(v.y for v in tc)
print("TC_end", round(tc_end, 4), "tip", round(tip - tc_end, 4), "VT_to_TC", round((tip - tc_end) - (tip - yle), 4))
fu = mwv(bpy.data.objects["Fuselage"])
aft = [v for v in fu if v.y < yle + 1e-4]
print("Fuse_ymin", round(min(v.y for v in fu), 4), "aft_of_VTle", len(aft))
# list mesh names containing Tail/Stripe/Title near aft
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type != "MESH":
        continue
    b = bb(o)
    if b[2] < yle + 2:  # ymin near/aft VT
        print("near_aft", o.name, f"y=[{b[2]:.2f},{b[3]:.2f}]")

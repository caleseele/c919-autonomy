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

tip = max(v.y for v in mwv(bpy.data.objects["Nose"]))
print("tip", round(tip, 4), "len", round(tip - min(v.y for v in mwv(bpy.data.objects["TailCone"])), 4))

# combine Fuse + TailCone
verts = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])

def section_stats(td, half=0.15):
    band = [v for v in verts if abs((tip - v.y) - td) <= half]
    if len(band) < 8:
        band = [v for v in verts if abs((tip - v.y) - td) <= half * 2]
    if not band:
        return None
    zs = [v.z for v in band]
    xs = [v.x for v in band]
    return {
        "n": len(band),
        "zmin": min(zs), "zmax": max(zs),
        "h": max(zs) - min(zs),
        "half_w": max(abs(x) for x in xs),
        "xmin": min(xs), "xmax": max(xs),
    }

# constant section ~ tip 20-25
for td in [20, 22, 24, 26]:
    s = section_stats(td)
    print(f"td={td}", s)

print("--- aft stations ---")
for td in [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 38.5, 38.84]:
    s = section_stats(td, 0.12)
    if s:
        print(f"td={td:.2f} n={s['n']} belly_z={s['zmin']:.3f} back_z={s['zmax']:.3f} h={s['h']:.3f} half_w={s['half_w']:.3f}")
    else:
        print(f"td={td:.2f} EMPTY")

# tip end of TailCone
tc = mwv(bpy.data.objects["TailCone"])
tc_end = min(v.y for v in tc)
tip_band = [v for v in tc if v.y < tc_end + 0.25]
print("TC_end_y", round(tc_end, 4), "tip_dist", round(tip - tc_end, 4))
if tip_band:
    xs = [v.x for v in tip_band]; zs = [v.z for v in tip_band]
    print("tip_band n", len(tip_band), "xspan", round(max(xs)-min(xs),3), "zspan", round(max(zs)-min(zs),3),
          "approx_diam", round(max(max(xs)-min(xs), max(zs)-min(zs)), 3))

# VT root on back
vt = mwv(bpy.data.objects["VerticalTail"])
zmin = min(v.z for v in vt)
low = [v for v in vt if v.z < zmin + 0.4]
print("VT_root z", round(min(v.z for v in low),3), round(max(v.z for v in low),3), "y", round(min(v.y for v in low),3), round(max(v.y for v in low),3))
# fuse back near VT
fu = mwv(bpy.data.objects["Fuselage"])
for v in low[::max(1,len(low)//5)]:
    col = [p for p in fu if abs(p.y-v.y)<0.3 and abs(p.x-v.x)<0.5]
    if col:
        print("  VT sample vs fuse_zmax", round(v.z,3), round(max(p.z for p in col),3), "gap", round(v.z - max(p.z for p in col),3))

for side in ("R", "L"):
    st = mwv(bpy.data.objects[f"Stab_{side}"])
    root = [v for v in st if abs(v.x) < 1.2]
    print(f"Stab_{side} root |x|min", round(min(abs(v.x) for v in root),3), "xspan", round(min(v.x for v in root),3), round(max(v.x for v in root),3))

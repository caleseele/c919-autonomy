# -*- coding: utf-8 -*-
"""Diagnose §6b: glass Y span, AntennasAPU, antenna bad place."""
import json, os, bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def tip_y():
    n = bpy.data.objects["Nose"]
    vs = [n.matrix_world @ v.co for v in n.data.vertices]
    return max(v.y for v in vs)

def aabb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return {a: [min(getattr(p,a) for p in pts), max(getattr(p,a) for p in pts)] for a in "xyz"}

tip = tip_y()
print(f"tip={tip}", flush=True)

# all mesh summary near station 20-28
rows = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    a = aabb(o)
    st0 = tip - a["y"][1]
    st1 = tip - a["y"][0]
    rows.append((o.name, len(o.data.vertices), st0, st1, a))
    if "Antenna" in o.name or "天线" in o.name or o.name == "AntennasAPU":
        print(f"ANT {o.name} verts={len(o.data.vertices)} st=[{st0:.3f},{st1:.3f}] aabb={a}", flush=True)

# glass real vertex span
g = None
for o in bpy.data.objects:
    if "舷窗" in o.name and "玻璃" in o.name:
        g = o
        break
if g:
    vs = [g.matrix_world @ v.co for v in g.data.vertices]
    ys = [v.y for v in vs]; xs=[v.x for v in vs]; zs=[v.z for v in vs]
    print(f"GLASS verts={len(vs)} y=[{min(ys):.4f},{max(ys):.4f}] st=[{tip-max(ys):.3f},{tip-min(ys):.3f}]", flush=True)
    print(f"  x=[{min(xs):.3f},{max(xs):.3f}] z=[{min(zs):.3f},{max(zs):.3f}]", flush=True)
    # sample 10 centroids-ish by sorting y
    ys_s = sorted(ys)
    print(f"  y percentiles: {[ys_s[i*len(ys_s)//10] for i in range(10)]}", flush=True)

s = None
for o in bpy.data.objects:
    if "舱门" in o.name and "缝" in o.name:
        s = o
        break
if s:
    vs = [s.matrix_world @ v.co for v in s.data.vertices]
    ys = [v.y for v in vs]
    print(f"SEAM verts={len(vs)} y=[{min(ys):.4f},{max(ys):.4f}] st=[{tip-max(ys):.3f},{tip-min(ys):.3f}]", flush=True)

# AntennasAPU detail
apu = bpy.data.objects.get("AntennasAPU")
if apu:
    vs = [apu.matrix_world @ v.co for v in apu.data.vertices]
    print(f"AntennasAPU n={len(vs)}", flush=True)
    for i,v in enumerate(vs):
        print(f"  v{i}: ({v.x:.3f},{v.y:.3f},{v.z:.3f}) st={tip-v.y:.3f}", flush=True)
else:
    print("AntennasAPU MISSING", flush=True)

# list objects with any verts in station 23-26 upper z>0.5
print("--- verts in st 23-26 z>0.8 ---", flush=True)
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    hits = []
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        st = tip - w.y
        if 23.0 <= st <= 26.5 and w.z > 0.8:
            hits.append(w)
    if hits:
        zs = [h.z for h in hits]
        print(f"  {o.name}: n={len(hits)} z=[{min(zs):.3f},{max(zs):.3f}]", flush=True)

out = {"tip": tip, "objects": [{"name":n,"verts":nv,"st":[st0,st1]} for n,nv,st0,st1,a in rows]}
json.dump(out, open(os.path.join(LOG,"section6b_diag.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("DONE", flush=True)

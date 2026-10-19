# -*- coding: utf-8 -*-
import bpy, bmesh, math, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=os.path.join(PROJ,"public","models","c919.blend"))
cut=bpy.data.objects.get("Nose_开窗")
print("matrix_world", list(cut.matrix_world))
print("location", tuple(cut.location), "scale", tuple(cut.scale))

bm=bmesh.new(); bm.from_mesh(cut.data)
print("LOCAL tip_y", max(v.co.y for v in bm.verts), "faces", len(bm.faces), "verts", len(bm.verts))
# verts with max y
tip_y=max(v.co.y for v in bm.verts)
vs=[v for v in bm.verts if v.co.y>tip_y-0.05]
print("local tipband", len(vs), "r_min", min(math.sqrt(v.co.x**2+v.co.z**2) for v in vs), "r_mean", sum(math.sqrt(v.co.x**2+v.co.z**2) for v in vs)/len(vs))
# any vert near axis at high y?
axis=[v for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5]
print("near-axis verts", [(round(v.co.x,4), round(v.co.y,4), round(v.co.z,4)) for v in sorted(axis, key=lambda v:-v.co.y)[:10]])
bm.free()

bm=bmesh.new(); bm.from_mesh(cut.data); bm.transform(cut.matrix_world)
tip_y=max(v.co.y for v in bm.verts)
vs=[v for v in bm.verts if v.co.y>tip_y-0.05]
print("WORLD tip_y", tip_y, "tipband r_min", min(math.sqrt(v.co.x**2+v.co.z**2) for v in vs), "r_mean", sum(math.sqrt(v.co.x**2+v.co.z**2) for v in vs)/len(vs))
bvh=BVHTree.FromBMesh(bm)
for dy in (0.2,0.5,1.0):
    o=Vector((0,tip_y+dy,0)); h=bvh.ray_cast(o, Vector((0,-1,0)))
    if h[0] is None: print(f"ray+{dy} MISS")
    else: print(f"ray+{dy} hit y={h[0].y:.4f} dist={(h[0]-o).length:.4f} r={math.sqrt(h[0].x**2+h[0].z**2):.4f}")
# boundary loops count
used=set(); nloops=0; sizes=[]
for e0 in bm.edges:
    if not e0.is_boundary or e0.index in used: continue
    n=1; used.add(e0.index); start=e0.verts[0]; prev=start; nxt=e0.verts[1]; guard=0
    while nxt!=start and guard<20000:
        guard+=1; found=None
        for e in nxt.link_edges:
            if e.is_boundary and e.index not in used: found=e; break
        if not found: break
        used.add(found.index); n+=1; prev=nxt
        nxt=found.verts[0] if found.verts[1]==prev else found.verts[1]
    if n>=6: nloops+=1; sizes.append(n)
print("boundary loops", nloops, sorted(sizes, reverse=True)[:8])
# faces near tip with ny
tip_faces=[f for f in bm.faces if f.calc_center_median().y>tip_y-0.4]
print("tip faces", len(tip_faces), "avg_ny", sum(f.normal.y for f in tip_faces)/max(len(tip_faces),1))
bm.free()
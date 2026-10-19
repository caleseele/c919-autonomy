# -*- coding: utf-8 -*-
import bpy, bmesh, math, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
bm = bmesh.new(); bm.from_mesh(cut.data); bm.transform(cut.matrix_world); bm.normal_update()
tip_y = max(v.co.y for v in bm.verts)
print("tip_y", tip_y, "faces", len(bm.faces), "boundary", sum(1 for e in bm.edges if e.is_boundary))
# boundary loops near tip
used=set(); loops=[]
for e0 in bm.edges:
    if not e0.is_boundary or e0.index in used: continue
    verts=[]; start=e0.verts[0]; prev=start; nxt=e0.verts[1]; used.add(e0.index); verts.append(start.co.copy())
    guard=0
    while nxt!=start and guard<20000:
        guard+=1; verts.append(nxt.co.copy())
        found=None
        for e in nxt.link_edges:
            if e.is_boundary and e.index not in used:
                found=e; break
        if not found: break
        used.add(found.index); prev=nxt; nxt=found.verts[0] if found.verts[1]==prev else found.verts[1]
    if len(verts)<3: continue
    c=sum(verts, Vector())/len(verts)
    loops.append((len(verts), c.y, max(v.y for v in verts), min(math.sqrt(v.x**2+v.z**2) for v in verts), max(math.sqrt(v.x**2+v.z**2) for v in verts)))
print("loops", loops)
# tip ray
bvh=BVHTree.FromBMesh(bm)
for dy in (0.5,1.0,1.5,2.0):
    origin=Vector((0, tip_y+dy, 0)); hit=bvh.ray_cast(origin, Vector((0,-1,0)))
    if hit[0] is None:
        print(f"ray dy={dy} MISS")
    else:
        print(f"ray dy={dy} hit y={hit[0].y:.3f} dist={(hit[0]-origin).length:.3f} r={math.sqrt(hit[0].x**2+hit[0].z**2):.3f}")
# verts near tip
for band in (0.02,0.05,0.1,0.2,0.4):
    vs=[v for v in bm.verts if v.co.y>tip_y-band]
    rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    print(f"band {band}: n={len(vs)} r_mean={sum(rs)/len(rs):.3f} r_max={max(rs):.3f} r_min={min(rs):.3f}")
bm.free()
seal=bpy.data.objects.get("C919_窗框")
glass=bpy.data.objects.get("C919_玻璃")
print("seal", len(seal.data.polygons) if seal else None, "glass", len(glass.data.polygons) if glass else None)
print("glb", os.path.getsize(os.path.join(PROJ,"public","models","c919.glb")))
# -*- coding: utf-8 -*-
import bpy, bmesh, json, os, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from collections import defaultdict

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new(); bm.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
    bm.transform(obj.matrix_world); bm.normal_update(); return bm

cut = bpy.data.objects.get("Nose_开窗")
bm = wbm(cut)
bvh = BVHTree.FromBMesh(bm)

# better hole check: near-side hit only if dist < 0.8
samples = {
    "WS_R": (Vector((0.55, 17.3, 1.35)), True),
    "WS_L": (Vector((-0.55, 17.3, 1.35)), True),
    "SW_R": (Vector((1.65, 16.3, 0.6)), True),
    "SW_L": (Vector((-1.65, 16.3, 0.6)), True),
    "tip": (Vector((0.0, 19.8, 0.0)), False),
    "cheek": (Vector((1.5, 18.5, 0.2)), True),
}
for name,(p,radial_mode) in samples.items():
    if name=="tip":
        origin=p+Vector((0,1.5,0)); direc=Vector((0,-1,0))
    else:
        radial=Vector((p.x,0,p.z)); radial.normalize()
        origin=p+radial*1.2; direc=-radial
    hit=bvh.ray_cast(origin, direc)
    if hit[0] is None:
        print(name, "OPEN (no hit)")
    else:
        dist=(hit[0]-origin).length
        status = "SOLID" if dist < 0.85 else f"OPEN (far hit {dist:.2f})"
        print(name, status, "hit", tuple(round(x,3) for x in hit[0]))

# boundary loops detail
used=set(); loops=[]
for e0 in bm.edges:
    if not e0.is_boundary or e0.index in used: continue
    verts_loop=[]; edges_loop=[]
    start=e0.verts[0]; prev=e0.verts[0]; nxt=e0.verts[1]
    used.add(e0.index); edges_loop.append(e0); verts_loop.append(start.co.copy())
    guard=0
    while nxt != start and guard < 10000:
        guard+=1
        verts_loop.append(nxt.co.copy())
        found=None
        for e in nxt.link_edges:
            if e.is_boundary and e.index not in used:
                found=e; break
        if not found: break
        used.add(found.index); edges_loop.append(found)
        prev=nxt
        nxt = found.verts[0] if found.verts[1]==prev else found.verts[1]
    if len(edges_loop)<3: continue
    c=sum(verts_loop, Vector())/len(verts_loop)
    ys=[v.y for v in verts_loop]; zs=[v.z for v in verts_loop]; xs=[v.x for v in verts_loop]
    loops.append({"n":len(edges_loop),"c":[round(c.x,3),round(c.y,3),round(c.z,3)],
                  "yr":[round(min(ys),3),round(max(ys),3)],
                  "zr":[round(min(zs),3),round(max(zs),3)],
                  "xr":[round(min(xs),3),round(max(xs),3)]})
print("LOOPS", json.dumps(loops, ensure_ascii=False))

# WS structure
for nm in ("WS_L","WS_R","SW_L","SW_R"):
    o=bpy.data.objects.get(nm)
    if not o: print(nm,"missing"); continue
    w=wbm(o)
    be=sum(1 for e in w.edges if e.is_boundary)
    # manifold?
    nonman=sum(1 for e in w.edges if len(e.link_faces)!=2 and len(e.link_faces)!=1)
    print(nm, "faces", len(w.faces), "boundary", be, "nonman_edges", nonman,
          "vol_est", "closed" if be==0 else "open")
    # normals: how many face +n vs -n
    n,c=Vector(),Vector(); a=0
    for f in w.faces:
        ar=f.calc_area(); n+=f.normal*ar; c+=f.calc_center_median()*ar; a+=ar
    n=n.normalized(); c=c/max(a,1e-9)
    dots=[f.normal.dot(n) for f in w.faces]
    print("  avg_n", tuple(round(x,3) for x in n), "dot>0.5", sum(1 for d in dots if d>0.5), "dot<-0.5", sum(1 for d in dots if d<-0.5))
    w.free()

# tip ring analysis
tip_y=max(v.co.y for v in bm.verts)
print("tip_y", tip_y)
for band in (0.05,0.1,0.2,0.3,0.5,0.8):
    ring=[v for v in bm.verts if tip_y-band-0.05 <= v.co.y <= tip_y-band+0.05]
    if not ring: continue
    rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
    print(f"  band dy={band:.2f} n={len(ring)} r_mean={sum(rs)/len(rs):.3f} r_max={max(rs):.3f} y_mean={sum(v.co.y for v in ring)/len(ring):.3f}")

bm.free()

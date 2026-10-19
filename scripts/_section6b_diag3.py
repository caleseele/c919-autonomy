# -*- coding: utf-8 -*-
import json, os, bpy
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
tip = max((bpy.data.objects["Nose"].matrix_world @ v.co).y for v in bpy.data.objects["Nose"].data.vertices)
fuse=bpy.data.objects["Fuselage"]
aft=next(o for o in bpy.data.objects if "蒙皮" in o.name and "尾" in o.name)
glass=next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
seam=next(o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name)

def radial(skin,wco):
    mw=skin.matrix_world; imw=mw.inverted()
    axis=Vector((0,wco.y,0)); r=Vector((wco.x,0,wco.z))
    if r.length<1e-5: r=Vector((1,0,0))
    r.normalize()
    start_l=imw@(axis+r*6); end_l=imw@(axis+r*5)
    d=(end_l-start_l).normalized()
    ok,loc,norm,_=skin.ray_cast(start_l,d,distance=14)
    if not ok: return None
    wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
    if wn.dot(r)<0: wn=-wn
    return (wco-wloc).dot(wn)

def island_stats(ob):
    import bmesh
    mw=ob.matrix_world
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    rem=set(bm.verts); rows=[]
    while rem:
        s=rem.pop(); st=[s]; isl={s}
        while st:
            v=st.pop()
            for e in v.link_edges:
                o=e.other_vert(v)
                if o not in isl: isl.add(o); rem.discard(o); st.append(o)
        idxs=[v.index for v in isl]
        cents=[mw@v.co for v in isl]
        cy=sum(p.y for p in cents)/len(cents)
        cz=sum(p.z for p in cents)/len(cents)
        cx=sum(p.x for p in cents)/len(cents)
        station=tip-cy
        skin=fuse if station<26 else aft
        dists=[radial(skin, mw@ob.data.vertices[i].co) for i in idxs]
        dists=[d for d in dists if d is not None]
        mean=sum(dists)/len(dists) if dists else None
        rows.append({"st":round(station,2),"z":round(cz,3),"x":round(cx,3),"mean":None if mean is None else round(mean,4),"n":len(idxs)})
    bm.free(); return rows

for name,ob in (("glass",glass),("seam",seam)):
    rows=island_stats(ob)
    rows.sort(key=lambda r: -(r["mean"] or 0))
    print(name,"top mean:", rows[:5], flush=True)
    rows2=sorted(rows, key=lambda r: r["st"])
    print(name,"by st first/last:", rows2[0], rows2[-1], flush=True)
    hi=[r for r in rows if r["mean"] and r["mean"]>0.05]
    print(name,"mean>0.05 count", len(hi), hi[:10], flush=True)

# antenna / objects with z>2.2 in st 20-28
print("--- high z in st 20-28 ---", flush=True)
for o in bpy.data.objects:
    if o.type!="MESH": continue
    hits=[]
    for v in o.data.vertices:
        w=o.matrix_world@v.co
        st=tip-w.y
        if 20<=st<=28 and w.z>2.15:
            hits.append(w)
    if hits:
        print(f"  {o.name} n={len(hits)} z=[{min(h.z for h in hits):.3f},{max(h.z for h in hits):.3f}] x=[{min(h.x for h in hits):.3f},{max(h.x for h in hits):.3f}]", flush=True)

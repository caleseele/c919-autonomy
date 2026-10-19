# -*- coding: utf-8 -*-
"""Remeasure sunk by vertex-mean signed dist; write section6b_measure.json"""
import json, os, bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
bpy.ops.wm.open_mainfile(filepath=BLEND)

tip = max((bpy.data.objects["Nose"].matrix_world @ v.co).y for v in bpy.data.objects["Nose"].data.vertices)
fuse = bpy.data.objects["Fuselage"]
aft = next(o for o in bpy.data.objects if "蒙皮" in o.name and "尾" in o.name)
SUNK_EPS = 5e-4
RAY_OUT = 6.0

def radial(skin, wco):
    mw=skin.matrix_world; imw=mw.inverted()
    axis=Vector((0,wco.y,0))
    radial=Vector((wco.x,0,wco.z))
    if radial.length<1e-5: radial=Vector((1,0,0))
    radial.normalize()
    start_l=imw@(axis+radial*RAY_OUT)
    end_l=imw@(axis+radial*RAY_OUT - radial)
    dir_l=(end_l-start_l).normalized()
    ok,loc,norm,_=skin.ray_cast(start_l, dir_l, distance=RAY_OUT*2.2)
    if not ok:
        return None
    wloc=mw@loc
    wn=(mw.to_3x3()@norm).normalized()
    if wn.dot(radial)<0: wn=-wn
    return (wco-wloc).dot(wn)

def islands(ob):
    import bmesh
    mw=ob.matrix_world
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    rem=set(bm.verts); out=[]
    while rem:
        s=rem.pop(); st=[s]; isl={s}
        while st:
            v=st.pop()
            for e in v.link_edges:
                o=e.other_vert(v)
                if o not in isl:
                    isl.add(o); rem.discard(o); st.append(o)
        idxs=[v.index for v in isl]
        cents=[mw@v.co for v in isl]
        c=Vector(tuple(sum(getattr(p,a) for p in cents)/len(cents) for a in 'xyz'))
        out.append((idxs, tip-c.y, c))
    bm.free(); return out

def measure(ob):
    mw=ob.matrix_world
    isls=islands(ob)
    sunk_lt=sunk_ge=0
    lt=ge=0
    means=[]
    for idxs, st, c in isls:
        skin = fuse if st < 26 else aft
        if st < 26: lt+=1
        else: ge+=1
        dists=[]
        for vi in idxs:
            s=radial(skin, mw@ob.data.vertices[vi].co)
            if s is not None: dists.append(s)
        mean = sum(dists)/len(dists) if dists else None
        means.append(mean)
        sunk = mean is not None and mean < SUNK_EPS
        if sunk:
            if st<26: sunk_lt+=1
            else: sunk_ge+=1
    ys=[(mw@v.co).y for v in ob.data.vertices]
    return {
        "name": ob.name, "total": len(isls), "lt26": lt, "ge26": ge,
        "sunk_lt26": sunk_lt, "sunk_ge26": sunk_ge, "sunk_total": sunk_lt+sunk_ge,
        "mean_signed_min": None if not means else round(min(m for m in means if m is not None),5),
        "mean_signed_max": None if not means else round(max(m for m in means if m is not None),5),
        "station_span": [round(tip-max(ys),3), round(tip-min(ys),3)],
    }

glass=next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
seam=next(o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name)
# before was collapsed
before={"glass":{"sunk_total":86,"station_span":[25.984,26.001]},
        "seam":{"sunk_total":8,"station_span":[25.984,26.004]}}
after={"glass":measure(glass),"seam":measure(seam)}
print("GLASS", after["glass"], flush=True)
print("SEAM", after["seam"], flush=True)

# dorsal objects again
rows=[]
y_lo=tip-(24.5+1.5); y_hi=tip-(24.5-1.5)
for o in bpy.data.objects:
    if o.type!="MESH": continue
    vs=[o.matrix_world@v.co for v in o.data.vertices]
    if not vs: continue
    ymin,ymax=min(v.y for v in vs),max(v.y for v in vs)
    zmax=max(v.z for v in vs)
    if ymax<y_lo or ymin>y_hi or zmax<0.3: continue
    rows.append({"物体":o.name,"verts":len(vs),
        "bbox":{"xmin":round(min(v.x for v in vs),3),"xmax":round(max(v.x for v in vs),3),
                "ymin":round(ymin,3),"ymax":round(ymax,3),
                "zmin":round(min(v.z for v in vs),3),"zmax":round(zmax,3)},
        "station_span":[round(tip-ymax,3),round(tip-ymin,3)]})

ant=next((o for o in bpy.data.objects if "尾段" in o.name and "天线" in o.name), None)
ant_info=None
if ant:
    vs=[ant.matrix_world@v.co for v in ant.data.vertices]
    ant_info={"物体":ant.name,"verts":len(vs),
        "bbox":{"xmin":round(min(v.x for v in vs),3),"xmax":round(max(v.x for v in vs),3),
                "ymin":round(min(v.y for v in vs),3),"ymax":round(max(v.y for v in vs),3),
                "zmin":round(min(v.z for v in vs),3),"zmax":round(max(v.z for v in vs),3)},
        "station_span":[round(tip-max(v.y for v in vs),3),round(tip-min(v.y for v in vs),3)],
        "动作":"保留(先前已重导)"}

out={"before":before,"after":after,"dorsal":rows,"antenna":ant_info,
     "GearBayDoors": bool(bpy.data.objects.get("GearBayDoors"))}
json.dump(out, open(os.path.join(LOG,"section6b_measure.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("dorsal", json.dumps(rows, ensure_ascii=False, indent=2), flush=True)
print("antenna", ant_info, flush=True)

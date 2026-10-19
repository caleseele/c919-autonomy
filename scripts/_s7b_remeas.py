import bpy, json, os
from mathutils import Vector

ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
BLEND=os.path.join(ROOT,r"public\models\c919.blend")
LOG=os.path.join(ROOT,r"scripts\_ref_detail_logs")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def mwv(ob):
    return [ob.matrix_world@v.co.copy() for v in ob.data.vertices]

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

fus=bpy.data.objects["Fuselage_REF"]
vs=mwv(fus)
tip=max(v.y for v in vs)
# sample stations tip_dist 8..22 (cylindrical)
best=None
rows=[]
for st in [i*0.5 for i in range(16,45)]:
    y0=tip-st
    band=[v for v in vs if abs(v.y-y0)<0.12]
    if len(band)<20: continue
    # exclude fin: drop high-z thin
    band2=[v for v in band if not (v.z>2.3 and abs(v.x)<0.9)]
    if len(band2)<16: band2=band
    w=max(v.x for v in band2)-min(v.x for v in band2)
    h=max(v.z for v in band2)-min(v.z for v in band2)
    rows.append((st,w,h,len(band2)))
    if best is None or w>best[1]:
        best=(st,w,h,len(band2))
print("max-width station", best)
# also crown height at x~0 (top-bottom) at that station
st,w,h,n=best
y0=tip-st
band=[v for v in vs if abs(v.y-y0)<0.12 and abs(v.x)<0.35 and v.z<2.5]
if band:
    h_crown=max(v.z for v in band)-min(v.z for v in band)
    print("crown h", h_crown, "z", min(v.z for v in band), max(v.z for v in band))
else:
    h_crown=h
# belly-excluded: only verts with z > belly+0.3 relative to side
band=[v for v in vs if abs(v.y-y0)<0.12]
z_side=sorted([v.z for v in band if abs(abs(v.x)-w/2)<0.15])
print("side z sample", z_side[:3], z_side[-3:] if z_side else None)
# use best section w,h
width=best[1]; height=best[2]
print("section W H", width, height)

# wing LE detail at several x bands
for n in ("REF_机翼_左","REF_机翼_右"):
    ob=bpy.data.objects[n]
    wvs=mwv(ob)
    for lo,hi in ((2.0,2.2),(2.2,2.4),(2.4,2.6),(2.0,2.6),(1.5,2.0)):
        sel=[v for v in wvs if lo<=abs(v.x)<=hi]
        if not sel: continue
        bestv=max(sel,key=lambda v:v.y)
        print(n, f"|x|[{lo},{hi}]", "st", round(tip-bestv.y,3), "x", round(bestv.x,3))

# span tips
wl=aabb(bpy.data.objects["REF_机翼_左"]); wr=aabb(bpy.data.objects["REF_机翼_右"])
print("span", wr["xmax"]-wl["xmin"] if wr["xmax"]>wl["xmax"] else max(wr["xmax"],wl["xmax"])-min(wr["xmin"],wl["xmin"]))
print("wing L x", wl["xmin"], wl["xmax"], "R", wr["xmin"], wr["xmax"])

# update json measurements for 宽/高 with section method
p=os.path.join(LOG,"section7b.json")
d=json.load(open(p,encoding="utf-8"))
# replace 机身最大宽/高 entries
new_items=[]
for it in d["measurements"]:
    if it["项目"]=="机身最大宽":
        ours=round(width,3); ref=3.96; df=ours-ref
        it={"项目":"机身最大宽","实测":ours,"参考":ref,"差值":round(df,3),"是否通过":"是" if abs(df)<=0.08 else "否"}
    elif it["项目"]=="机身最大高":
        ours=round(height,3); ref=4.17; df=ours-ref
        it={"项目":"机身最大高","实测":ours,"参考":ref,"差值":round(df,3),"是否通过":"是" if abs(df)<=0.10 else "否"}
    new_items.append(it)
d["measurements"]=new_items
d["extra"]["max_section"]={"st":best[0],"width":width,"height":height,"n":best[3],"crown_h":h_crown}
json.dump(d, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(d, open(os.path.join(ROOT,"logs","section7b.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("updated measurements:")
for it in new_items: print(it)

import bpy
from mathutils import Vector
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")
tip=max((bpy.data.objects["Nose"].matrix_world@v.co).y for v in bpy.data.objects["Nose"].data.vertices)
fuse=bpy.data.objects["Fuselage"]; nose=bpy.data.objects["Nose"]
g=next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
s=next(o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name)

def ray_r(skin,wco):
    mw=skin.matrix_world; imw=mw.inverted()
    axis=Vector((0,wco.y,0)); r=Vector((wco.x,0,wco.z))
    if r.length<1e-5: r=Vector((1,0,0))
    r.normalize()
    start_l=imw@(axis+r*8); end_l=imw@(axis+r*7)
    d=(end_l-start_l).normalized()
    ok,loc,norm,_=skin.ray_cast(start_l,d,distance=20)
    if not ok: return None
    wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
    if wn.dot(r)<0: wn=-wn
    return (wco-wloc).dot(wn), Vector((wco.x,0,wco.z)).length, Vector((wloc.x,0,wloc.z)).length

# sample glass verts at stations ~6,10,14,18,22
import random
samples={6:[],10:[],14:[],18:[],22:[],26:[]}
for v in g.data.vertices:
    w=g.matrix_world@v.co
    st=tip-w.y
    for key in list(samples):
        if abs(st-key)<0.4 and abs(w.x)>1.5:
            skin = nose if st<5.72 else fuse
            if st>=26: continue
            h=ray_r(skin,w)
            if h: samples[key].append(h)
            break
for k,vals in samples.items():
    if not vals: print(f"st~{k}: no samples", flush=True); continue
    signs=[v[0] for v in vals]
    print(f"st~{k}: n={len(vals)} signed[{min(signs):.4f},{max(signs):.4f}] mean={sum(signs)/len(signs):.4f}", flush=True)

# all mesh max z by station bins 18-26
print("--- max z by object in st bins ---", flush=True)
for o in bpy.data.objects:
    if o.type!="MESH": continue
    bins={}
    for v in o.data.vertices:
        w=o.matrix_world@v.co
        st=tip-w.y
        if 18<=st<=27 and w.z>1.5:
            b=int(st)
            bins[b]=max(bins.get(b, -99), w.z)
    if bins:
        print(f"  {o.name}: { {k:round(v,3) for k,v in sorted(bins.items())} }", flush=True)

# door seam signed at forward
print("--- forward seam verts signed ---", flush=True)
for v in s.data.vertices:
    w=s.matrix_world@v.co
    st=tip-w.y
    if 4.5<=st<=6.0 and abs(w.x)>1.2:
        skin=nose if st<5.72 else fuse
        h=ray_r(skin,w)
        if h:
            print(f"  seam st={st:.2f} signed={h[0]:.4f} r={h[1]:.3f}/{h[2]:.3f}", flush=True)
            break

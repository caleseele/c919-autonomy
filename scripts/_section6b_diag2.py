# -*- coding: utf-8 -*-
import json, os, bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

tip = max((bpy.data.objects["Nose"].matrix_world @ v.co).y for v in bpy.data.objects["Nose"].data.vertices)
fuse = bpy.data.objects["Fuselage"]
glass = next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
aft = next(o for o in bpy.data.objects if "蒙皮" in o.name and "尾" in o.name)

def islands(ob):
    mw = ob.matrix_world
    import bmesh
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    rem = set(bm.verts); out=[]
    while rem:
        s=rem.pop(); st=[s]; isl={s}
        while st:
            v=st.pop()
            for e in v.link_edges:
                o=e.other_vert(v)
                if o not in isl:
                    isl.add(o); rem.discard(o); st.append(o)
        cents=[mw@v.co for v in isl]
        c=Vector((sum(p.x for p in cents)/len(cents), sum(p.y for p in cents)/len(cents), sum(p.z for p in cents)/len(cents)))
        out.append((c, tip-c.y, [v.index for v in isl], len(isl)))
    bm.free(); return out

def radial_hit(skin, wco):
    mw=skin.matrix_world; imw=mw.inverted()
    axis=Vector((0,wco.y,0))
    radial=Vector((wco.x,0,wco.z))
    if radial.length<1e-5: radial=Vector((1,0,0))
    radial.normalize()
    start_w=axis+radial*6.0
    start_l=imw@start_w
    end_l=imw@(start_w-radial)
    dir_l=(end_l-start_l).normalized()
    ok,loc,norm,face=skin.ray_cast(start_l, dir_l, distance=14.0)
    if not ok:
        return None
    wloc=mw@loc
    wn=(mw.to_3x3()@norm).normalized()
    if wn.dot(radial)<0: wn=-wn
    signed=(wco-wloc).dot(wn)
    return dict(ok=True, signed=signed, wloc=tuple(wloc), radial_len=(wco-axis).length, surf_r=(wloc-axis).length, ny=wn.y)

isls=islands(glass)
# sample first 5 <26 and 3 >=26
samples=[]
for c,st,idxs,nv in isls:
    skin = fuse if st<26 else aft
    h=radial_hit(skin,c)
    samples.append({"st":round(st,2),"nv":nv,"c":[round(c.x,3),round(c.y,3),round(c.z,3)],
                    "hit":None if not h else {k:(round(v,4) if isinstance(v,float) else v) for k,v in h.items()}})

# print summary of signed
signeds=[]
miss=0
for c,st,idxs,nv in isls:
    skin=fuse if st<26 else aft
    h=radial_hit(skin,c)
    if not h: miss+=1; continue
    signeds.append(h["signed"])
print(f"islands={len(isls)} miss_ray={miss}", flush=True)
if signeds:
    print(f"signed min/med/max={min(signeds):.4f}/{sorted(signeds)[len(signeds)//2]:.4f}/{max(signeds):.4f}", flush=True)
    print(f"sunk(<0.0005)={sum(1 for s in signeds if s<0.0005)} outside(>0.0005)={sum(1 for s in signeds if s>=0.0005)}", flush=True)
print("samples:", json.dumps(samples[:8], ensure_ascii=False, indent=2), flush=True)

# compare one window vertex |x| vs fuselage ray
c,st,idxs,nv=isls[10]
skin=fuse if st<26 else aft
# take a vert
vco=glass.matrix_world@glass.data.vertices[idxs[0]].co
h=radial_hit(skin,vco)
print(f"vert0 st={st:.2f} co={[round(x,3) for x in vco]} hit={h}", flush=True)

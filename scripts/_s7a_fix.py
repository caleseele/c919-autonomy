import bpy, json, math, os
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
OUT = os.path.join(ROOT, "public", "models")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
BLEND = os.path.join(OUT, "c919.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

print("MESHES:")
for o in sorted(bpy.data.objects, key=lambda x:x.name):
    if o.type=="MESH":
        a=aabb(o)
        print(f"  {o.name} v={len(o.data.vertices)} y=[{a['ymin']:.3f},{a['ymax']:.3f}] z=[{a['zmin']:.3f},{a['zmax']:.3f}]")

g=bpy.data.objects.get("REF_风挡玻璃")
if g:
    g.name="CockpitGlass_REF"
    print("renamed glass")

d1=bpy.data.objects.get("CockpitDarkPlane.001")
d0=bpy.data.objects.get("CockpitDarkPlane")
glass=bpy.data.objects.get("CockpitGlass_REF")
if d1 and d0 and glass:
    gy=0.5*(aabb(glass)["ymin"]+aabb(glass)["ymax"])
    if abs(aabb(d1)["ymin"]-gy) < abs(aabb(d0)["ymin"]-gy):
        bpy.data.objects.remove(d0, do_unlink=True); d1.name="CockpitDarkPlane"
        print("kept .001")
    else:
        bpy.data.objects.remove(d1, do_unlink=True)
        print("removed .001")
elif d1 and not d0:
    d1.name="CockpitDarkPlane"

fus=bpy.data.objects["Fuselage_REF"]
tip=max(v.y for v in mwv(fus))
print(f"tip={tip:.4f}")
print("fuse", aabb(fus))
rad=bpy.data.objects.get("RadomePanelLines")
print("radome", aabb(rad) if rad else None)
dark=bpy.data.objects.get("CockpitDarkPlane")
print("dark", aabb(dark) if dark else None)
print("glass", aabb(glass) if glass else None)

vs=mwv(fus)
fin=[v for v in vs if v.z>2.0 and abs(v.x)<0.6 and (tip-v.y)>28.0]
print("fin", len(fin))
vt_le=None
if fin:
    zmin_f=min(v.z for v in fin)
    root=[v for v in fin if v.z < zmin_f+1.5]
    vt_le=tip-max(v.y for v in root)
    print(f"VT LE={vt_le:.3f} zmin={zmin_f:.3f}")
else:
    fin2=[v for v in vs if v.z>3.0 and abs(v.x)<0.5]
    print("fin2", len(fin2))
    if fin2:
        zmin_f=min(v.z for v in fin2)
        root=[v for v in fin2 if v.z < zmin_f+2.0]
        vt_le=tip-max(v.y for v in root)
        print("VT LE alt", vt_le)

# station of max Z (fin tip area)
mz=max(vs, key=lambda v:v.z)
print("maxZ point", mz, "st", tip-mz.y)

for n in ("REF_发动机_左","REF_发动机_右"):
    ob=bpy.data.objects.get(n)
    if ob:
        a=aabb(ob)
        print(n, "lip_st", round(tip-a["ymax"],3), "aft_st", round(tip-a["ymin"],3))

for n in ("REF_机翼_左","REF_机翼_右"):
    ob=bpy.data.objects.get(n)
    vs=mwv(ob)
    for thr in (1.0,1.5,2.0,2.5,3.0):
        root=[v for v in vs if abs(v.x)<thr]
        if root:
            print(n, f"|x|<{thr}", round(tip-max(v.y for v in root),3))

json.dump({"tip":tip,"vt_le":vt_le}, open(os.path.join(LOG,"section7a_fix.json"),"w",encoding="utf-8"), indent=2)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("saved")

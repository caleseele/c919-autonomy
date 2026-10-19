import bpy, json, math
from mathutils import Vector, kdtree, Matrix
from bpy_extras.object_utils import world_to_camera_view

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = ROOT + r"\public\models\c919.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

SX,SY,SZ = 1.0475227637527205, 1.0, 1.0104343689231436
DX,DY,DZ = 0.0, 15.463823181152343, -4.239782612001511

def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    return {k:f(getattr(p,a) for p in pts) for k,a,f in [
        ("xmin","x",min),("xmax","x",max),("ymin","y",min),("ymax","y",max),("zmin","z",min),("zmax","z",max)]}

nose = bpy.data.objects.get("REF_机头蒙皮") or bpy.data.objects.get("Nose")
mid = bpy.data.objects["REF_中机身蒙皮"]
aft = bpy.data.objects["REF_尾段蒙皮_含垂尾"]
print("names", nose.name, mid.name, aft.name)
print("nose aabb", aabb(nose))
print("mid aabb", aabb(mid))
print("aft aabb", aabb(aft))

front_y = 14.963823318481445
aft_y = -5.427177429199219

def ring(ob, y, tol=0.06, rmin=1.5, rmax=2.4):
    out=[]
    for v in mwv(ob):
        if abs(v.y - y) > tol: continue
        r = (v.x*v.x + v.z*v.z)**0.5
        if rmin <= r <= rmax:
            out.append(v)
    return out

def hd(a,b):
    if len(a)<3 or len(b)<3: return None, len(a), len(b)
    kd=kdtree.KDTree(len(b))
    for i,p in enumerate(b): kd.insert(p,i)
    kd.balance()
    d1=[kd.find(p)[2] for p in a]
    kd2=kdtree.KDTree(len(a))
    for i,p in enumerate(a): kd2.insert(p,i)
    kd2.balance()
    d2=[kd2.find(p)[2] for p in b]
    return max(max(d1),max(d2)), len(a), len(b)

for label,y,oa,ob in [("front",front_y,nose,mid),("aft",aft_y,mid,aft)]:
    for rmin,rmax in [(1.5,2.4),(1.7,2.2),(0.0,5.0)]:
        a=ring(oa,y,0.08,rmin,rmax); b=ring(ob,y,0.08,rmin,rmax)
        mx,na,nb=hd(a,b)
        print(f"{label} r=[{rmin},{rmax}] n={na}/{nb} max_mm={None if mx is None else mx*1000:.3f}")

# What scale does nose imply vs T_REF at front cut?
nb=ring(nose, front_y, 0.1, 0.0, 5.0)
mb=ring(mid, front_y, 0.1, 0.0, 5.0)
if nb and mb:
    nh=max(abs(v.x) for v in nb); mh=max(abs(v.x) for v in mb)
    nz0,nz1=min(v.z for v in nb), max(v.z for v in nb)
    mz0,mz1=min(v.z for v in mb), max(v.z for v in mb)
    print(f"front halfw nose={nh:.4f} mid={mh:.4f} d={abs(nh-mh)*1000:.2f}mm")
    print(f"front z nose=[{nz0:.4f},{nz1:.4f}] mid=[{mz0:.4f},{mz1:.4f}]")
    print(f"front y nose span={[min(v.y for v in nb), max(v.y for v in nb)]} mid={[min(v.y for v in mb), max(v.y for v in mb)]}")

# aft shell
ab=ring(aft, aft_y, 0.1, 1.5, 2.4)
mb2=ring(mid, aft_y, 0.1, 1.5, 2.4)
if ab and mb2:
    print(f"aft halfw aft={max(abs(v.x) for v in ab):.4f} mid={max(abs(v.x) for v in mb2):.4f}")
    print(f"aft z aft=[{min(v.z for v in ab):.4f},{max(v.z for v in ab):.4f}] mid=[{min(v.z for v in mb2):.4f},{max(v.z for v in mb2):.4f}]")

out=r"C:\Users\希儿\Projects\c919-autonomy\scripts\_ref_detail_logs\section7_diag.json"
json.dump({"nose":aabb(nose),"mid":aabb(mid),"aft":aabb(aft)}, open(out,"w",encoding="utf-8"), indent=2)
print("wrote", out)

import bpy, json, math
from mathutils import Vector, kdtree
ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")

def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

nose=bpy.data.objects.get("REF_机头蒙皮") or bpy.data.objects.get("Nose")
mid=bpy.data.objects["REF_中机身蒙皮"]
aft=bpy.data.objects["REF_尾段蒙皮_含垂尾"]
front_y=14.963823318481445
aft_y=-5.427177429199219

def band(ob,y,tol=0.08):
    return [v for v in mwv(ob) if abs(v.y-y)<=tol]

def shell(vs, rmin=1.6, rmax=2.25):
    return [v for v in vs if rmin <= (v.x*v.x+v.z*v.z)**0.5 <= rmax]

def hausdorff(a,b):
    kd=kdtree.KDTree(len(b))
    for i,p in enumerate(b): kd.insert(p,i)
    kd.balance()
    d1=max(kd.find(p)[2] for p in a)
    pair1=max(((kd.find(p)[2], p, kd.find(p)[0]) for p in a), key=lambda t:t[0])
    kd2=kdtree.KDTree(len(a))
    for i,p in enumerate(a): kd2.insert(p,i)
    kd2.balance()
    d2=max(kd2.find(p)[2] for p in b)
    pair2=max(((kd2.find(p)[2], p, kd2.find(p)[0]) for p in b), key=lambda t:t[0])
    return max(d1,d2), pair1, pair2

info={}
for label,y,oa,ob in [("front",front_y,nose,mid),("aft",aft_y,mid,aft)]:
    A=band(oa,y); B=band(ob,y)
    As=shell(A); Bs=shell(B)
    mx,p1,p2=hausdorff(A,B)
    mxs,ps1,ps2=hausdorff(As,Bs) if len(As)>=3 and len(Bs)>=3 else (None,None,None)
    info[label]={
        "y":y,
        "n":[len(A),len(B)],
        "n_shell":[len(As),len(Bs)],
        "max_mm":mx*1000,
        "max_shell_mm": None if mxs is None else mxs*1000,
        "pair_all":{"d_mm":p1[0]*1000,"a":[p1[1].x,p1[1].y,p1[1].z],"b":[p1[2].x,p1[2].y,p1[2].z]},
        "oa_y":[min(v.y for v in mwv(oa)), max(v.y for v in mwv(oa))],
        "ob_y":[min(v.y for v in mwv(ob)), max(v.y for v in mwv(ob))],
    }
    if mxs is not None:
        info[label]["pair_shell"]={"d_mm":ps1[0]*1000,"a":[ps1[1].x,ps1[1].y,ps1[1].z],"b":[ps1[2].x,ps1[2].y,ps1[2].z]}

# axial gap nose→mid
info["axial_gap_nose_mid_mm"]=(aabb(mid)["ymax"] - aabb(nose)["ymin"])*1000
info["axial_gap_mid_aft_mm"]=(aabb(aft)["ymax"] - aabb(mid)["ymin"])*1000  # should be ~0; mid ymin vs aft ymax
# actually mid and aft both end at -5.427; overlap check
info["mid_aft_ymax_diff_mm"]=(aabb(mid)["ymin"] - aabb(aft)["ymax"])*1000

visible=sorted(o.name for o in bpy.data.objects if o.type=="MESH" and not o.hide_get())
info["visible"]=visible
info["aabbs"]={n:aabb(bpy.data.objects[n]) for n in ("REF_机头蒙皮","REF_中机身蒙皮","REF_尾段蒙皮_含垂尾") if bpy.data.objects.get(n)}

# load prior result and merge
p=ROOT+r"\scripts\_ref_detail_logs\section7.json"
res=json.load(open(p,encoding="utf-8"))
res["diag"]=info
json.dump(res, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(res, open(ROOT+r"\logs\section7.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(info, ensure_ascii=False, indent=2))

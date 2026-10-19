import bpy, json
from mathutils import Vector, kdtree
ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")

def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]

nose=bpy.data.objects["REF_机头蒙皮"]
mid=bpy.data.objects["REF_中机身蒙皮"]
aft=bpy.data.objects["REF_尾段蒙皮_含垂尾"]
front_y=14.963823318481445
aft_y=-5.427177429199219

def band(ob,y,tol):
    return [v for v in mwv(ob) if abs(v.y-y)<=tol]

def hausdorff(a,b):
    if len(a)<3 or len(b)<3: return None, len(a), len(b)
    kd=kdtree.KDTree(len(b))
    for i,p in enumerate(b): kd.insert(p,i)
    kd.balance()
    d1=max(kd.find(p)[2] for p in a)
    kd2=kdtree.KDTree(len(a))
    for i,p in enumerate(a): kd2.insert(p,i)
    kd2.balance()
    d2=max(kd2.find(p)[2] for p in b)
    return max(d1,d2)*1000, len(a), len(b)

rows=[]
for tol in (0.002, 0.005, 0.01, 0.015, 0.03, 0.05, 0.08):
    for label,y,oa,ob in [("front",front_y,nose,mid),("aft",aft_y,mid,aft)]:
        mx,na,nb=hausdorff(band(oa,y,tol), band(ob,y,tol))
        rows.append({"tol_mm":tol*1000,"cut":label,"max_mm":mx,"na":na,"nb":nb})
        print(f"tol={tol*1000:5.1f}mm {label:5s} n={na}/{nb} max_mm={mx}")

# Also: distance between nose aft ring (ymin cluster) and mid front ring (ymax cluster)
def end_ring(ob, which, depth=0.02):
    vs=mwv(ob)
    if which=="min":
        y0=min(v.y for v in vs)
        return [v for v in vs if v.y <= y0+depth]
    else:
        y0=max(v.y for v in vs)
        return [v for v in vs if v.y >= y0-depth]

for d in (0.01, 0.02, 0.05):
    A=end_ring(nose,"min",d); B=end_ring(mid,"max",d)
    mx,na,nb=hausdorff(A,B)
    print(f"endring depth={d*1000:.0f}mm nose_aft↔mid_front n={na}/{nb} max_mm={mx}")
    # axial gap between mean Y
    ya=sum(v.y for v in A)/len(A); yb=sum(v.y for v in B)/len(B)
    print(f"  meanY nose={ya:.4f} mid={yb:.4f} gap_mm={(yb-ya)*1000:.2f}")

A=end_ring(mid,"min",0.02); B=end_ring(aft,"max",0.02)
mx,na,nb=hausdorff(A,B)
print(f"endring mid_aft↔aft_front n={na}/{nb} max_mm={mx}")
ya=sum(v.y for v in A)/len(A); yb=sum(v.y for v in B)/len(B)
print(f"  meanY mid={ya:.4f} aft={yb:.4f} gap_mm={(ya-yb)*1000:.2f}")

json.dump(rows, open(ROOT+r"\scripts\_ref_detail_logs\section7_tol_sweep.json","w",encoding="utf-8"), indent=2)

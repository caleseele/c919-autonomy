import bpy, json, math, os
from mathutils import Matrix, Vector

ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
REFS=os.path.join(ROOT,"refs")
BLEND=os.path.join(ROOT,r"public\models\c919.blend")
# use bak-before-s8 for clean state with old engines
BAK=os.path.join(ROOT,r"public\models\c919.bak-before-s8.blend")
bpy.ops.wm.open_mainfile(filepath=BAK)

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

oldL=bpy.data.objects["REF_发动机_左"]; oldR=bpy.data.objects["REF_发动机_右"]
print("OLD L", aabb(oldL))
print("OLD R", aabb(oldR))

SX,SY,SZ=1.0475227637527205,1.0,1.0104343689231436
DX,DY,DZ=0.0,15.463823181152343,-4.239782612001511
INV_SX,INV_SZ=1/SX,1/SZ
Z0=-4.239783763885498

def T_REF():
    R=Matrix.Rotation(math.pi,4,"Z")
    S=Matrix.Diagonal((SX,SY,SZ,1.0))
    T=Matrix.Translation(Vector((DX,DY,DZ)))
    return T@S@R

def Unscale():
    T1=Matrix.Translation(Vector((0,0,-Z0)))
    S=Matrix.Diagonal((INV_SX,1.0,INV_SZ,1.0))
    T2=Matrix.Translation(Vector((0,0,Z0)))
    return T2@S@T1

def find_parts():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "分件" in fn: return os.path.join(REFS,fn)
    raise SystemExit("no parts")

def find_whole():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "发动机" in fn and "分件" not in fn:
            return os.path.join(REFS,fn)
    raise SystemExit("no whole")

# Import parts RAW (no xform)
before=set(bpy.data.objects)
bpy.ops.wm.obj_import(filepath=find_parts())
raw=[o for o in bpy.data.objects if o not in before and o.type=="MESH"]
print("RAW parts sample:")
for o in sorted(raw, key=lambda x:x.name)[:4]:
    print(" ", o.name, aabb(o))
# combined raw L
Lraw=[o for o in raw if "_左_" in o.name]
Rraw=[o for o in raw if "_右_" in o.name]
def comb(obs):
    bs=[aabb(o) for o in obs]
    return {k:f(b[k] for b in bs) for k,f in [("xmin",min),("xmax",max),("ymin",min),("ymax",max),("zmin",min),("zmax",max)]}
print("RAW L comb", comb(Lraw))
print("RAW R comb", comb(Rraw))

# Import whole engine RAW for comparison
before2=set(bpy.data.objects)
bpy.ops.wm.obj_import(filepath=find_whole())
whole=[o for o in bpy.data.objects if o not in before2 and o.type=="MESH"]
print("RAW whole:")
for o in whole:
    print(" ", o.name, aabb(o))

# Apply T_REF only to a copy of raw L comb - transform verts of one nacelle
# Compare whole raw vs parts raw - should be similar if same coords
print("--- after T_REF on parts ---")
M=T_REF()
for o in raw:
    o.data.transform(o.matrix_world); o.matrix_world=Matrix.Identity(4)
    o.data.transform(M); o.data.update()
print("T_REF L", comb(Lraw))
print("T_REF R", comb(Rraw))

print("--- after T_REF+unscale on parts ---")
U=Unscale()
for o in raw:
    o.data.transform(U); o.data.update()
print("FULL L", comb(Lraw))
print("FULL R", comb(Rraw))

# Also transform whole engines the same way
print("--- whole engines same chain ---")
for o in whole:
    o.data.transform(o.matrix_world); o.matrix_world=Matrix.Identity(4)
    o.data.transform(M); o.data.update()
    o.data.transform(U); o.data.update()
    print(o.name, aabb(o))

# Don't save
json.dump({"oldL":aabb(oldL),"newL":comb(Lraw),"oldR":aabb(oldR),"newR":comb(Rraw),
           "whole":{o.name:aabb(o) for o in whole}},
          open(os.path.join(ROOT,r"scripts\_ref_detail_logs\section8_diag.json"),"w",encoding="utf-8"), indent=2)
print("wrote diag")

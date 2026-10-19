import bpy, os
from mathutils import Vector
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))

def bb(o):
    pts=[o.matrix_world@Vector(c) for c in o.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)

for n in ["Nose","CockpitGlass_REF","REF_WindshieldFrame","REF_Wipers","REF_ProbesAntennas","REF_CockpitInterior","CockpitDarkPlane"]:
    o=bpy.data.objects.get(n)
    if not o:
        print("MISSING", n); continue
    xmin,xmax,ymin,ymax,zmin,zmax=bb(o)
    print("%s x=%.2f..%.2f y=%.2f..%.2f z=%.2f..%.2f"%(n,xmin,xmax,ymin,ymax,zmin,zmax))
still=[n for n in ["CockpitPillar_Center","CockpitSeals","Wiper_L_Arm","CockpitInterior","CockpitGlareShield"] if bpy.data.objects.get(n)]
print("STILL_PRESENT", still)
print("ALL_REF", [o.name for o in bpy.data.objects if o.name.startswith("REF_")])

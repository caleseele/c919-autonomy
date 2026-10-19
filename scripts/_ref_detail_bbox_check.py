import bpy, json
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")

def bb(o):
    pts=[o.matrix_world@Vector(c) for c in o.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

for n in ["Nose","CockpitGlass_REF","REF_WindshieldFrame","REF_Wipers","REF_ProbesAntennas","REF_CockpitInterior","CockpitDarkPlane"]:
    o=bpy.data.objects.get(n)
    if not o:
        print("MISSING", n); continue
    b=bb(o)
    print(f"{n:24s} Y=[{b['ymin']:.2f},{b['ymax']:.2f}] Z=[{b['zmin']:.2f},{b['zmax']:.2f}] X=[{b['xmin']:.2f},{b['xmax']:.2f}]")
print("deleted_check", [n for n in ["CockpitPillar_Center","CockpitSeals","Wiper_L_Arm","CockpitInterior"] if bpy.data.objects.get(n)])

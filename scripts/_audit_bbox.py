import bpy
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
for n in ("PilotSeats","GlareShield","Windshield","Nose","CockpitFrames"):
    o = bpy.data.objects.get(n)
    if not o:
        print("MISSING", n); continue
    bb = [o.matrix_world @ v.co for v in o.bound_box]
    xs=[p.x for p in bb]; ys=[p.y for p in bb]; zs=[p.z for p in bb]
    print(n, "Y", round(min(ys),3), round(max(ys),3), "Z", round(min(zs),3), round(max(zs),3), "hide_r", o.hide_render)

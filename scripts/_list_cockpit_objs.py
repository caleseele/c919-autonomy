import bpy
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
for o in bpy.data.objects:
    if any(k in o.name.lower() for k in ("seat","glare","wind","nose","cockpit","wiper")):
        print("OBJ", o.name, o.type, "hide", o.hide_render)

import bpy, os
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
planes=[o for o in bpy.data.objects if o.name.startswith("CockpitDarkPlane")]
print("planes", [o.name for o in planes])
# keep one
for o in planes[1:]:
    me=o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if me and me.users==0: bpy.data.meshes.remove(me)
    print("removed", o.name)
if len(planes)>1:
    bpy.ops.export_scene.gltf(filepath=os.path.join(ROOT,"public","models","c919.glb"), export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
    print("reexported", os.path.getsize(os.path.join(ROOT,"public","models","c919.glb")))

import bpy, json, os, shutil
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
BLEND=os.path.join(ROOT,r"public\models\c919.blend")
GLB=os.path.join(ROOT,r"public\models\c919.glb")
bpy.ops.wm.open_mainfile(filepath=BLEND)
# canonicalize names
renames={
    "REF_风挡玻璃":"CockpitGlass_REF",
    "CockpitDarkPlane.001":"CockpitDarkPlane",
}
for old,new in renames.items():
    ob=bpy.data.objects.get(old)
    if ob:
        # if target exists, remove target if duplicate
        tgt=bpy.data.objects.get(new)
        if tgt and tgt!=ob:
            bpy.data.objects.remove(tgt, do_unlink=True)
        ob.name=new
        print("obj", old, "->", ob.name)
    me=bpy.data.meshes.get(old)
    if me:
        me.name=new
        print("mesh", old, "->", me.name)

# ensure glass object mesh name
g=bpy.data.objects.get("CockpitGlass_REF")
if g and g.data:
    g.data.name="CockpitGlass_REF"
    print("glass mesh", g.data.name)

visible=sorted(o.name for o in bpy.data.objects if o.type=="MESH" and not o.hide_get())
print("VISIBLE", visible)

bpy.ops.object.select_all(action="DESELECT")
n=0
for o in bpy.data.objects:
    if o.type=="MESH" and not o.hide_get() and not o.hide_render:
        o.select_set(True); n+=1
bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
shutil.copy2(BLEND, os.path.join(ROOT,r"public\models\c919.bak-section7.blend"))
# patch json visible
for p in (os.path.join(ROOT,r"scripts\_ref_detail_logs\section7a.json"),
          os.path.join(ROOT,r"logs\section7a.json")):
    if os.path.isfile(p):
        d=json.load(open(p,encoding="utf-8"))
        d["visible_meshes"]=visible
        d["glb_mesh_count"]=n
        json.dump(d, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("done n", n)

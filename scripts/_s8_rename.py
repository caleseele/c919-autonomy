import bpy, json, os, shutil
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
BLEND=os.path.join(ROOT,r"public\models\c919.blend")
GLB=os.path.join(ROOT,r"public\models\c919.glb")
LOG=os.path.join(ROOT,r"scripts\_ref_detail_logs")
bpy.ops.wm.open_mainfile(filepath=BLEND)

# Strip .001 from left engine parts if no conflict
for o in list(bpy.data.objects):
    if o.type!="MESH": continue
    if ".001" in o.name and o.name.startswith("REF_发动机_"):
        base=o.name.replace(".001","")
        if bpy.data.objects.get(base) is None:
            o.name=base
            if o.data and o.data.name.endswith(".001"):
                o.data.name=base
            print("renamed", base)

visible=sorted(o.name for o in bpy.data.objects if o.type=="MESH" and not o.hide_get())
print("VISIBLE", len(visible))
for n in visible:
    if "发动机" in n: print(" ", n)

bpy.ops.object.select_all(action="DESELECT")
n=0
for o in bpy.data.objects:
    if o.type=="MESH" and not o.hide_get() and not o.hide_render:
        o.select_set(True); n+=1
bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
shutil.copy2(BLEND, os.path.join(ROOT,r"public\models\c919.bak-section8.blend"))

p=os.path.join(LOG,"section8.json")
d=json.load(open(p,encoding="utf-8"))
d["visible_meshes"]=visible
d["glb_mesh_count"]=n
d["note_8_3"]="CockpitDarkPlane deleted (cockpit bulkhead/dark slab; z above belly so not in strict belly band, explicit delete per SPEC)"
json.dump(d, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(d, open(os.path.join(ROOT,"logs","section8.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("glb", n, "done")

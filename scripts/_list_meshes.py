import bpy
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type=="MESH" and ("起落架" in o.name or "Gear" in o.name or "gear" in o.name or "舱门" in o.name):
        print("OBJ", o.name)
print("---ALL COUNT", sum(1 for o in bpy.data.objects if o.type=="MESH" and not o.hide_get()))
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type=="MESH" and not o.hide_get():
        print(o.name)

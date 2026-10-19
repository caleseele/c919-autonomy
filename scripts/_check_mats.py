# -*- coding: utf-8 -*-
import bpy
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")
for n in ("REF_前起落架_舱门","REF_主起落架_舱门","REF_前起落架_支柱轮","REF_主起落架_支柱轮"):
    o=bpy.data.objects.get(n)
    if not o:
        print("MISSING", n); continue
    mats=[m.name for m in o.data.materials]
    print("OBJ", n, mats)
    for m in o.data.materials:
        if m and m.node_tree:
            bsdf=m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                c=list(bsdf.inputs["Base Color"].default_value)
                print("  base", c, "m", bsdf.inputs["Metallic"].default_value, "r", bsdf.inputs["Roughness"].default_value)

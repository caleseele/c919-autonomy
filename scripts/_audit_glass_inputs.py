import bpy
mat = bpy.data.materials.get("CockpitGlass")
print("MAT", mat)
if mat and mat.use_nodes:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    print("BSDF", bsdf)
    if bsdf:
        for inp in bsdf.inputs:
            if any(k in inp.name.lower() for k in ("alpha", "trans", "rough", "base")):
                try:
                    print("IN", inp.name, "=", inp.default_value)
                except Exception as e:
                    print("IN", inp.name, "ERR", e)

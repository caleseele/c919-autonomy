import bpy, json
from mathutils import Matrix, Vector
ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")

def mat_info(ob):
    rows=[]
    if not ob or ob.type!="MESH": return rows
    for i,m in enumerate(ob.data.materials):
        if not m: continue
        info={"slot":i,"name":m.name,"blend":getattr(m,"blend_method",None)}
        if m.use_nodes:
            bsdf=m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                def g(k):
                    if k in bsdf.inputs:
                        v=bsdf.inputs[k].default_value
                        try: return list(v)
                        except TypeError: return float(v)
                    return None
                info["base"]=g("Base Color")
                info["metallic"]=g("Metallic")
                info["roughness"]=g("Roughness")
                info["alpha"]=g("Alpha")
                info["ior"]=g("IOR")
                for tk in ("Transmission Weight","Transmission"):
                    if tk in bsdf.inputs:
                        info["transmission"]=g(tk); info["transmission_key"]=tk; break
        rows.append(info)
    return rows

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

names=[
    "REF_机头蒙皮","Nose","CockpitGlass_REF","REF_风挡玻璃",
    "REF_风挡窗框","REF_WindshieldFrame","REF_雨刮器","REF_Wipers",
    "REF_探头天线","REF_ProbesAntennas","REF_驾驶舱内饰","REF_CockpitInterior",
    "RadomePanelLines","CockpitDarkPlane",
]
out={"objects":{},"all_mesh":[]}
for o in bpy.data.objects:
    if o.type=="MESH":
        out["all_mesh"].append(o.name)
for n in names:
    o=bpy.data.objects.get(n)
    if not o: continue
    out["objects"][n]={
        "exists":True,
        "mw":[list(r) for r in o.matrix_world],
        "aabb":aabb(o),
        "mats":mat_info(o),
        "verts":len(o.data.vertices) if o.type=="MESH" else 0,
    }
print(json.dumps(out,ensure_ascii=False,indent=2))
open(ROOT+r"\scripts\_ref_detail_logs\section7a_pre.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))

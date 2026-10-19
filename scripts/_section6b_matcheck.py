import bpy, json
from mathutils import Vector
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")
g=next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
s=next(o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name)
for ob in (g,s):
    mats=[m.name for m in ob.data.materials]
    print(ob.name, "mats", mats, "hide_render", ob.hide_render, "hide_get", ob.hide_get(), flush=True)
    if ob.data.materials:
        m=ob.data.materials[0]
        bsdf=m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
        if bsdf:
            print("  alpha", bsdf.inputs["Alpha"].default_value if "Alpha" in bsdf.inputs else None,
                  "blend", getattr(m,"blend_method",None), flush=True)
# count islands with |x|>1.5 (true side windows) vs |x|<1.0
tip=max((bpy.data.objects["Nose"].matrix_world@v.co).y for v in bpy.data.objects["Nose"].data.vertices)
import bmesh
mw=g.matrix_world
bm=bmesh.new(); bm.from_mesh(g.data); bm.verts.ensure_lookup_table()
rem=set(bm.verts); side=0; mid=0
while rem:
    seed=rem.pop(); st=[seed]; isl={seed}
    while st:
        v=st.pop()
        for e in v.link_edges:
            o=e.other_vert(v)
            if o not in isl: isl.add(o); rem.discard(o); st.append(o)
    c=sum((mw@v.co for v in isl), Vector())/len(isl)
    if abs(c.x)>1.5: side+=1
    else: mid+=1
bm.free()
print(f"glass side(|x|>1.5)={side} mid(|x|<=1.5)={mid}", flush=True)
# seam stations
mw=s.matrix_world
bm=bmesh.new(); bm.from_mesh(s.data); bm.verts.ensure_lookup_table()
rem=set(bm.verts)
print("seam islands:", flush=True)
while rem:
    seed=rem.pop(); st=[seed]; isl={seed}
    while st:
        v=st.pop()
        for e in v.link_edges:
            o=e.other_vert(v)
            if o not in isl: isl.add(o); rem.discard(o); st.append(o)
    c=sum((mw@v.co for v in isl), Vector())/len(isl)
    print(f"  st={tip-c.y:.2f} x={c.x:.2f} z={c.z:.2f} n={len(isl)}", flush=True)
bm.free()

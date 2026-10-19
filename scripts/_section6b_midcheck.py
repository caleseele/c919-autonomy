import bpy
from mathutils import Vector
import bmesh
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT+r"\public\models\c919.blend")
tip=max((bpy.data.objects["Nose"].matrix_world@v.co).y for v in bpy.data.objects["Nose"].data.vertices)
g=next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
mw=g.matrix_world
bm=bmesh.new(); bm.from_mesh(g.data); bm.verts.ensure_lookup_table()
rem=set(bm.verts)
print("mid glass:", flush=True)
while rem:
    s=rem.pop(); st=[s]; isl={s}
    while st:
        v=st.pop()
        for e in v.link_edges:
            o=e.other_vert(v)
            if o not in isl: isl.add(o); rem.discard(o); st.append(o)
    c=sum((mw@v.co for v in isl), Vector())/len(isl)
    if abs(c.x)<=1.5:
        print(f"  st={tip-c.y:.2f} x={c.x:.3f} z={c.z:.3f} n={len(isl)}", flush=True)
bm.free()
print("high z st20-28:", flush=True)
for o in bpy.data.objects:
    if o.type!="MESH": continue
    hits=[o.matrix_world@v.co for v in o.data.vertices if 20<=(tip-(o.matrix_world@v.co).y)<=28 and (o.matrix_world@v.co).z>2.15]
    if hits:
        print(f"  {o.name} n={len(hits)} zmax={max(h.z for h in hits):.3f}", flush=True)

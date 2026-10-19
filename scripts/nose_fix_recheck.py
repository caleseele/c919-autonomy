import bpy, bmesh, json, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend"))
cut = bpy.data.objects["Nose_开窗"]
bm = bmesh.new(); bm.from_mesh(cut.data); bm.transform(cut.matrix_world)
bvh = BVHTree.FromBMesh(bm)
samples = {
    "WS_R": Vector((0.55, 17.3, 1.35)),
    "WS_L": Vector((-0.55, 17.3, 1.35)),
    "SW_R": Vector((1.65, 16.3, 0.6)),
    "SW_L": Vector((-1.65, 16.3, 0.6)),
    "tip": Vector((0.0, 19.8, 0.0)),
    "cheek": Vector((1.5, 18.5, 0.2)),
}
for name, p in samples.items():
    radial = Vector((p.x, 0, p.z))
    if radial.length < 1e-6:
        radial = Vector((0,0,1))
    else:
        radial.normalize()
    if name == "tip":
        origin, direc = p + Vector((0, 1.5, 0)), Vector((0, -1, 0))
        expect = 1.5
    else:
        origin, direc = p + radial * 1.2, -radial
        expect = 1.2
    hit = bvh.ray_cast(origin, direc)
    if hit[0] is None:
        status = "OPEN"
        dist = None
    else:
        dist = hit[3]
        # near-side skin expected ~expect; far-side hit => near is open
        status = "OPEN" if dist > expect + 0.8 else "SOLID"
    print(name, status, "dist", dist, "expect", expect)
print("faces", len(bm.faces), "boundary", sum(1 for e in bm.edges if e.is_boundary))
ys=[v.co.y for v in bm.verts]; print("y", min(ys), max(ys))
bm.free()
# list visible meshes
for o in bpy.data.objects:
    if o.type=='MESH' and not o.hide_render and not o.hide_get():
        print("VIS", o.name, len(o.data.polygons))

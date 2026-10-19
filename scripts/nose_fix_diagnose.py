# -*- coding: utf-8 -*-
import bpy, bmesh, json, os
from mathutils import Vector
from collections import defaultdict

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919_nose_fix_step3.blend")
OUT = os.path.join(PROJ, "scripts", "_nose_fix_logs", "diagnose_step3.json")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def world_bm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
    bm.transform(obj.matrix_world); bm.normal_update()
    return bm

def walk_loops(edges):
    unused = set(edges)
    loops = []
    while unused:
        start = unused.pop()
        loop = [start]
        changed = True
        while changed:
            changed = False
            verts = set()
            for e in loop:
                verts.update(e.verts)
            for e in list(unused):
                if e.verts[0] in verts or e.verts[1] in verts:
                    unused.remove(e); loop.append(e); changed = True
        loops.append(loop)
    return loops

report = {"objects": []}
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    report["objects"].append({
        "name": o.name,
        "hide": o.hide_get(),
        "hide_render": o.hide_render,
        "verts": len(o.data.vertices),
        "faces": len(o.data.polygons),
    })

body = bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
print("BODY", body.name if body else None)
bm = world_bm(body)
be = [e for e in bm.edges if e.is_boundary]
print("boundary_edges", len(be))
loops = walk_loops(be)
print("loops", len(loops))
loop_info = []
for i, loop in enumerate(loops):
    mids = [((e.verts[0].co + e.verts[1].co) * 0.5) for e in loop]
    xs=[m.x for m in mids]; ys=[m.y for m in mids]; zs=[m.z for m in mids]
    info = {
        "i": i, "n_edges": len(loop),
        "x": [min(xs), max(xs)], "y": [min(ys), max(ys)], "z": [min(zs), max(zs)],
        "cy": sum(ys)/len(ys), "cx": sum(xs)/len(xs), "cz": sum(zs)/len(zs),
    }
    loop_info.append(info)
    print("LOOP", info)

# Sample points inside expected WS regions — raycast to see if skin still there
bvh_ok = True
try:
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromBMesh(bm)
    samples = [
        ("WS_R", Vector((0.55, 17.3, 1.35))),
        ("WS_L", Vector((-0.55, 17.3, 1.35))),
        ("SW_R", Vector((1.65, 16.3, 0.6))),
        ("SW_L", Vector((-1.65, 16.3, 0.6))),
        ("skin_cheek", Vector((1.5, 18.5, 0.2))),
    ]
    hits = []
    for name, p in samples:
        # cast from outside along -radial
        radial = Vector((p.x, 0, p.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        radial.normalize()
        origin = p + radial * 1.0
        hit = bvh.ray_cast(origin, -radial)
        hits.append({"name": name, "hit": hit[0] is not None, "loc": list(hit[0]) if hit[0] else None, "dist": hit[3] if hit[0] else None})
        print("SAMPLE", name, "hit", hit[0] is not None, hit[3] if hit[0] else None)
    report["samples"] = hits
except Exception as e:
    print("bvh err", e)

report["loops"] = loop_info
report["body"] = body.name
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("wrote", OUT)
bm.free()

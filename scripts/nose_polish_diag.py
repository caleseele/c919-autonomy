# -*- coding: utf-8 -*-
import bpy, bmesh, json, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from collections import defaultdict

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
LOG = os.path.join(PROJ, "scripts", "_nose_fix_logs", "polish_diag.json")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm

info = {"objects": []}
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs=[v.x for v in bb]; ys=[v.y for v in bb]; zs=[v.z for v in bb]
    info["objects"].append({
        "name": o.name,
        "hide": o.hide_get(),
        "hide_render": o.hide_render,
        "faces": len(o.data.polygons),
        "verts": len(o.data.vertices),
        "bbox": [[min(xs),max(xs)],[min(ys),max(ys)],[min(zs),max(zs)]],
    })

cut = bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
glass = bpy.data.objects.get("C919_玻璃")
seal = bpy.data.objects.get("C919_窗框")
info["cut_name"] = cut.name if cut else None
info["glass_faces"] = len(glass.data.polygons) if glass else None
info["seal_faces"] = len(seal.data.polygons) if seal else None

if cut:
    bm = wbm(cut)
    bvh = BVHTree.FromBMesh(bm)
    # boundary loops
    boundary = [e for e in bm.edges if e.is_boundary]
    # walk loops
    used=set(); loops=[]
    for e0 in boundary:
        if e0.index in used: continue
        loop=[e0]; used.add(e0.index)
        cur=e0; start=e0.verts[0]; prev=e0.verts[0]; nxt=e0.verts[1]
        while nxt != start:
            found=None
            for e in nxt.link_edges:
                if e.is_boundary and e.index not in used:
                    found=e; break
            if not found: break
            used.add(found.index); loop.append(found)
            prev=nxt
            nxt = found.verts[0] if found.verts[1]==prev else found.verts[1]
        loops.append(len(loop))
    info["boundary_edges"] = len(boundary)
    info["boundary_loops"] = sorted(loops, reverse=True)
    # hole checks
    samples = {
        "WS_R": Vector((0.55, 17.3, 1.35)),
        "WS_L": Vector((-0.55, 17.3, 1.35)),
        "SW_R": Vector((1.65, 16.3, 0.6)),
        "SW_L": Vector((-1.65, 16.3, 0.6)),
        "tip": Vector((0.0, 19.8, 0.0)),
        "cheek": Vector((1.5, 18.5, 0.2)),
    }
    checks={}
    for name,p in samples.items():
        if name=="tip":
            hit=bvh.ray_cast(p+Vector((0,1.5,0)), Vector((0,-1,0)))
        else:
            radial=Vector((p.x,0,p.z)); radial.normalize()
            hit=bvh.ray_cast(p+radial*1.2, -radial)
        checks[name]="SOLID" if hit[0] else "OPEN"
    info["holes"]=checks
    ys=[v.co.y for v in bm.verts]
    tip_y=max(ys)
    tip_verts=[v for v in bm.verts if v.co.y>tip_y-0.05]
    tip_rs=[(v.co.x**2+v.co.z**2)**0.5 for v in tip_verts]
    info["tip"]={"tip_y":tip_y,"n_tip_verts":len(tip_verts),"max_r":max(tip_rs) if tip_rs else None,"mean_r":sum(tip_rs)/len(tip_rs) if tip_rs else None}
    # faces near tip flatness
    tip_faces=[f for f in bm.faces if f.calc_center_median().y>tip_y-0.15]
    norms=[f.normal.copy() for f in tip_faces]
    if norms:
        avg=sum(norms, Vector())/len(norms)
        info["tip"]["n_faces"]=len(tip_faces)
        info["tip"]["avg_ny"]=avg.y
        info["tip"]["dot_min"]=min(n.dot(avg.normalized()) for n in norms)
    bm.free()

if glass:
    bm=wbm(glass)
    # islands
    seen=set(); islands=[]
    for f in bm.faces:
        if f in seen: continue
        stack=[f]; isl=[]; seen.add(f)
        while stack:
            cur=stack.pop(); isl.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen:
                        seen.add(nb); stack.append(nb)
        islands.append(isl)
    info["glass_islands"]=[{"faces":len(isl),"center":list(sum((f.calc_center_median() for f in isl), Vector())/len(isl))} for isl in islands]
    # boundary per island
    for i,isl in enumerate(islands):
        ec=defaultdict(int)
        for f in isl:
            for e in f.edges: ec[e]+=1
        be=[e for e,c in ec.items() if c==1]
        info["glass_islands"][i]["boundary_edges"]=len(be)
    bm.free()

with open(LOG,"w",encoding="utf-8") as f:
    json.dump(info,f,indent=2,ensure_ascii=False)
print("WROTE", LOG)
print(json.dumps({k:info[k] for k in info if k!="objects"}, indent=2, ensure_ascii=False))
print("MESH_COUNT", len(info["objects"]))
for o in info["objects"]:
    if any(x in o["name"] for x in ("Nose","玻璃","窗框","Cabin","WS_","SW_","Cockpit","Frame")):
        print(o["name"], "faces", o["faces"], "hide", o["hide"], "yr", o["bbox"][1])

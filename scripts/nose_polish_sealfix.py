# -*- coding: utf-8 -*-
"""Rebuild seals+glass on current radome-fixed blend, export."""
from __future__ import annotations
import json, math, os
from collections import defaultdict
import bmesh, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
OUT = os.path.join(PROJ, "public", "models", "nose-fix")
LOG = os.path.join(PROJ, "scripts", "_nose_fix_logs")
NOTES = os.path.join(PROJ, "scripts", "NOSE_POLISH_PASS_NOTES.zh-Hans.md")
SEAL_W, SEAL_INSET, GLASS_INSET = 0.04, 0.002, 0.004

def log(*a):
    print("SEALFIX", *a, flush=True)

def wbm(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new(); bm.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
    bm.transform(obj.matrix_world); bm.normal_update(); return bm

def mkmat(name, col, rough, trans=None, alpha=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs: bsdf.inputs["Base Color"].default_value = (*col, 1)
    if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value = rough
    if trans is not None:
        for k in ("Transmission Weight", "Transmission"):
            if k in bsdf.inputs: bsdf.inputs[k].default_value = trans
        if "IOR" in bsdf.inputs: bsdf.inputs["IOR"].default_value = 1.5
        if alpha is not None and "Alpha" in bsdf.inputs: bsdf.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            if hasattr(mat, attr):
                try: setattr(mat, attr, val)
                except Exception: pass
    return mat

def outer_faces_island(bm):
    seen=set(); islands=[]
    for f in bm.faces:
        if f in seen: continue
        stack=[f]; isl=[]; seen.add(f)
        while stack:
            cur=stack.pop(); isl.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen: seen.add(nb); stack.append(nb)
        islands.append(isl)
    out=[]
    for isl in islands:
        n=Vector(); c=Vector(); a=0.0
        for f in isl:
            ar=f.calc_area(); n+=f.normal*ar; c+=f.calc_center_median()*ar; a+=ar
        if a<1e-9: continue
        n=n.normalized(); c=c/a
        if n.dot(c-Vector((0,16.5,0)))<0: n=-n
        outer=[f for f in isl if f.normal.dot(n)>0.15] or list(isl)
        out.append((outer,n,c))
    return out

bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
assert cut

# light edge polish if not done
bm=bmesh.new(); bm.from_mesh(cut.data)
short=[e for e in bm.edges if e.is_boundary and e.calc_length()<0.008]
if short:
    bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
    bm.to_mesh(cut.data); cut.data.update()
    log("dissolved short", len(short))
bm.free()

body_bm=wbm(cut); body_bvh=BVHTree.FromBMesh(body_bm)
gl=bmesh.new(); seal=bmesh.new()
for nm in ("WS_L","WS_R","SW_L","SW_R"):
    src=bpy.data.objects.get(nm)
    if not src: continue
    sbm=wbm(src)
    for outer,n,c in outer_faces_island(sbm):
        if sum(f.calc_area() for f in outer)<0.02: continue
        vmap={}
        for f in outer:
            ids=[]
            for v in f.verts:
                if v.index not in vmap:
                    p=v.co-n*GLASS_INSET
                    hit=body_bvh.ray_cast(p+n*0.15,-n)
                    if hit[0] is not None and (hit[0]-p).length<0.35:
                        p=hit[0]-n*GLASS_INSET
                    vmap[v.index]=gl.verts.new(p)
                ids.append(vmap[v.index])
            try: gl.faces.new(ids)
            except ValueError: pass
        ec=defaultdict(int)
        for f in outer:
            for e in f.edges: ec[e]+=1
        created=0
        for e,cnt in ec.items():
            if cnt!=1: continue
            v0,v1=e.verts[0].co,e.verts[1].co
            mid=(v0+v1)*0.5; t=v1-v0
            if t.length<1e-8: continue
            t.normalize()
            inward=c-mid; inward=inward-t*inward.dot(t)
            if inward.length<1e-8: inward=n.cross(t)
            if inward.length<1e-8: continue
            inward.normalize()
            def snap(p, n=n):
                q=p-n*SEAL_INSET
                hit=body_bvh.ray_cast(q+n*0.25,-n)
                if hit[0] is not None and (hit[0]-q).length<0.4:
                    return hit[0]-n*SEAL_INSET
                return q
            pts=[snap(v0),snap(v1),snap(v1+inward*SEAL_W),snap(v0+inward*SEAL_W)]
            try:
                seal.faces.new([seal.verts.new(p) for p in pts]); created+=1
            except ValueError: pass
        log("pane", nm, "seals", created)
    sbm.free()
body_bm.free()

gmat=mkmat("C919_玻璃",(0.867,0.933,0.922),0.02,1.0,0.3)
smat=mkmat("C919_窗框",(0.02,0.02,0.02),0.5)
cmat=mkmat("C919_驾驶舱",(0.07,0.07,0.08),0.6)
for nm,bm,mat in (("C919_玻璃",gl,gmat),("C919_窗框",seal,smat)):
    me=bpy.data.meshes.new(nm+"_m"); bm.to_mesh(me); nfaces=len(me.polygons); bm.free()
    old=bpy.data.objects.get(nm)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    ob=bpy.data.objects.new(nm, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat); log(nm, nfaces)

cabin=bpy.data.objects.get("CockpitCabin")
if cabin:
    cabin.data.materials.clear(); cabin.data.materials.append(cmat)
    cabin.hide_set(False); cabin.hide_render=False

# hide helpers
for o in bpy.data.objects:
    if o.type!="MESH": continue
    hide=(o.name=="Nose" or o.name.startswith(("WS_","SW_","切割")) or "2-287" in o.name
          or o.name in ("CockpitFrames","WindshieldWipers","PanelLines","REF_玻璃","NoseSolid"))
    o.hide_render=hide
    try: o.hide_set(hide)
    except: pass
cut.hide_set(False); cut.hide_render=False
for nm in ("C919_玻璃","C919_窗框","CockpitCabin","Fuselage"):
    o=bpy.data.objects.get(nm)
    if o: o.hide_set(False); o.hide_render=False

# tip verify
bm=wbm(cut); bvh=BVHTree.FromBMesh(bm)
tip_y=max(v.co.y for v in bm.verts)
hit=bvh.ray_cast(Vector((0,tip_y+0.5,0)), Vector((0,-1,0)))
dist=(hit[0]-Vector((0,tip_y+0.5,0))).length if hit[0] else 999
tip_status="SOLID" if dist<0.85 else f"OPEN dist={dist:.2f}"
vs=[v for v in bm.verts if v.co.y>tip_y-0.03]
rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
axis=sorted([(round(v.co.x,4),round(v.co.y,4),round(v.co.z,4))
             for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5],
            key=lambda t:-t[1])[:5]
open_n=0
for name,p in [("WS_R",Vector((0.55,17.3,1.35))),("WS_L",Vector((-0.55,17.3,1.35))),
               ("SW_R",Vector((1.65,16.3,0.6))),("SW_L",Vector((-1.65,16.3,0.6)))]:
    radial=Vector((p.x,0,p.z)); radial.normalize()
    h=bvh.ray_cast(p+radial*1.2,-radial)
    st="OPEN" if (h[0] is None or (h[0]-(p+radial*1.2)).length>=0.85) else "SOLID"
    if st=="OPEN": open_n+=1
be=sum(1 for e in bm.edges if e.is_boundary)
sil=[]
for y in [19.6,19.8,20.0,20.2,20.4]:
    ring=[v for v in bm.verts if abs(v.co.y-y)<0.025]
    if not ring: sil.append({"y":y,"empty":True}); continue
    rr=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
    sil.append({"y":y,"r_mean":round(sum(rr)/len(rr),3),"r_min":round(min(rr),3),"n":len(ring)})
bm.free()
seal_n=len(bpy.data.objects["C919_窗框"].data.polygons)
glass_n=len(bpy.data.objects["C919_玻璃"].data.polygons)
log("tip", tip_status, "r_min", min(rs) if rs else None, "seals", seal_n, "open", open_n, "axis", axis)

# render
sc=bpy.context.scene; sc.render.engine="BLENDER_WORKBENCH"
sc.render.resolution_x=1280; sc.render.resolution_y=720
cam=bpy.data.objects.get("NoseFixCam")
if not cam:
    cd=bpy.data.cameras.new("NoseFixCam"); cam=bpy.data.objects.new("NoseFixCam",cd)
    bpy.context.collection.objects.link(cam)
sc.camera=cam
tip=Vector((0,19.9,0.55))
for tag,eye,lens in (("front",tip+Vector((0,6,0.4)),55),("side",tip+Vector((7,-1,0.8)),50),("45",tip+Vector((4.5,4,1.5)),50)):
    cam.location=eye; cam.data.lens=lens
    cam.rotation_euler=(tip-eye).normalized().to_track_quat("-Z","Y").to_euler()
    sc.render.filepath=os.path.join(OUT,f"polish_final_{tag}.png")
    bpy.ops.render.render(write_still=True)
    log("render", tag)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
size=os.path.getsize(GLB); log("GLB", size)
bpy.ops.wm.save_as_mainfile(filepath=WORK)

missing=[]
if seal_n<=0: missing.append("seals 0")
if open_n<4: missing.append(f"open={open_n}")
if (min(rs) if rs else 1)>0.08: missing.append(f"tip r_min={min(rs):.3f}")
if tip_status!="SOLID": missing.append(f"tip {tip_status}")

report={"glb":size,"seal_faces":seal_n,"glass_faces":glass_n,"tip_status":tip_status,
        "tip_y":tip_y,"r_min":min(rs) if rs else None,"r_mean":sum(rs)/len(rs) if rs else None,
        "axis":axis,"sil":sil,"open":open_n,"boundary":be,"missing":missing}
with open(os.path.join(LOG,"polish_final_report.json"),"w",encoding="utf-8") as f:
    json.dump(report,f,indent=2,ensure_ascii=False)

with open(NOTES,"w",encoding="utf-8") as f:
    f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm boundary, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_n} faces** from WS/SW outer-face boundaries (closed thin solids had 0 island boundary)
   - ~4 cm, inset 2 mm, BVH snap onto skin, black Roughness 0.5, flush/inward
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: centerline sphere-map (cx=cz=0) + poke tip on +Y axis — continuous arc, not flat disk
5. Helpers hidden; GLB use_visible=True; no REF mesh merged

## Checks
- windows OPEN: {open_n}/4
- tip_axis: {tip_status}; tip_y={tip_y:.3f}; r_min={min(rs) if rs else None}; r_mean={sum(rs)/len(rs) if rs else None}
- near_axis: {axis}
- sil: {sil}
- boundary_edges: {be}
- seal_faces={seal_n} glass_faces={glass_n}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING ({len(missing)})
""" + ("\n".join("- "+m for m in missing) if missing else "- none critical") + """

## Honesty
- Window rims still have some OBB-boolean faceting (not CAD fillets).
- Seals follow pane outlines; may not hug every jagged hole edge perfectly.
- Radome is sphere-mapped from the old flat tip (better arc than a plate, not REF-perfect CAD).
""")
log("DONE", size, "seals", seal_n, "open", open_n, "missing", missing)
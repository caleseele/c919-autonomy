# -*- coding: utf-8 -*-
"""Finish polish v5: verify + export + notes (mesh already radome-fixed in blend)."""
import json, math, os
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

def log(*a):
    print("FINISH", *a, flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
assert cut

# If tip not solid, re-apply centerline radome quickly
dg = bpy.context.evaluated_depsgraph_get()
ev = cut.evaluated_get(dg)
bm = bmesh.new(); bm.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
bm.transform(cut.matrix_world); bm.normal_update()
tip_y = max(v.co.y for v in bm.verts)
bvh = BVHTree.FromBMesh(bm)
hit = bvh.ray_cast(Vector((0, tip_y+0.5, 0)), Vector((0,-1,0)))
dist = (hit[0]-Vector((0,tip_y+0.5,0))).length if hit[0] else 999
vs = [v for v in bm.verts if v.co.y > tip_y-0.03]
rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
axis = sorted([(round(v.co.x,4),round(v.co.y,4),round(v.co.z,4))
               for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5],
              key=lambda t:-t[1])[:5]
log("loaded tip_y", tip_y, "dist", dist, "r_min", min(rs) if rs else None, "axis", axis)

need_fix = (dist >= 0.85) or (not rs) or (min(rs) > 0.08) or (not axis)
bm.free()

if need_fix:
    log("re-apply radome")
    # inline centerline
    bm = bmesh.new(); bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
    tip_y = max(v.co.y for v in bm.verts)
    flat=[]
    for f in bm.faces:
        c=f.calc_center_median(); n=f.normal.normalized(); r=math.sqrt(c.x**2+c.z**2)
        if c.y>=tip_y-0.45 and r<=0.65 and n.y>=0.65: flat.append(f)
    tip_verts=set()
    for f in flat:
        for v in f.verts: tip_verts.add(v)
    for v in bm.verts:
        if v.co.y>tip_y-0.40 and math.sqrt(v.co.x**2+v.co.z**2)<0.55: tip_verts.add(v)
    rim=[v for v in tip_verts if 0.30<=math.sqrt(v.co.x**2+v.co.z**2)<=0.55]
    if len(rim)<6: rim=sorted(tip_verts, key=lambda v: -math.sqrt(v.co.x**2+v.co.z**2))[:12]
    cy=sum(v.co.y for v in rim)/len(rim)
    R=sum(math.sqrt(v.co.x**2+v.co.z**2) for v in rim)/len(rim)
    R=max(min(R,0.60),0.35)
    for v in tip_verts:
        dx,dz=v.co.x,v.co.z; r=math.sqrt(dx*dx+dz*dz)
        if r>R and r>1e-9:
            s=R/r; v.co.x=dx*s; v.co.z=dz*s; r=R
        r_clamped=min(r,R*0.999999)
        v.co.y=cy+math.sqrt(max(0.0,R*R-r_clamped*r_clamped))
    best=min(flat, key=lambda f: f.calc_center_median().x**2+f.calc_center_median().z**2)
    ret=bmesh.ops.poke(bm, faces=[best])
    for v in ret.get("verts",[]):
        v.co=Vector((0.0, cy+R, 0.0)); log("poke", tuple(v.co))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data); cut.data.update(); bm.free()

# final stats
bm = bmesh.new(); bm.from_mesh(cut.data); bm.normal_update()
tip_y = max(v.co.y for v in bm.verts)
bvh = BVHTree.FromBMesh(bm)
hit = bvh.ray_cast(Vector((0, tip_y+0.5, 0)), Vector((0,-1,0)))
dist = (hit[0]-Vector((0,tip_y+0.5,0))).length if hit[0] else 999
tip_status = "SOLID" if dist < 0.85 else f"OPEN dist={dist:.2f}"
vs = [v for v in bm.verts if v.co.y > tip_y-0.03]
rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
axis = sorted([(round(v.co.x,4),round(v.co.y,4),round(v.co.z,4))
               for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5],
              key=lambda t:-t[1])[:5]
open_n=0
for name,p in [("WS_R",Vector((0.55,17.3,1.35))),("WS_L",Vector((-0.55,17.3,1.35))),
               ("SW_R",Vector((1.65,16.3,0.6))),("SW_L",Vector((-1.65,16.3,0.6)))]:
    radial=Vector((p.x,0,p.z)); radial.normalize()
    h=bvh.ray_cast(p+radial*1.2,-radial)
    st="OPEN" if (h[0] is None or (h[0]-(p+radial*1.2)).length>=0.85) else "SOLID"
    if st=="OPEN": open_n+=1
    log("check", name, st)
be=sum(1 for e in bm.edges if e.is_boundary)
sil=[]
for y in [19.6,19.8,20.0,20.1,20.2,20.3,20.4]:
    ring=[v for v in bm.verts if abs(v.co.y-y)<0.025]
    if not ring: sil.append({"y":y,"empty":True}); continue
    rr=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
    sil.append({"y":y,"r_mean":round(sum(rr)/len(rr),3),"r_min":round(min(rr),3),"n":len(ring)})
bm.free()
log("FINAL tip", tip_status, "r_min", min(rs) if rs else None, "r_mean", sum(rs)/len(rs) if rs else None, "axis", axis)

seal=bpy.data.objects.get("C919_窗框"); glass=bpy.data.objects.get("C919_玻璃")
seal_n=len(seal.data.polygons) if seal else 0
glass_n=len(glass.data.polygons) if glass else 0
log("seal", seal_n, "glass", glass_n, "open", open_n, "boundary", be)

# hide + render
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

with open(os.path.join(LOG,"polish_v5_report.json"),"w",encoding="utf-8") as f:
    json.dump({"glb":size,"seal_faces":seal_n,"glass_faces":glass_n,"tip_status":tip_status,
               "tip_y":tip_y,"r_min":min(rs) if rs else None,"r_mean":sum(rs)/len(rs) if rs else None,
               "axis":axis,"sil":sil,"open":open_n,"boundary":be,"missing":missing}, f, indent=2, ensure_ascii=False)

with open(NOTES,"w",encoding="utf-8") as f:
    f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm boundary, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_n} faces** from WS/SW outer-face boundaries (panes are closed thin solids → island boundary was 0)
   - ~4 cm wide, inset 2 mm, BVH-projected onto skin, black Roughness 0.5
3. Glass: single-sided outer rebuild, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: centerline sphere-map (cx=cz=0) + poke tip vert on +Y axis → continuous arc (not flat disk)
5. Helpers hidden (CockpitFrames/REF/cutters); GLB use_visible=True
6. No REF mesh merged into export

## Checks
- windows OPEN: {open_n}/4
- tip_axis: {tip_status}; tip_y={tip_y:.3f}; r_min={min(rs) if rs else None}; r_mean={sum(rs)/len(rs) if rs else None}
- near_axis: {axis}
- silhouette: {sil}
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
- Window rims still show some OBB-boolean faceting (not CAD fillets).
- Seals follow pane outlines; may not perfectly hug every jagged hole edge.
- Radome is a sphere-map of the old flat tip disk (R≈0.35–0.45 m), better arc than a flat plate, not REF-perfect.
""")
log("DONE", size, "seals", seal_n, "open", open_n, "missing", missing)
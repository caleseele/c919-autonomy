# -*- coding: utf-8 -*-
"""Aggressive radome rebuild: chop tip, hemisphere from clean ring at y~19.75."""
from __future__ import annotations
import math, os
import bmesh, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
OUT = os.path.join(PROJ, "public", "models", "nose-fix")
NOTES = os.path.join(PROJ, "scripts", "NOSE_POLISH_PASS_NOTES.zh-Hans.md")

def log(*a):
    print("RADOME2", *a, flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
assert cut

# Work in object local (identity expected)
bm = bmesh.new()
bm.from_mesh(cut.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# Chop plane: remove everything forward of Y_CUT with r < R_CUT*1.15
# Find good cut: scan for ring with r~0.6-0.75 at y in 19.4-19.9
best=None
for y0 in [19.4 + i*0.05 for i in range(0, 16)]:
    ring=[v for v in bm.verts if abs(v.co.y-y0)<0.03]
    if len(ring)<12: continue
    rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
    rmean=sum(rs)/len(rs)
    if 0.50 <= rmean <= 0.90:
        score=abs(rmean-0.65)+abs(y0-19.65)*0.3
        if best is None or score<best[0]:
            best=(score,y0,rmean,len(ring))
log("best ring candidate", best)
Y_CUT = best[1] if best else 19.65
R_EQ = best[2] if best else 0.65

# Delete faces whose center is forward of Y_CUT - 0.02 (entire nose tip region)
kill_faces=[]
for f in bm.faces:
    c=f.calc_center_median()
    if c.y > Y_CUT - 0.02:
        kill_faces.append(f)
log("kill faces forward of", Y_CUT, ":", len(kill_faces))
if kill_faces:
    bmesh.ops.delete(bm, geom=kill_faces, context="FACES")
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

# Delete verts with y > Y_CUT + 0.01 that are now orphan or still there
kill_verts=[v for v in bm.verts if v.co.y > Y_CUT + 0.01]
if kill_verts:
    log("kill forward verts", len(kill_verts))
    bmesh.ops.delete(bm, geom=kill_verts, context="VERTS")
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

# orphans
orph=[v for v in bm.verts if not v.link_faces]
if orph:
    log("orphans", len(orph))
    bmesh.ops.delete(bm, geom=orph, context="VERTS")
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()

# Find tip boundary loop — highest cy among loops with r~R_EQ
used=set(); tip_verts=None; best_score=-1e9; tip_meta=None
for e0 in bm.edges:
    if not e0.is_boundary or e0.index in used: continue
    verts=[]; start=e0.verts[0]; prev=start; nxt=e0.verts[1]; used.add(e0.index); verts.append(start)
    guard=0
    while nxt!=start and guard<20000:
        guard+=1; verts.append(nxt)
        found=None
        for e in nxt.link_edges:
            if e.is_boundary and e.index not in used:
                found=e; break
        if not found: break
        used.add(found.index); prev=nxt
        nxt=found.verts[0] if found.verts[1]==prev else found.verts[1]
    if len(verts)<8: continue
    cy=sum(v.co.y for v in verts)/len(verts)
    cx=sum(v.co.x for v in verts)/len(verts)
    cz=sum(v.co.z for v in verts)/len(verts)
    rs=[math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in verts]
    rmean=sum(rs)/len(rs)
    if cy < Y_CUT - 0.5: continue
    score = cy - abs(rmean - R_EQ)
    if score > best_score:
        best_score=score; tip_verts=verts; tip_meta=(cx,cy,cz,rmean,len(verts))

if tip_verts is None:
    log("FAIL no tip loop")
else:
    cx,cy,cz,rmean,n = tip_meta
    log("tip loop", tip_meta)
    R = max(min(rmean, 0.80), 0.45)
    ordered = sorted(tip_verts, key=lambda v: math.atan2(v.co.z-cz, v.co.x-cx))
    # snap ring to circle
    for v in ordered:
        ang=math.atan2(v.co.z-cz, v.co.x-cx)
        v.co.x = cx + R*math.cos(ang)
        v.co.z = cz + R*math.sin(ang)
        v.co.y = cy

    n_rings = 6
    rings = [ordered]
    for ri in range(1, n_rings):
        phi = (ri / n_rings) * (math.pi * 0.5)
        yy = cy + R * math.sin(phi)
        rr = R * math.cos(phi)
        new_ring=[]
        for v in ordered:
            ang=math.atan2(v.co.z-cz, v.co.x-cx)
            new_ring.append(bm.verts.new((cx+rr*math.cos(ang), yy, cz+rr*math.sin(ang))))
        prev=rings[-1]
        nn=len(ordered)
        for i in range(nn):
            j=(i+1)%nn
            try: bm.faces.new([prev[i], prev[j], new_ring[j], new_ring[i]])
            except ValueError: pass
        rings.append(new_ring)

    tip_v = bm.verts.new((cx, cy+R, cz))
    last=rings[-1]; nn=len(last)
    for i in range(nn):
        j=(i+1)%nn
        try: bm.faces.new([last[i], last[j], tip_v])
        except ValueError: pass

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    center=Vector((cx,cy,cz))
    flipped=0
    for f in bm.faces:
        c=f.calc_center_median()
        if c.y > cy - 0.02:
            if f.normal.dot(c-center) < 0:
                f.normal_flip(); flipped+=1
    log("flipped", flipped, "sphere tip", cy+R, "R", R)

bm.to_mesh(cut.data); cut.data.update(); bm.free()

# verify
bm=bmesh.new(); bm.from_mesh(cut.data); bm.transform(cut.matrix_world); bm.normal_update()
new_tip=max(v.co.y for v in bm.verts)
# band very tip
vs=[v for v in bm.verts if v.co.y > new_tip-0.03]
rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
log("new_tip", new_tip, "band3cm n", len(vs), "r_mean", sum(rs)/len(rs) if rs else None, "r_min", min(rs) if rs else None, "r_max", max(rs) if rs else None)
# silhouette samples along y
for y in [19.5, 19.7, 19.9, 20.1, 20.3, 20.5]:
    ring=[v for v in bm.verts if abs(v.co.y-y)<0.04]
    if not ring: log(f"sil y={y} empty"); continue
    rr=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
    log(f"sil y={y:.1f} r_mean={sum(rr)/len(rr):.3f} r_max={max(rr):.3f}")
bvh=BVHTree.FromBMesh(bm)
hit=bvh.ray_cast(Vector((0,new_tip+1,0)), Vector((0,-1,0)))
log("axis", "hit" if hit[0] else "MISS", hit[0].y if hit[0] else None, "dist", (hit[0]-Vector((0,new_tip+1,0))).length if hit[0] else None)
open_n=0
for name,p in [("WS_R",Vector((0.55,17.3,1.35))),("WS_L",Vector((-0.55,17.3,1.35))),
               ("SW_R",Vector((1.65,16.3,0.6))),("SW_L",Vector((-1.65,16.3,0.6)))]:
    radial=Vector((p.x,0,p.z)); radial.normalize()
    h=bvh.ray_cast(p+radial*1.2,-radial)
    st="OPEN" if (h[0] is None or (h[0]-(p+radial*1.2)).length>=0.85) else "SOLID"
    if st=="OPEN": open_n+=1
    log("check",name,st)
bm.free()

seal=bpy.data.objects.get("C919_窗框"); glass=bpy.data.objects.get("C919_玻璃")
log("seal", len(seal.data.polygons) if seal else 0, "glass", len(glass.data.polygons) if glass else 0)

for o in bpy.data.objects:
    if o.type!="MESH": continue
    hide=(o.name=="Nose" or o.name.startswith("WS_") or o.name.startswith("SW_")
          or o.name.startswith("切割") or "2-287" in o.name
          or o.name in ("CockpitFrames","WindshieldWipers","PanelLines","REF_玻璃","NoseSolid"))
    o.hide_render=hide
    try: o.hide_set(hide)
    except: pass
cut.hide_set(False); cut.hide_render=False
for nm in ("C919_玻璃","C919_窗框","CockpitCabin"):
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
    fp=os.path.join(OUT,f"polish_final_{tag}.png"); sc.render.filepath=fp
    bpy.ops.render.render(write_still=True); log("render",fp)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
size=os.path.getsize(GLB); log("GLB", size)
bpy.ops.wm.save_as_mainfile(filepath=WORK)

r_mean = sum(rs)/len(rs) if rs else -1
missing=[]
if open_n<4: missing.append(f"open={open_n}")
if r_mean>0.12: missing.append(f"tip r_mean={r_mean:.3f}")
if not seal or len(seal.data.polygons)==0: missing.append("no seals")
with open(NOTES,"w",encoding="utf-8") as f:
    f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish (dissolve short / limited dissolve / loop smooth)
2. Seals: **{len(seal.data.polygons) if seal else 0} faces** — from WS/SW outer faces, 4cm, flush/inward, BVH snap
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3 inset 4mm
4. Radome v2: chopped faces y>{Y_CUT:.2f}, hemisphere fan R={R_EQ:.3f} from tip boundary (6 rings + tip vert)
5. Helpers hidden; GLB use_visible=True

## Checks
- windows OPEN: {open_n}/4
- tip_y={new_tip:.3f}; last-3cm r_mean={r_mean:.3f} r_min={min(rs) if rs else None}
- seal={len(seal.data.polygons) if seal else 0} glass={len(glass.data.polygons) if glass else 0}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING ({len(missing)})
""" + ("\n".join("- "+m for m in missing) if missing else "- none critical") + "\n")
log("DONE", size, "open", open_n, "r_mean", r_mean, "missing", missing)
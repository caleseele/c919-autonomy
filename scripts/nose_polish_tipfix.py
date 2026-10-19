# -*- coding: utf-8 -*-
"""Fix flat radome disk: delete tip faces, hemisphere fan from ring. Also verify seals."""
from __future__ import annotations
import json, math, os, shutil
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
    print("TIPFIX", *a, flush=True)

def mkmat(name, col, rough, trans=None, alpha=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (*col, 1)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = rough
    if trans is not None:
        for k in ("Transmission Weight", "Transmission"):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = trans
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.5
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            if hasattr(mat, attr):
                try: setattr(mat, attr, val)
                except Exception: pass
    return mat

bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
assert cut

bm = bmesh.new()
bm.from_mesh(cut.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
bm.normal_update()

# --- identify flat tip faces: high Y, normal mostly +Y ---
tip_y = max(v.co.y for v in bm.verts)
flat = []
for f in bm.faces:
    c = f.calc_center_median()
    n = f.normal.normalized()
    if c.y > tip_y - 0.55 and n.y > 0.55:
        flat.append(f)
    elif c.y > tip_y - 0.35 and n.y > 0.35 and math.sqrt(c.x**2+c.z**2) < 0.7:
        flat.append(f)
# unique
flat = list({f.index: f for f in flat}.values())
log("flat tip faces", len(flat), "tip_y", tip_y)

# also collect verts that stick past a chosen equator with large r (rim spikes)
# Choose equator: find ring with r~0.55-0.7 around y where flat faces start
if flat:
    flat_y_min = min(f.calc_center_median().y for f in flat)
else:
    flat_y_min = tip_y - 0.4
log("flat_y_min", flat_y_min)

# Delete flat faces
if flat:
    bmesh.ops.delete(bm, geom=flat, context="FACES")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

# Find tip boundary loop (highest mean y among boundary loops with small r)
used=set(); tip_loop_verts=None; tip_loop_score=-1e9
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
        nxt = found.verts[0] if found.verts[1]==prev else found.verts[1]
    if len(verts) < 6: continue
    cy = sum(v.co.y for v in verts)/len(verts)
    rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in verts]
    rmean = sum(rs)/len(rs)
    # tip ring: high y, moderate r
    if cy < 18.5: continue
    if rmean > 1.2 or rmean < 0.15: continue
    score = cy - abs(rmean - 0.55)*0.5
    if score > tip_loop_score:
        tip_loop_score = score
        tip_loop_verts = verts
        tip_rmean = rmean
        tip_cy = cy

if tip_loop_verts is None:
    log("NO tip loop found — abort radome fan")
else:
    log("tip loop n", len(tip_loop_verts), "cy", round(tip_cy,3), "rmean", round(tip_rmean,3))
    # Order verts around circle by atan2
    cx = sum(v.co.x for v in tip_loop_verts)/len(tip_loop_verts)
    cz = sum(v.co.z for v in tip_loop_verts)/len(tip_loop_verts)
    ordered = sorted(tip_loop_verts, key=lambda v: math.atan2(v.co.z-cz, v.co.x-cx))
    R = sum(math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in ordered)/len(ordered)
    R = max(min(R, 0.85), 0.35)
    # Pull ring verts onto perfect circle at tip_cy
    for v in ordered:
        ang = math.atan2(v.co.z-cz, v.co.x-cx)
        v.co.x = cx + R * math.cos(ang)
        v.co.z = cz + R * math.sin(ang)
        v.co.y = tip_cy

    # Build hemisphere: rings of verts + tip
    n_rings = 5
    ring_verts = [ordered]
    for ri in range(1, n_rings):
        # parametric: from equator (phi=0) to near tip (phi -> pi/2)
        phi = (ri / n_rings) * (math.pi * 0.5)
        # y = tip_cy + R*sin(phi); r = R*cos(phi)
        yy = tip_cy + R * math.sin(phi)
        rr = R * math.cos(phi)
        new_ring = []
        for v in ordered:
            ang = math.atan2(v.co.z-cz, v.co.x-cx)
            nv = bm.verts.new((cx + rr*math.cos(ang), yy, cz + rr*math.sin(ang)))
            new_ring.append(nv)
        ring_verts.append(new_ring)
        # bridge quads between ring_verts[ri-1] and ring_verts[ri]
        prev = ring_verts[ri-1]
        n = len(ordered)
        for i in range(n):
            j = (i+1)%n
            try:
                bm.faces.new([prev[i], prev[j], new_ring[j], new_ring[i]])
            except ValueError:
                pass

    tip_v = bm.verts.new((cx, tip_cy + R, cz))
    last = ring_verts[-1]
    n = len(last)
    for i in range(n):
        j = (i+1)%n
        try:
            bm.faces.new([last[i], last[j], tip_v])
        except ValueError:
            pass

    # Also delete any leftover verts that were past the old flat tip and are now loose
    # (orphans with no faces)
    orphans = [v for v in bm.verts if not v.link_faces]
    if orphans:
        log("delete orphans", len(orphans))
        bmesh.ops.delete(bm, geom=orphans, context="VERTS")

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # flip any tip faces pointing inward
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y > tip_cy - 0.05:
            # want outward: away from sphere center (cx, tip_cy, cz)
            center = Vector((cx, tip_cy, cz))
            if f.normal.dot(c - center) < 0:
                f.normal_flip()

bm.to_mesh(cut.data)
cut.data.update()
bm.free()

# re-open and measure
bm = bmesh.new(); bm.from_mesh(cut.data); bm.transform(cut.matrix_world)
new_tip = max(v.co.y for v in bm.verts)
tip_verts = [v for v in bm.verts if v.co.y > new_tip - 0.05]
rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in tip_verts]
log("new_tip", new_tip, "n", len(tip_verts), "r_mean", sum(rs)/len(rs) if rs else None, "r_max", max(rs) if rs else None, "r_min", min(rs) if rs else None)
# axis ray
bvh = BVHTree.FromBMesh(bm)
origin = Vector((0, new_tip+1.0, 0))
hit = bvh.ray_cast(origin, Vector((0,-1,0)))
if hit[0]:
    dist=(hit[0]-origin).length
    log("axis hit y", hit[0].y, "dist", dist, "SOLID" if dist<0.9 else "OPEN-ish")
else:
    log("axis MISS")

# window checks
open_n=0
for name,p in [("WS_R",Vector((0.55,17.3,1.35))),("WS_L",Vector((-0.55,17.3,1.35))),
               ("SW_R",Vector((1.65,16.3,0.6))),("SW_L",Vector((-1.65,16.3,0.6)))]:
    radial=Vector((p.x,0,p.z)); radial.normalize()
    hit=bvh.ray_cast(p+radial*1.2, -radial)
    st="OPEN" if (hit[0] is None or (hit[0]-(p+radial*1.2)).length>=0.85) else "SOLID"
    if st=="OPEN": open_n+=1
    log("check", name, st)
bm.free()

# ensure seals still present
seal=bpy.data.objects.get("C919_窗框")
glass=bpy.data.objects.get("C919_玻璃")
log("seal faces", len(seal.data.polygons) if seal else 0, "glass", len(glass.data.polygons) if glass else 0)

# hide helpers
for o in bpy.data.objects:
    if o.type!="MESH": continue
    hide = (o.name=="Nose" or o.name.startswith("WS_") or o.name.startswith("SW_")
            or o.name.startswith("切割") or "2-287" in o.name
            or o.name in ("CockpitFrames","WindshieldWipers","PanelLines","REF_玻璃","NoseSolid"))
    o.hide_render=hide
    try: o.hide_set(hide)
    except: pass
cut.hide_set(False); cut.hide_render=False
for nm in ("C919_玻璃","C919_窗框","CockpitCabin"):
    o=bpy.data.objects.get(nm)
    if o: o.hide_set(False); o.hide_render=False

# render
sc=bpy.context.scene
sc.render.engine="BLENDER_WORKBENCH"
sc.render.resolution_x=1280; sc.render.resolution_y=720
cam=bpy.data.objects.get("NoseFixCam")
if not cam:
    cd=bpy.data.cameras.new("NoseFixCam"); cam=bpy.data.objects.new("NoseFixCam",cd)
    bpy.context.collection.objects.link(cam)
sc.camera=cam
tip=Vector((0,19.9,0.55))
for tag,eye,lens in (("front", tip+Vector((0,6,0.4)),55),("side", tip+Vector((7,-1,0.8)),50),("45", tip+Vector((4.5,4,1.5)),50)):
    cam.location=eye; cam.data.lens=lens
    cam.rotation_euler=(tip-eye).normalized().to_track_quat("-Z","Y").to_euler()
    fp=os.path.join(OUT, f"polish_final_{tag}.png")
    sc.render.filepath=fp
    bpy.ops.render.render(write_still=True)
    log("render", fp)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
size=os.path.getsize(GLB)
log("GLB", size)
bpy.ops.wm.save_as_mainfile(filepath=WORK)

# update notes
r_mean = sum(rs)/len(rs) if rs else -1
missing=[]
if (seal and len(seal.data.polygons)<=0): missing.append("seals 0")
if open_n<4: missing.append(f"windows open={open_n}")
if r_mean>0.15: missing.append(f"tip r_mean={r_mean:.3f} still >0.15 in last 5cm band")
with open(NOTES,"w",encoding="utf-8") as f:
    f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve short boundary, limited dissolve 8°, loop smooth
2. Seals: **{len(seal.data.polygons) if seal else 0} faces** from WS/SW outer-face boundaries (4cm, flush/inward, BVH snap)
3. Glass: single-sided outer rebuild, Transmission #DDEEEB Alpha 0.3
4. Radome: deleted flat +Y tip faces, built hemisphere fan (5 rings) from tip boundary loop → continuous arc
5. Helpers hidden; GLB use_visible=True

## Checks
- windows OPEN: {open_n}/4
- tip_y: {new_tip:.3f}; tip band r_mean={r_mean:.3f} r_min={min(rs) if rs else None}
- seal faces: {len(seal.data.polygons) if seal else 0}
- glass faces: {len(glass.data.polygons) if glass else 0}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING ({len(missing)})
""" + ("\n".join(f"- {m}" for m in missing) if missing else "- none critical") + "\n")
log("DONE", size, "open", open_n, "seal", len(seal.data.polygons) if seal else 0, "missing", missing)
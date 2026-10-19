# -*- coding: utf-8 -*-
"""C919 nose polish v3: edges + seals + poke/hemisphere radome (tip-only)."""
from __future__ import annotations
import json, math, os, shutil
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
os.makedirs(OUT, exist_ok=True); os.makedirs(LOG, exist_ok=True)

def log(*a):
    print("POLISHv3", *a, flush=True)

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

def boundary_loops(bm):
    used=set(); loops=[]
    for e0 in bm.edges:
        if not e0.is_boundary or e0.index in used: continue
        edges=[]; verts=[]; start=e0.verts[0]; prev=start; nxt=e0.verts[1]
        used.add(e0.index); edges.append(e0); verts.append(start)
        guard=0
        while nxt!=start and guard<20000:
            guard+=1; verts.append(nxt)
            found=None
            for e in nxt.link_edges:
                if e.is_boundary and e.index not in used:
                    found=e; break
            if not found: break
            used.add(found.index); edges.append(found); prev=nxt
            nxt = found.verts[0] if found.verts[1]==prev else found.verts[1]
        if len(edges)>=8: loops.append((edges, verts))
    return loops

def polish_edges(cut):
    bm=bmesh.new(); bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    short=[e for e in bm.edges if e.is_boundary and e.calc_length()<0.008]
    if short:
        bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        log("dissolved short", len(short))
    near=set()
    for e in bm.edges:
        if e.is_boundary:
            for f in e.link_faces: near.add(f)
    if near:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(8), use_dissolve_boundaries=False,
            verts=list({v for f in near for v in f.verts}),
            edges=list({e for f in near for e in f.edges if not e.is_boundary}))
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    for _ in range(8):
        loops=boundary_loops(bm); moves={}
        for edges, verts in loops:
            n=len(verts); ys=[v.co.y for v in verts]
            if n<8 or max(ys)<15.2 or min(ys)>19.0: continue
            for i,v in enumerate(verts):
                target=(verts[(i-1)%n].co + verts[(i+1)%n].co)*0.5
                moves[v.index]=v.co.lerp(target, 0.45)
        for idx,co in moves.items(): bm.verts[idx].co=co
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data); cut.data.update()
    be=sum(1 for e in bm.edges if e.is_boundary); nl=len(boundary_loops(bm)); bm.free()
    log("polish edges be", be, "loops", nl); return be, nl

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

def rebuild_glass_seals(cut):
    sources=[bpy.data.objects[n] for n in ("WS_L","WS_R","SW_L","SW_R") if bpy.data.objects.get(n)]
    body_bm=wbm(cut); body_bvh=BVHTree.FromBMesh(body_bm)
    gl=bmesh.new(); seal=bmesh.new(); report=[]
    for src in sources:
        sbm=wbm(src)
        for outer,n,c in outer_faces_island(sbm):
            if sum(f.calc_area() for f in outer)<0.02: continue
            vmap={}
            for f in outer:
                ids=[]
                for v in f.verts:
                    if v.index not in vmap:
                        p=v.co-n*GLASS_INSET
                        hit=body_bvh.ray_cast(p+n*0.15, -n)
                        if hit[0] is not None and (hit[0]-p).length<0.35:
                            p=hit[0]-n*GLASS_INSET
                        vmap[v.index]=gl.verts.new(p)
                    ids.append(vmap[v.index])
                try: gl.faces.new(ids)
                except ValueError: pass
            ec=defaultdict(int)
            for f in outer:
                for e in f.edges: ec[e]+=1
            bedges=[e for e,cnt in ec.items() if cnt==1]; created=0
            for e in bedges:
                v0,v1=e.verts[0].co, e.verts[1].co
                mid=(v0+v1)*0.5; t=v1-v0
                if t.length<1e-8: continue
                t.normalize()
                inward=c-mid; inward=inward-t*inward.dot(t)
                if inward.length<1e-8: inward=n.cross(t)
                if inward.length<1e-8: continue
                inward.normalize()
                def snap(p):
                    q=p-n*SEAL_INSET
                    hit=body_bvh.ray_cast(q+n*0.25,-n)
                    if hit[0] is not None and (hit[0]-q).length<0.4:
                        return hit[0]-n*SEAL_INSET
                    return q
                pts=[snap(v0),snap(v1),snap(v1+inward*SEAL_W),snap(v0+inward*SEAL_W)]
                try:
                    seal.faces.new([seal.verts.new(p) for p in pts]); created+=1
                except ValueError: pass
            report.append({"src":src.name,"seals":created,"bedges":len(bedges)})
            log("pane", src.name, "seals", created)
        sbm.free()
    body_bm.free()
    gmat=mkmat("C919_玻璃",(0.867,0.933,0.922),0.02,1.0,0.3)
    smat=mkmat("C919_窗框",(0.02,0.02,0.02),0.5)
    cmat=mkmat("C919_驾驶舱",(0.07,0.07,0.08),0.6)
    out_counts={}
    for nm,bm,mat in (("C919_玻璃",gl,gmat),("C919_窗框",seal,smat)):
        me=bpy.data.meshes.new(nm+"_m"); bm.to_mesh(me); out_counts[nm]=len(me.polygons); bm.free()
        old=bpy.data.objects.get(nm)
        if old: bpy.data.objects.remove(old, do_unlink=True)
        ob=bpy.data.objects.new(nm, me); bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat); log(nm, out_counts[nm])
    cabin=bpy.data.objects.get("CockpitCabin")
    if cabin:
        cabin.data.materials.clear(); cabin.data.materials.append(cmat)
        cabin.hide_set(False); cabin.hide_render=False
    return {"seal_faces": out_counts.get("C919_窗框",0), "glass_faces": out_counts.get("C919_玻璃",0), "panes": report}

def radome_tip_only(cut):
    """Delete ONLY flat tip-disk faces (ny high, r small, y high). Hemisphere from that ring."""
    bm=bmesh.new(); bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
    tip_y=max(v.co.y for v in bm.verts)

    # Flat tip faces: center near axis, facing mostly +Y, near tip
    flat=[]
    for f in bm.faces:
        c=f.calc_center_median(); n=f.normal.normalized()
        r=math.sqrt(c.x*c.x+c.z*c.z)
        if c.y < tip_y - 0.6: continue
        if r > 0.75: continue
        if n.y < 0.45: continue
        flat.append(f)
    flat=list({f.index:f for f in flat}.values())
    log("flat tip faces", len(flat), "tip_y", tip_y)
    if not flat:
        bm.free(); return {"ok": False, "reason": "no flat faces"}

    # Boundary verts of flat region BEFORE delete
    flat_set=set(flat)
    ring_edges=[]
    for f in flat:
        for e in f.edges:
            # edge is on rim if not all link_faces in flat
            if any(lf not in flat_set for lf in e.link_faces) or e.is_boundary:
                ring_edges.append(e)
    # unique ring verts
    ring_vert_set=set()
    for e in ring_edges:
        # keep only edges that have exactly one face in flat (true rim)
        n_flat=sum(1 for lf in e.link_faces if lf in flat_set)
        if n_flat==1:
            for v in e.verts: ring_vert_set.add(v)
    log("ring verts before delete", len(ring_vert_set))

    bmesh.ops.delete(bm, geom=flat, context="FACES")
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

    # After delete, tip hole boundary should be the ring — pick highest-y small-r loop
    used=set(); tip_loop=None; best=-1e9; meta=None
    for e0 in bm.edges:
        if not e0.is_boundary or e0.index in used: continue
        verts=[]; start=e0.verts[0]; prev=start; nxt=e0.verts[1]; used.add(e0.index); verts.append(start)
        guard=0
        while nxt!=start and guard<20000:
            guard+=1; verts.append(nxt)
            found=None
            for e in nxt.link_edges:
                if e.is_boundary and e.index not in used: found=e; break
            if not found: break
            used.add(found.index); prev=nxt
            nxt=found.verts[0] if found.verts[1]==prev else found.verts[1]
        if len(verts)<6: continue
        cy=sum(v.co.y for v in verts)/len(verts)
        cx=sum(v.co.x for v in verts)/len(verts)
        cz=sum(v.co.z for v in verts)/len(verts)
        rs=[math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in verts]
        rmean=sum(rs)/len(rs)
        # MUST be tip: high y AND small-moderate r (not window ~1.5+)
        if cy < tip_y - 1.0: continue
        if rmean > 0.85 or rmean < 0.12: continue
        score=cy - abs(rmean-0.5)*0.2
        if score>best:
            best=score; tip_loop=verts; meta=(cx,cy,cz,rmean,len(verts))

    if tip_loop is None:
        log("no tip loop after flat delete — skip hemisphere")
        bm.to_mesh(cut.data); cut.data.update(); bm.free()
        return {"ok": False, "reason": "no tip loop"}

    cx,cy,cz,rmean,n = meta
    R=max(min(rmean, 0.70), 0.35)
    log("tip loop", "n", n, "cy", round(cy,3), "R", round(R,3))
    ordered=sorted(tip_loop, key=lambda v: math.atan2(v.co.z-cz, v.co.x-cx))
    for v in ordered:
        ang=math.atan2(v.co.z-cz, v.co.x-cx)
        v.co.x=cx+R*math.cos(ang); v.co.z=cz+R*math.sin(ang); v.co.y=cy

    rings=[ordered]
    n_rings=6
    for ri in range(1, n_rings):
        phi=(ri/n_rings)*(math.pi*0.5)
        yy=cy+R*math.sin(phi); rr=R*math.cos(phi)
        new_ring=[]
        for v in ordered:
            ang=math.atan2(v.co.z-cz, v.co.x-cx)
            new_ring.append(bm.verts.new((cx+rr*math.cos(ang), yy, cz+rr*math.sin(ang))))
        prev=rings[-1]; nn=len(ordered)
        for i in range(nn):
            j=(i+1)%nn
            try: bm.faces.new([prev[i], prev[j], new_ring[j], new_ring[i]])
            except ValueError: pass
        rings.append(new_ring)
    tip_v=bm.verts.new((cx, cy+R, cz))
    last=rings[-1]; nn=len(last)
    for i in range(nn):
        j=(i+1)%nn
        try: bm.faces.new([last[i], last[j], tip_v])
        except ValueError: pass

    # remove orphans
    orph=[v for v in bm.verts if not v.link_faces]
    if orph:
        bmesh.ops.delete(bm, geom=orph, context="VERTS"); log("orphans", len(orph))

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    center=Vector((cx,cy,cz)); flipped=0
    for f in bm.faces:
        c=f.calc_center_median()
        if c.y>cy-0.02 and f.normal.dot(c-center)<0:
            f.normal_flip(); flipped+=1
    log("flipped", flipped, "sphere_tip", cy+R)

    bm.to_mesh(cut.data); cut.data.update()
    new_tip=max(v.co.y for v in bm.verts)
    # tip sharpness: verts within 3cm of tip
    vs=[v for v in bm.verts if v.co.y>new_tip-0.03]
    rs=[math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in vs]
    bm.free()
    return {"ok": True, "cy": cy, "R": R, "new_tip": new_tip,
            "r_mean": sum(rs)/len(rs) if rs else None,
            "r_min": min(rs) if rs else None, "r_max": max(rs) if rs else None,
            "n_tipband": len(vs)}

def hole_check(obj):
    bm=wbm(obj); bvh=BVHTree.FromBMesh(bm); out={}; open_n=0
    samples={"WS_R":Vector((0.55,17.3,1.35)),"WS_L":Vector((-0.55,17.3,1.35)),
             "SW_R":Vector((1.65,16.3,0.6)),"SW_L":Vector((-1.65,16.3,0.6)),
             "tip":Vector((0.0,19.8,0.0)),"cheek":Vector((1.5,18.5,0.2))}
    for name,p in samples.items():
        if name=="tip":
            origin=p+Vector((0,2.0,0)); direc=Vector((0,-1,0)); thresh=1.2
        else:
            radial=Vector((p.x,0,p.z)); radial.normalize()
            origin=p+radial*1.2; direc=-radial; thresh=0.85
        hit=bvh.ray_cast(origin, direc)
        if hit[0] is None: st="OPEN"
        else:
            dist=(hit[0]-origin).length
            st="SOLID" if dist<thresh else "OPEN"
        out[name]=st
        if name.startswith(("W","S")) and st=="OPEN": open_n+=1
        log("check", name, st)
    out["_open_windows"]=open_n
    tip_y=max(v.co.y for v in bm.verts)
    vs=[v for v in bm.verts if v.co.y>tip_y-0.03]
    rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    out["tip_y"]=tip_y; out["tip_r_mean"]=sum(rs)/len(rs) if rs else None
    out["tip_r_min"]=min(rs) if rs else None
    out["faces"]=len(bm.faces); out["boundary"]=sum(1 for e in bm.edges if e.is_boundary)
    bm.free(); return out

def hide_helpers(cut):
    for o in bpy.data.objects:
        if o.type!="MESH": continue
        hide=(o.name=="Nose" or o.name.startswith(("WS_","SW_","切割")) or "2-287" in o.name
              or o.name in ("CockpitFrames","WindshieldWipers","PanelLines","REF_玻璃","NoseSolid"))
        o.hide_render=hide
        try: o.hide_set(hide)
        except Exception: pass
    cut.hide_set(False); cut.hide_render=False
    for nm in ("C919_玻璃","C919_窗框","CockpitCabin","Fuselage"):
        o=bpy.data.objects.get(nm)
        if o: o.hide_set(False); o.hide_render=False

def render_views(prefix, cut):
    sc=bpy.context.scene; sc.render.engine="BLENDER_WORKBENCH"
    sc.render.resolution_x=1280; sc.render.resolution_y=720
    cam=bpy.data.objects.get("NoseFixCam")
    if not cam:
        cd=bpy.data.cameras.new("NoseFixCam"); cam=bpy.data.objects.new("NoseFixCam",cd)
        bpy.context.collection.objects.link(cam)
    sc.camera=cam; hide_helpers(cut)
    tip=Vector((0,19.9,0.55))
    for tag,eye,lens in (("front",tip+Vector((0,6,0.4)),55),("side",tip+Vector((7,-1,0.8)),50),("45",tip+Vector((4.5,4,1.5)),50)):
        cam.location=eye; cam.data.lens=lens
        cam.rotation_euler=(tip-eye).normalized().to_track_quat("-Z","Y").to_euler()
        fp=os.path.join(OUT,f"{prefix}_{tag}.png"); sc.render.filepath=fp
        bpy.ops.render.render(write_still=True); log("render", fp)

def main():
    # backup already exists from earlier; refresh if needed
    if not os.path.isfile(GLB+".bak-nose-polish"):
        shutil.copy2(GLB, GLB+".bak-nose-polish")
        shutil.copy2(BLEND, BLEND+".bak-nose-polish")

    bpy.ops.wm.open_mainfile(filepath=BLEND)
    cut=bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
    assert cut
    log("body", cut.name, "faces", len(cut.data.polygons))

    log("===== EDGES =====")
    be,nl=polish_edges(cut)
    render_views("polish_edges", cut)

    log("===== SEALS =====")
    seal_info=rebuild_glass_seals(cut)
    render_views("polish_seals", cut)

    log("===== RADOME =====")
    rad=radome_tip_only(cut)
    log("radome", rad)
    polish_edges(cut)  # light re-smooth window rims only (loops filter y)
    render_views("polish_radome", cut)

    log("===== FINAL =====")
    hide_helpers(cut)
    checks=hole_check(cut)
    render_views("polish_final", cut)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size=os.path.getsize(GLB); log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    missing=[]
    if seal_info["seal_faces"]<=0: missing.append("seals 0")
    if checks.get("_open_windows",0)<4: missing.append(f"open={checks.get('_open_windows')}")
    # tip sharpness: r_min should be ~0 (tip vert); r_mean of 3cm band can be small
    if checks.get("tip_r_min",1) and checks["tip_r_min"]>0.08:
        missing.append(f"tip r_min={checks['tip_r_min']:.3f} (want near 0)")
    if checks.get("tip")=="OPEN": missing.append("tip OPEN (hole?)")
    if size>2.5*1024*1024: missing.append("GLB>2.5MB")

    report={"glb":size,"seals":seal_info,"radome":rad,"holes":checks,"missing":missing,"be":be,"nl":nl}
    with open(os.path.join(LOG,"polish_v3_report.json"),"w",encoding="utf-8") as f:
        json.dump(report,f,indent=2,ensure_ascii=False)

    with open(NOTES,"w",encoding="utf-8") as f:
        f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `{cut.name}`

## Done
1. Hole-edge polish: dissolve <8mm boundary, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_info['seal_faces']} faces** from WS/SW outer-face boundaries (closed thin solids had 0 boundary)
   - 4cm wide, inset 2mm, BVH-projected onto skin, black Roughness 0.5
3. Glass: single-sided outer rebuild, Transmission #DDEEEB Alpha 0.3, inset 4mm
4. Radome: delete flat +Y tip-disk faces only (r<0.75), hemisphere fan from that ring (not window loops)
   - result: {json.dumps(rad, ensure_ascii=False)}
5. Helpers hidden; GLB use_visible=True

## Checks
- {json.dumps(checks, ensure_ascii=False)}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING ({len(missing)})
""" + ("\n".join("- "+m for m in missing) if missing else "- none critical") + "\n")
    log("DONE", size, "seals", seal_info["seal_faces"], "open", checks.get("_open_windows"), "missing", missing)

if __name__ == "__main__":
    main()
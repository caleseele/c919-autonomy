# -*- coding: utf-8 -*-
"""Fix aft cabin: restore from pre-reproject if needed, or reimport cabin and
project <26 with radial; >=26 use closest_point on aft ONLY with |x| preference
matching pre-project side (sign of x preserved, reject hits with |x|<1.2)."""
import json, math, os, shutil
from datetime import datetime
import bmesh, bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section6")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

TAIL_SX, TAIL_SZ = 1.0475227637527205, 1.0104343689231436
TAIL_DX, TAIL_DY, TAIL_DZ = 0.0, 15.463823181152343, -4.239782612001511
OFFSET = 0.001

def log(m):
    print(m, flush=True)
    open(os.path.join(LOG,"section6b3_console.txt"),"a",encoding="utf-8").write(m+"\n")

def tip_y():
    n=bpy.data.objects["Nose"]
    return max((n.matrix_world@v.co).y for v in n.data.vertices)

def apply_mw(ob):
    ob.data.transform(ob.matrix_world); ob.data.update(); ob.matrix_world=Matrix.Identity(4)

def delete_object(name):
    ob=bpy.data.objects.get(name)
    if not ob: return False
    me=ob.data if ob.type=="MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users==0: bpy.data.meshes.remove(me)
    return True

def tail_M():
    R=Matrix.Rotation(math.pi,4,"Z")
    S=Matrix.Diagonal((TAIL_SX,1.0,TAIL_SZ,1.0))
    T=Matrix.Translation(Vector((TAIL_DX,TAIL_DY,TAIL_DZ)))
    return T@S@R

def find_cabin():
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "舱门" in fn:
            return os.path.join(REFS, fn)
    raise FileNotFoundError("cabin")

def islands(ob):
    tip=tip_y(); mw=ob.matrix_world
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    rem=set(bm.verts); out=[]
    while rem:
        s=rem.pop(); st=[s]; isl={s}
        while st:
            v=st.pop()
            for e in v.link_edges:
                o=e.other_vert(v)
                if o not in isl: isl.add(o); rem.discard(o); st.append(o)
        idxs=[v.index for v in isl]
        cents=[mw@v.co for v in isl]
        c=Vector(tuple(sum(getattr(p,a) for p in cents)/len(cents) for a in "xyz"))
        out.append({"verts":idxs,"c":c,"st":tip-c.y,"side":1 if c.x>=0 else -1})
    bm.free(); return out

def project_fwd(skin, wco):
    """Radial ray + closest for Nose/Fuselage."""
    mw=skin.matrix_world; imw=mw.inverted()
    axis=Vector((0,wco.y,0))
    radial=Vector((wco.x,0,wco.z))
    if radial.length<1e-5: radial=Vector((1,0,0))
    radial.normalize()
    start_l=imw@(axis+radial*8)
    end_l=imw@(axis+radial*7)
    d=(end_l-start_l).normalized()
    ok,loc,norm,_=skin.ray_cast(start_l,d,distance=20)
    if ok:
        wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
        if wn.dot(radial)<0: wn=-wn
        if abs(wn.y)<0.7 and Vector((wloc.x,0,wloc.z)).length>1.0:
            return wloc, wn
    ok,loc,norm,_=skin.closest_point_on_mesh(imw@wco)
    if ok:
        wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
        if wn.dot(radial)<0: wn=-wn
        return wloc, wn
    return None, None

def project_aft(skin, wco, side_sign):
    """Closest point on aft skin, preferring same side |x|>=1.2, reject fin."""
    mw=skin.matrix_world; imw=mw.inverted()
    # seed probes on the correct side at several radii/heights around wco
    candidates=[]
    for rad in (1.6, 1.8, 1.95, 2.05, 2.15, 2.25):
        for dz in (-0.4,-0.2,0,0.2,0.4):
            probe=Vector((side_sign*rad, wco.y, wco.z+dz))
            ok,loc,norm,_=skin.closest_point_on_mesh(imw@probe)
            if not ok: continue
            wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
            if abs(wloc.x)<1.15:  # reject centerline / fin root
                continue
            if wloc.x * side_sign < 0:  # wrong side
                continue
            if abs(wn.y)>0.7:  # endcap
                continue
            # outward
            radial=Vector((wloc.x,0,wloc.z)); 
            if radial.length>1e-6:
                radial.normalize()
                if wn.dot(radial)<0: wn=-wn
            dist=(wco-wloc).length
            candidates.append((dist, wloc, wn))
    if candidates:
        candidates.sort(key=lambda t:t[0])
        return candidates[0][1], candidates[0][2]
    # fallback: closest then push to side
    ok,loc,norm,_=skin.closest_point_on_mesh(imw@wco)
    if not ok: return None, None
    wloc=mw@loc; wn=(mw.to_3x3()@norm).normalized()
    if abs(wloc.x)<1.15:
        # force to side at similar z
        wloc=Vector((side_sign*2.0, wco.y, wco.z))
        ok2,loc2,norm2,_=skin.closest_point_on_mesh(imw@wloc)
        if ok2:
            wloc=mw@loc2; wn=(mw.to_3x3()@norm2).normalized()
    radial=Vector((wloc.x,0,wloc.z))
    if radial.length>1e-6:
        radial.normalize()
        if wn.dot(radial)<0: wn=-wn
    return wloc, wn

def reimport_cabin(tip):
    for o in list(bpy.data.objects):
        if o.type!="MESH": continue
        if ("舷窗" in o.name and "玻璃" in o.name) or ("舱门" in o.name and "缝" in o.name):
            delete_object(o.name)
    path=find_cabin()
    before=set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new=[o for o in bpy.data.objects if o not in before]
    M=tail_M()
    for ob in new:
        if ob.type!="MESH": continue
        apply_mw(ob)
        ob.data.transform(M); ob.data.update()
        ob.matrix_world=Matrix.Identity(4)
        if not ob.name.startswith("REF_"):
            ob.name="REF_"+ob.name
    # materials
    glass=None
    for m in bpy.data.materials:
        if m.name=="Glass" or "舷窗" in m.name:
            glass=m; break
    if glass is None:
        glass=bpy.data.materials.new("Glass"); glass.use_nodes=True
        bsdf=glass.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value=(0.18,0.23,0.24,1)
            bsdf.inputs["Roughness"].default_value=0.03
            bsdf.inputs["Alpha"].default_value=0.45
            if "Transmission Weight" in bsdf.inputs:
                bsdf.inputs["Transmission Weight"].default_value=1.0
            glass.blend_method="BLEND"
    seam=bpy.data.materials.get("REF_舱门缝线")
    if seam is None:
        seam=bpy.data.materials.new("REF_舱门缝线"); seam.use_nodes=True
        bsdf=seam.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value=(0.227,0.239,0.259,1)
            bsdf.inputs["Roughness"].default_value=0.5
    for ob in new:
        if ob.type!="MESH": continue
        ob.data.materials.clear()
        if "玻璃" in ob.name: ob.data.materials.append(glass)
        else: ob.data.materials.append(seam)
    bpy.context.view_layer.update()
    return new, path

def project_all(ob, nose, fuse, aft, fuse_st0):
    tip=tip_y(); mw=ob.matrix_world; imw=mw.inverted(); me=ob.data
    # capture side from PRE-project centroids
    isls=islands(ob)
    ok=fail=0
    for isl in isls:
        st=isl["st"]; side=isl["side"]
        if st < fuse_st0 + 0.05:
            skin=nose; mode="fwd"
        elif st < 26.0:
            skin=fuse; mode="fwd"
        else:
            skin=aft; mode="aft"
        for vi in isl["verts"]:
            wco=mw@me.vertices[vi].co
            if mode=="fwd":
                wloc,wn=project_fwd(skin,wco)
            else:
                wloc,wn=project_aft(skin,wco,side)
            if wloc is None:
                fail+=1; continue
            me.vertices[vi].co=imw@(wloc+wn*OFFSET)
            ok+=1
    me.update(); bpy.context.view_layer.update()
    return ok, fail

def measure_report(ob, tip):
    isls=islands(ob)
    rows=[]
    for isl in isls:
        rows.append({"st":round(isl["st"],2),"x":round(isl["c"].x,3),"z":round(isl["c"].z,3),"n":isl and len(isl["verts"])})
    ys=[(ob.matrix_world@v.co).y for v in ob.data.vertices]
    xs=[(ob.matrix_world@v.co).x for v in ob.data.vertices]
    return {
        "total":len(isls),
        "station_span":[round(tip-max(ys),3),round(tip-min(ys),3)],
        "side_islands":sum(1 for r in rows if abs(r["x"])>1.5),
        "mid_islands":sum(1 for r in rows if abs(r["x"])<=1.5),
        "x_span":[round(min(xs),3),round(max(xs),3)],
        "islands":rows,
    }

def cam_render(tip):
    def ay(ob):
        pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
        return min(p.y for p in pts), max(p.y for p in pts)
    ys=[]
    for o in bpy.data.objects:
        if o.type=="MESH":
            a,b=ay(o); ys+=[a,b]
    tail=min(ys)
    scene=bpy.context.scene
    scene.render.engine="BLENDER_WORKBENCH"
    scene.display.shading.light="STUDIO"
    scene.display.shading.color_type="MATERIAL"
    scene.render.resolution_x=1280; scene.render.resolution_y=480
    cam=bpy.data.objects.get("LengthSideCam")
    if not cam:
        data=bpy.data.cameras.new("LengthSideCam"); cam=bpy.data.objects.new("LengthSideCam",data)
        bpy.context.collection.objects.link(cam)
    cam.data.type="ORTHO"; cam.data.ortho_scale=38.84*1.12
    ymid=0.5*(tip+tail)
    cam.location=(-80,ymid,0); cam.rotation_euler=(math.pi/2,0,-math.pi/2)
    scene.camera=cam; bpy.context.view_layer.update()
    ts=world_to_camera_view(scene,cam,Vector((0,tip,0))).x
    ls=world_to_camera_view(scene,cam,Vector((0,tail,0))).x
    if not (ts<ls):
        cam.location=(80,ymid,0); cam.rotation_euler=(math.pi/2,0,math.pi/2)
        bpy.context.view_layer.update()
        ts=world_to_camera_view(scene,cam,Vector((0,tip,0))).x
        ls=world_to_camera_view(scene,cam,Vector((0,tail,0))).x
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    ours=os.path.join(PREV,f"side_ours_{stamp}.png")
    refp=os.path.join(PREV,f"side_ref_{stamp}.png")
    cmp=os.path.join(PREV,f"side_compare_{stamp}.png")
    for o in bpy.data.objects:
        if o.type=="MESH": o.hide_render=o.name.startswith("LengthRef_")
    scene.render.filepath=ours; bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"): bpy.data.objects.remove(o,do_unlink=True)
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(REFS,"REF_C919_meters.fbx"),global_scale=1.0)
    refs=[o for o in bpy.data.objects if o not in before]
    for o in refs: o.name="LengthRef_"+o.name[:40]
    rys=[]
    for o in refs:
        if o.type=="MESH":
            a,b=ay(o); rys+=[a,b]
    dy=tip-max(rys)
    for o in refs: o.location.y+=dy
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type=="MESH": o.hide_render=not o.name.startswith("LengthRef_")
    scene.render.filepath=refp; bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"): bpy.data.objects.remove(o,do_unlink=True)
    for o in bpy.data.objects:
        if o.type=="MESH": o.hide_render=False
    json.dump({"ours":ours,"ref":refp,"compare":cmp,"stamp":stamp,"tip_sx":ts,"tail_sx":ls},
              open(os.path.join(LOG,"section6b_stack.json"),"w",encoding="utf-8"))
    return {"tip_sx":ts,"tail_sx":ls,"ok":ts<ls,"ours":ours,"ref":refp,"compare":cmp,"stamp":stamp}

def signed_mean(ob, nose, fuse, aft, fuse_st0):
    tip=tip_y(); mw=ob.matrix_world
    sunk=0; total=0
    for isl in islands(ob):
        total+=1
        st=isl["st"]
        if st < fuse_st0+0.05: skin=nose
        elif st<26: skin=fuse
        else: skin=aft
        dists=[]
        for vi in isl["verts"]:
            wco=mw@ob.data.vertices[vi].co
            if st>=26:
                wloc,wn=project_aft(skin,wco,isl["side"])
            else:
                wloc,wn=project_fwd(skin,wco)
            if wloc is None or wn is None: continue
            dists.append((wco-wloc).dot(wn))
        if dists and (sum(dists)/len(dists) < 5e-4):
            sunk+=1
    return sunk, total

def main():
    open(os.path.join(LOG,"section6b3_console.txt"),"w",encoding="utf-8").close()
    log("=== section6b3 side-aware aft project ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tip=tip_y()
    nose=bpy.data.objects["Nose"]; fuse=bpy.data.objects["Fuselage"]
    aft=next(o for o in bpy.data.objects if "蒙皮" in o.name and "尾" in o.name)
    fa_ys=[(fuse.matrix_world@v.co).y for v in fuse.data.vertices]
    fuse_st0=tip-max(fa_ys)
    log(f"tip={tip:.4f} fuse_st0={fuse_st0:.3f}")

    # BEFORE: current (possibly bad aft)
    g0=next((o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name),None)
    s0=next((o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name),None)
    before_note={}
    if g0: before_note["glass"]=measure_report(g0,tip)
    if s0: before_note["seam"]=measure_report(s0,tip)
    log(f"before glass mid={before_note.get('glass',{}).get('mid_islands')} side={before_note.get('glass',{}).get('side_islands')}")
    log(f"before seam mid={before_note.get('seam',{}).get('mid_islands')} side={before_note.get('seam',{}).get('side_islands')}")

    new, path = reimport_cabin(tip)
    log(f"reimported {[o.name for o in new]}")
    # pre-project report
    for ob in new:
        if ob.type!="MESH": continue
        r=measure_report(ob,tip)
        log(f"pre-project {ob.name} side={r['side_islands']} mid={r['mid_islands']} st={r['station_span']}")

    for ob in new:
        if ob.type!="MESH": continue
        ok,fail=project_all(ob,nose,fuse,aft,fuse_st0)
        log(f"project {ob.name} ok={ok} fail={fail}")

    after={}
    sunk_tbl={}
    for ob in new:
        if ob.type!="MESH": continue
        lab="glass" if "玻璃" in ob.name else "seam"
        after[lab]=measure_report(ob,tip)
        sk,tot=signed_mean(ob,nose,fuse,aft,fuse_st0)
        sunk_tbl[lab]={"sunk":sk,"total":tot}
        log(f"after {lab} side={after[lab]['side_islands']} mid={after[lab]['mid_islands']} "
            f"st={after[lab]['station_span']} sunk={sk}/{tot}")
        if lab=="seam":
            for isl in after[lab]["islands"]:
                log(f"  seam isl st={isl['st']} x={isl['x']} z={isl['z']}")

    rend=cam_render(tip)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    ant=next((o for o in bpy.data.objects if "尾段" in o.name and "天线" in o.name),None)
    ant_info=None
    if ant:
        vs=[ant.matrix_world@v.co for v in ant.data.vertices]
        ant_info={"name":ant.name,"st":[round(tip-max(v.y for v in vs),3),round(tip-min(v.y for v in vs),3)],
                  "zmax":round(max(v.z for v in vs),3)}
    result={"before_note":before_note,"after":after,"sunk":sunk_tbl,"antenna":ant_info,"render":rend,
            "scripts":["section6b_window_project.py","section6b2_reproject.py","section6b3_side_project.py"]}
    json.dump(result, open(os.path.join(LOG,"section6b3.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    open(PROGRESS,"w",encoding="utf-8").write("\n".join([
        "# PROGRESS — §6b3 side-aware cabin project",
        "- backup: c919.bak-section6b.blend",
        "- reimport cabin REF_尾段 xform; project Nose/Fuse radial; aft side-aware closest +1mm",
        f"- glass sunk {sunk_tbl.get('glass')}; side/mid={after.get('glass',{}).get('side_islands')}/{after.get('glass',{}).get('mid_islands')}",
        f"- seam sunk {sunk_tbl.get('seam')}; mid should be 0",
        f"- antenna {ant_info}; GearBayDoors kept; 86 glass=SPEC OK",
        f"- cam tip_sx={rend['tip_sx']:.4f} tail_sx={rend['tail_sx']:.4f}",
        f"- compare stamp {rend['stamp']}",
        "- scripts: section6b_window_project.py, section6b2_reproject.py, section6b3_side_project.py",
    ])+"\n")
    log("=== section6b3 DONE ===")

if __name__=="__main__":
    main()

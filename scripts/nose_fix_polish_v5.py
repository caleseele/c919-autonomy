# -*- coding: utf-8 -*-
"""Final polish: edges + seals + centerline hemisphere map."""
from __future__ import annotations
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

v3path = os.path.join(PROJ, "scripts", "nose_fix_polish_v3.py")
src = open(v3path, encoding="utf-8").read()
src = src.replace('if __name__ == "__main__":\n    main()\n', "")
src = src.replace("def main():", "def _unused_main():")
ns = {"__name__": "helpers", "__file__": v3path}
exec(compile(src, v3path, "exec"), ns)
polish_edges = ns["polish_edges"]
rebuild_glass_seals = ns["rebuild_glass_seals"]
hide_helpers = ns["hide_helpers"]
render_views = ns["render_views"]
wbm = ns["wbm"]

def log(*a):
    print("POLISHv5", *a, flush=True)

def radome_centerline(cut):
    """Sphere-map tip using aircraft centerline cx=cz=0. Strict forward faces only."""
    bm = bmesh.new(); bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
    tip_y = max(v.co.y for v in bm.verts)
    CX, CZ = 0.0, 0.0

    # Strict flat tip: ny>0.8, r<0.55, near tip
    flat = []
    for f in bm.faces:
        c = f.calc_center_median(); n = f.normal.normalized()
        r = math.sqrt(c.x**2 + c.z**2)
        if c.y < tip_y - 0.35: continue
        if r > 0.55: continue
        if n.y < 0.80: continue
        flat.append(f)
    if len(flat) < 8:
        flat = []
        for f in bm.faces:
            c = f.calc_center_median(); n = f.normal.normalized()
            r = math.sqrt(c.x**2 + c.z**2)
            if c.y < tip_y - 0.45: continue
            if r > 0.65: continue
            if n.y < 0.65: continue
            flat.append(f)
    flat = list({f.index: f for f in flat}.values())
    log("flat", len(flat), "tip_y", tip_y)

    tip_verts = set()
    for f in flat:
        for v in f.verts: tip_verts.add(v)
    # add nearby verts strictly in tip cylinder
    for v in bm.verts:
        r = math.sqrt(v.co.x**2 + v.co.z**2)
        if v.co.y > tip_y - 0.40 and r < 0.55:
            tip_verts.add(v)

    if len(tip_verts) < 8:
        bm.free(); return {"ok": False}

    # Equator y = mean y of verts with r in [0.35, 0.55]
    rim = [v for v in tip_verts if 0.30 <= math.sqrt(v.co.x**2+v.co.z**2) <= 0.55]
    if len(rim) < 6:
        rim = sorted(tip_verts, key=lambda v: -math.sqrt(v.co.x**2+v.co.z**2))[:max(12, len(tip_verts)//3)]
    cy = sum(v.co.y for v in rim) / len(rim)
    R = sum(math.sqrt(v.co.x**2+v.co.z**2) for v in rim) / len(rim)
    R = max(min(R, 0.60), 0.35)
    log("cy", round(cy,3), "R", round(R,3), "nverts", len(tip_verts), "nrim", len(rim))

    for v in tip_verts:
        dx, dz = v.co.x - CX, v.co.z - CZ
        r = math.sqrt(dx*dx + dz*dz)
        if r > R and r > 1e-9:
            s = R / r
            v.co.x = CX + dx * s
            v.co.z = CZ + dz * s
            r = R
        r_clamped = min(r, R * 0.999999)
        v.co.y = cy + math.sqrt(max(0.0, R*R - r_clamped*r_clamped))

    # Poke central-most flat face and put tip on centerline
    best, bestd = None, 1e9
    for f in flat:
        if not f.is_valid: continue
        c = f.calc_center_median()
        d = c.x**2 + c.z**2
        if d < bestd: bestd = d; best = f
    tip_co = Vector((CX, cy + R, CZ))
    if best is not None and best.is_valid:
        ret = bmesh.ops.poke(bm, faces=[best])
        for v in ret.get("verts", []):
            v.co = tip_co.copy()
            log("poke tip", tuple(round(x,4) for x in v.co))
    else:
        # snap nearest vert to tip
        v0 = min(tip_verts, key=lambda v: v.co.x**2 + v.co.z**2)
        v0.co = tip_co.copy()
        log("snap tip", tuple(round(x,4) for x in v0.co))

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # flip tip faces if inward
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y > cy and math.sqrt(c.x**2+c.z**2) < R*1.1:
            if f.normal.dot(c - Vector((CX, cy, CZ))) < 0:
                f.normal_flip()

    bm.to_mesh(cut.data); cut.data.update()
    new_tip = max(v.co.y for v in bm.verts)
    vs = [v for v in bm.verts if v.co.y > new_tip - 0.03]
    rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    axis = [v for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>cy]
    bvh = BVHTree.FromBMesh(bm)
    hit = bvh.ray_cast(Vector((0, new_tip+0.5, 0)), Vector((0,-1,0)))
    dist = (hit[0]-Vector((0,new_tip+0.5,0))).length if hit[0] else None
    bm.free()
    return {
        "ok": True, "cy": cy, "R": R, "new_tip": new_tip,
        "r_min": min(rs) if rs else None, "r_mean": sum(rs)/len(rs) if rs else None,
        "axis_n": len(axis), "ray_dist": dist,
        "tip_solid": (dist is not None and dist < 0.85),
    }

def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    cut = bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
    assert cut
    log("body", cut.name, len(cut.data.polygons))

    log("===== EDGES =====")
    polish_edges(cut)
    render_views("polish_edges", cut)

    log("===== SEALS =====")
    seal_info = rebuild_glass_seals(cut)
    render_views("polish_seals", cut)

    log("===== RADOME =====")
    rad = radome_centerline(cut)
    log("radome", rad)
    render_views("polish_radome", cut)

    # verify after render (mesh should be unchanged)
    bm = wbm(cut); tip_y = max(v.co.y for v in bm.verts)
    vs = [v for v in bm.verts if v.co.y > tip_y - 0.03]
    rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    axis = sorted([(round(v.co.x,4),round(v.co.y,4),round(v.co.z,4))
                   for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5],
                  key=lambda t:-t[1])[:5]
    bvh = BVHTree.FromBMesh(bm)
    hit = bvh.ray_cast(Vector((0, tip_y+0.5, 0)), Vector((0,-1,0)))
    tip_status = "OPEN" if hit[0] is None else (
        "SOLID" if (hit[0]-Vector((0,tip_y+0.5,0))).length < 0.85
        else f"OPEN dist={(hit[0]-Vector((0,tip_y+0.5,0))).length:.2f}")
    open_n = 0
    for name,p in [("WS_R",Vector((0.55,17.3,1.35)),),("WS_L",Vector((-0.55,17.3,1.35)),),
                   ("SW_R",Vector((1.65,16.3,0.6)),),("SW_L",Vector((-1.65,16.3,0.6)),)]:
        p=p[0]
        radial=Vector((p.x,0,p.z)); radial.normalize()
        h=bvh.ray_cast(p+radial*1.2,-radial)
        st="OPEN" if (h[0] is None or (h[0]-(p+radial*1.2)).length>=0.85) else "SOLID"
        if st=="OPEN": open_n+=1
        log("check", name, st)
    be = sum(1 for e in bm.edges if e.is_boundary)
    sil=[]
    for y in [19.6,19.8,20.0,20.1,20.2,20.3]:
        ring=[v for v in bm.verts if abs(v.co.y-y)<0.025]
        if not ring: sil.append({"y":y,"empty":True}); continue
        rr=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
        sil.append({"y":y,"r_mean":round(sum(rr)/len(rr),3),"r_min":round(min(rr),3),"n":len(ring)})
    bm.free()
    log("verify tip", tip_status, "r_min", min(rs) if rs else None, "axis", axis, "sil", sil)

    hide_helpers(cut)
    render_views("polish_final", cut)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size=os.path.getsize(GLB); log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    missing=[]
    if seal_info["seal_faces"]<=0: missing.append("seals 0")
    if open_n<4: missing.append(f"open={open_n}")
    if (min(rs) if rs else 1) > 0.08: missing.append(f"tip r_min={min(rs):.3f}")
    if tip_status != "SOLID": missing.append(f"tip {tip_status}")

    with open(os.path.join(LOG,"polish_v5_report.json"),"w",encoding="utf-8") as f:
        json.dump({"glb":size,"seals":seal_info,"radome":rad,"tip_status":tip_status,
                   "r_min":min(rs) if rs else None,"r_mean":sum(rs)/len(rs) if rs else None,
                   "axis":axis,"sil":sil,"open":open_n,"boundary":be,"missing":missing}, f, indent=2, ensure_ascii=False)

    with open(NOTES,"w",encoding="utf-8") as f:
        f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_info['seal_faces']} faces** from WS/SW outer-face boundaries
   - 4 cm, inset 2 mm, BVH snap, black Roughness 0.5
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: centerline sphere-map (cx=cz=0) + poke tip vert on axis
   - {json.dumps(rad, ensure_ascii=False)}
5. Helpers hidden; GLB use_visible=True

## Checks
- windows OPEN: {open_n}/4
- tip_axis: {tip_status}; tip_y={tip_y:.3f}; r_min={min(rs) if rs else None}; r_mean={sum(rs)/len(rs) if rs else None}
- near_axis: {axis}
- sil: {sil}
- boundary: {be}
- seal={seal_info['seal_faces']} glass={seal_info['glass_faces']}
- GLB: {size} bytes ({size/1024/1024:.2f} MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## Honesty / MISSING ({len(missing)})
""" + ("\n".join("- "+m for m in missing) if missing else "- none critical") + """

Notes: OBB boolean holes still leave some faceting on window rims; seals follow pane outlines (may not perfectly match jagged hole). Radome R≈0.35–0.60m sphere-map from flat disk — better arc than flat plate, not CAD-perfect.
""")
    log("DONE", size, "seals", seal_info["seal_faces"], "open", open_n, "missing", missing)

if __name__ == "__main__":
    main()
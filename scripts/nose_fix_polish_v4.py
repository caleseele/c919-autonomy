# -*- coding: utf-8 -*-
"""Polish v4: edges+seals from v3 helpers, sphere-map radome (no delete)."""
from __future__ import annotations
import json, math, os, shutil, runpy
from collections import defaultdict
import bmesh, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
BAK = BLEND + ".bak-nose-polish"
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
OUT = os.path.join(PROJ, "public", "models", "nose-fix")
LOG = os.path.join(PROJ, "scripts", "_nose_fix_logs")
NOTES = os.path.join(PROJ, "scripts", "NOSE_POLISH_PASS_NOTES.zh-Hans.md")

shutil.copy2(BAK, BLEND)
shutil.copy2(GLB + ".bak-nose-polish", GLB)

# Load v3 as module-like dict without running main
v3path = os.path.join(PROJ, "scripts", "nose_fix_polish_v3.py")
src = open(v3path, encoding="utf-8").read()
src = src.replace('if __name__ == "__main__":\n    main()\n', "")
src = src.replace("def main():", "def _v3_main_unused():")
ns = {"__name__": "nose_fix_polish_v3_helpers", "__file__": v3path}
exec(compile(src, v3path, "exec"), ns)

polish_edges = ns["polish_edges"]
rebuild_glass_seals = ns["rebuild_glass_seals"]
hide_helpers = ns["hide_helpers"]
render_views = ns["render_views"]
hole_check = ns["hole_check"]
wbm = ns["wbm"]

def log(*a):
    print("POLISHv4", *a, flush=True)

def radome_sphere_map(cut):
    bm = bmesh.new(); bm.from_mesh(cut.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
    tip_y = max(v.co.y for v in bm.verts)

    flat = []
    for f in bm.faces:
        c = f.calc_center_median(); n = f.normal.normalized()
        r = math.sqrt(c.x**2 + c.z**2)
        if c.y < tip_y - 0.45: continue
        if r > 0.70: continue
        if n.y < 0.70: continue
        flat.append(f)
    if len(flat) < 5:
        flat = []
        for f in bm.faces:
            c = f.calc_center_median(); n = f.normal.normalized()
            r = math.sqrt(c.x**2 + c.z**2)
            if c.y < tip_y - 0.55: continue
            if r > 0.80: continue
            if n.y < 0.50: continue
            flat.append(f)
    flat = list({f.index: f for f in flat}.values())
    log("flat faces", len(flat))

    tip_verts = set()
    for f in flat:
        for v in f.verts: tip_verts.add(v)
    for v in bm.verts:
        r = math.sqrt(v.co.x**2 + v.co.z**2)
        if v.co.y > tip_y - 0.50 and r < 0.70:
            tip_verts.add(v)

    rs = [(v, math.sqrt(v.co.x**2 + v.co.z**2)) for v in tip_verts]
    rs.sort(key=lambda t: -t[1])
    rmax = rs[0][1]
    rim = [v for v, r in rs if r >= rmax * 0.82]
    if len(rim) < 6:
        rim = [v for v, r in rs[:max(8, len(rs)//4)]]
    cx = sum(v.co.x for v in rim) / len(rim)
    cz = sum(v.co.z for v in rim) / len(rim)
    cy = sum(v.co.y for v in rim) / len(rim)
    R = sum(math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in rim) / len(rim)
    R = max(min(R, 0.75), 0.30)
    log("sphere cy", round(cy,3), "R", round(R,3), "rim", len(rim), "nverts", len(tip_verts))

    moved = 0
    for v in tip_verts:
        dx, dz = v.co.x - cx, v.co.z - cz
        r = math.sqrt(dx*dx + dz*dz)
        if r > R * 1.02 and r > 1e-9:
            s = R / r
            v.co.x = cx + dx * s
            v.co.z = cz + dz * s
            r = R
        r_clamped = min(r, R * 0.999999)
        v.co.y = cy + math.sqrt(max(0.0, R*R - r_clamped*r_clamped))
        moved += 1

    # ensure tip on axis
    axis_verts = [v for v in tip_verts if v.is_valid and math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) < 0.10]
    if axis_verts:
        v0 = min(axis_verts, key=lambda v: (v.co.x-cx)**2+(v.co.z-cz)**2)
        v0.co = Vector((cx, cy + R, cz))
        log("snapped tip")
    elif flat:
        ret = bmesh.ops.poke(bm, faces=[flat[0]])
        for v in ret.get("verts", []):
            v.co = Vector((cx, cy + R, cz))
            tip_verts.add(v)
            log("poked tip")

    for _ in range(4):
        for v in list(tip_verts):
            if not v.is_valid or not v.link_edges: continue
            acc = Vector(); cnt = 0
            for e in v.link_edges:
                ov = e.other_vert(v)
                if ov in tip_verts:
                    acc += ov.co; cnt += 1
            if cnt < 2: continue
            mid = acc / cnt
            dx, dz = mid.x - cx, mid.z - cz
            r = math.sqrt(dx*dx + dz*dz)
            r_clamped = min(r, R * 0.999999)
            target = Vector((mid.x, cy + math.sqrt(max(0.0, R*R - r_clamped*r_clamped)), mid.z))
            v.co = v.co.lerp(target, 0.4)

    # re-snap tip after smooth
    axis_verts = [v for v in tip_verts if v.is_valid and math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) < 0.12]
    if axis_verts:
        v0 = min(axis_verts, key=lambda v: (v.co.x-cx)**2+(v.co.z-cz)**2)
        v0.co = Vector((cx, cy + R, cz))

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cut.data); cut.data.update()
    new_tip = max(v.co.y for v in bm.verts)
    vs = [v for v in bm.verts if v.co.y > new_tip - 0.03]
    rrs = [math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in vs]
    axis_n = sum(1 for v in bm.verts if math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2)<0.05 and v.co.y>cy)
    bm.free()
    return {"ok": True, "cy": cy, "R": R, "moved": moved, "new_tip": new_tip,
            "r_mean": sum(rrs)/len(rrs) if rrs else None,
            "r_min": min(rrs) if rrs else None, "axis_n": axis_n}

def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    cut = bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
    assert cut
    log("body", cut.name, len(cut.data.polygons))

    log("===== EDGES =====")
    be, nl = polish_edges(cut)
    # patch log prefix inside polish — still prints POLISHv3; ok
    render_views("polish_edges", cut)

    log("===== SEALS =====")
    seal_info = rebuild_glass_seals(cut)
    render_views("polish_seals", cut)

    log("===== RADOME =====")
    rad = radome_sphere_map(cut)
    log("radome", rad)
    render_views("polish_radome", cut)

    log("===== FINAL =====")
    hide_helpers(cut)
    checks = hole_check(cut)
    bm = wbm(cut); bvh = BVHTree.FromBMesh(bm)
    tip_y = max(v.co.y for v in bm.verts)
    hit = bvh.ray_cast(Vector((0, tip_y + 0.5, 0)), Vector((0, -1, 0)))
    if hit[0] is None:
        tip_status = "OPEN"
    else:
        dist = (hit[0] - Vector((0, tip_y + 0.5, 0)).length if False else (hit[0]-Vector((0, tip_y+0.5,0))).length)
        tip_status = "SOLID" if dist < 0.85 else f"OPEN dist={dist:.2f}"
    vs = [v for v in bm.verts if v.co.y > tip_y - 0.03]
    rs = [math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    checks["tip_axis"] = tip_status
    checks["tip_y"] = tip_y
    checks["tip_r_min"] = min(rs) if rs else None
    checks["tip_r_mean"] = sum(rs)/len(rs) if rs else None
    checks["near_axis"] = sorted(
        [(round(v.co.x,3), round(v.co.y,3), round(v.co.z,3))
         for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.06 and v.co.y>19.5],
        key=lambda t: -t[1])[:8]
    sil=[]
    for y in [19.6,19.8,20.0,20.2,20.4]:
        ring=[v for v in bm.verts if abs(v.co.y-y)<0.03]
        if not ring: sil.append({"y":y,"empty":True}); continue
        rr=[math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
        sil.append({"y":y,"r_mean":round(sum(rr)/len(rr),3),"r_min":round(min(rr),3),"n":len(ring)})
    checks["sil"]=sil
    checks["boundary"]=sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    log("tip_axis", tip_status, "r_min", checks["tip_r_min"], "near_axis", checks["near_axis"][:3], "sil", sil)
    render_views("polish_final", cut)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size=os.path.getsize(GLB); log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    missing=[]
    if seal_info["seal_faces"]<=0: missing.append("seals 0")
    if checks.get("_open_windows",0)<4: missing.append(f"open={checks.get('_open_windows')}")
    if (checks.get("tip_r_min") or 1) > 0.08: missing.append(f"tip r_min={checks['tip_r_min']:.3f}")
    if not tip_status.startswith("SOLID"): missing.append(f"tip {tip_status}")

    with open(os.path.join(LOG,"polish_v4_report.json"),"w",encoding="utf-8") as f:
        json.dump({"glb":size,"seals":seal_info,"radome":rad,"holes":checks,"missing":missing}, f, indent=2, ensure_ascii=False)

    with open(NOTES,"w",encoding="utf-8") as f:
        f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_info['seal_faces']} faces** from WS/SW outer-face boundaries (closed panes had 0 boundary)
   - 4 cm, inset 2 mm, BVH snap, black Roughness 0.5
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: sphere-map flat tip disk → hemisphere (no face delete)
   - {json.dumps(rad, ensure_ascii=False)}
5. Helpers hidden; GLB use_visible=True

## Checks
- windows OPEN: {checks.get('_open_windows')}/4
- tip_axis: {tip_status}; tip_y={tip_y:.3f}; r_min={checks['tip_r_min']}; r_mean={checks['tip_r_mean']}
- near_axis: {checks['near_axis']}
- sil: {sil}
- boundary: {checks['boundary']}
- seal={seal_info['seal_faces']} glass={seal_info['glass_faces']}
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
# -*- coding: utf-8 -*-
"""Re-apply tip-only radome on current polished blend; no edge re-polish."""
from __future__ import annotations
import json, math, os
import bmesh, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
# Use bak + re-do seals/edges/radome cleanly: restore bak then run without 2nd edge polish
BAK = BLEND + ".bak-nose-polish"
WORK = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
OUT = os.path.join(PROJ, "public", "models", "nose-fix")
NOTES = os.path.join(PROJ, "scripts", "NOSE_POLISH_PASS_NOTES.zh-Hans.md")
LOG = os.path.join(PROJ, "scripts", "_nose_fix_logs")

# Import polish helpers by exec of v3 functions — simpler: inline copy of needed parts
# Actually: restore bak, call nose_fix_polish_v3 but we need patched version.
# Fast path: restore bak, run patched pipeline inline.

import shutil
shutil.copy2(BAK, BLEND)
shutil.copy2(GLB + ".bak-nose-polish", GLB)

# Patch: run v3 main logic by importing after editing — just exec the v3 file with a monkeypatch.
# Easiest: duplicate radome+seals+edges from v3 without second polish_edges.

exec(open(os.path.join(PROJ, "scripts", "nose_fix_polish_v3.py"), encoding="utf-8").read().split("def main():")[0])

def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    cut = bpy.data.objects.get("Nose_开窗") or bpy.data.objects.get("Nose")
    assert cut
    log("body", cut.name, len(cut.data.polygons))

    log("===== EDGES =====")
    be, nl = polish_edges(cut)
    render_views("polish_edges", cut)

    log("===== SEALS =====")
    seal_info = rebuild_glass_seals(cut)
    render_views("polish_seals", cut)

    log("===== RADOME (no re-edge) =====")
    rad = radome_tip_only(cut)
    log("radome", rad)
    render_views("polish_radome", cut)

    log("===== FINAL =====")
    hide_helpers(cut)
    checks = hole_check(cut)
    # honest tip solidity: ray from tip_y+0.5
    bm = wbm(cut); bvh = BVHTree.FromBMesh(bm)
    tip_y = max(v.co.y for v in bm.verts)
    hit = bvh.ray_cast(Vector((0, tip_y + 0.5, 0)), Vector((0, -1, 0)))
    if hit[0] is None:
        tip_status = "OPEN"
    else:
        dist = (hit[0] - Vector((0, tip_y + 0.5, 0))).length
        tip_status = "SOLID" if dist < 0.85 else f"OPEN dist={dist:.2f}"
    checks["tip_axis"] = tip_status
    checks["tip_y_true"] = tip_y
    vs = [v for v in bm.verts if v.co.y > tip_y - 0.03]
    rs = [math.sqrt(v.co.x**2 + v.co.z**2) for v in vs]
    checks["tip_r_mean"] = sum(rs)/len(rs) if rs else None
    checks["tip_r_min"] = min(rs) if rs else None
    checks["tip_r_max"] = max(rs) if rs else None
    # silhouette
    sil = []
    for y in [19.5, 19.7, 19.9, 20.0, 20.1, 20.2, 20.3, 20.4]:
        ring = [v for v in bm.verts if abs(v.co.y - y) < 0.03]
        if not ring:
            sil.append({"y": y, "empty": True}); continue
        rr = [math.sqrt(v.co.x**2+v.co.z**2) for v in ring]
        sil.append({"y": y, "r_mean": sum(rr)/len(rr), "r_max": max(rr), "n": len(ring)})
    checks["silhouette"] = sil
    bm.free()
    log("tip_axis", tip_status, "r_min", checks["tip_r_min"], "r_mean", checks["tip_r_mean"])
    render_views("polish_final", cut)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
    size = os.path.getsize(GLB); log("GLB", size)
    bpy.ops.wm.save_as_mainfile(filepath=WORK)

    missing = []
    if seal_info["seal_faces"] <= 0: missing.append("seals 0")
    if checks.get("_open_windows", 0) < 4: missing.append(f"open={checks.get('_open_windows')}")
    if checks.get("tip_r_min", 1) > 0.08: missing.append(f"tip r_min={checks['tip_r_min']:.3f}")
    if tip_status != "SOLID": missing.append(f"tip {tip_status}")
    if size > 2.5 * 1024 * 1024: missing.append("GLB>2.5MB")

    with open(os.path.join(LOG, "polish_v3b_report.json"), "w", encoding="utf-8") as f:
        json.dump({"glb": size, "seals": seal_info, "radome": rad, "holes": checks, "missing": missing}, f, indent=2, ensure_ascii=False)

    with open(NOTES, "w", encoding="utf-8") as f:
        f.write(f"""# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm, limited dissolve 8°, loop Laplacian
2. Seals: **{seal_info['seal_faces']} faces** (WS/SW outer-face boundaries; panes are closed thin solids)
   - 4 cm, inset 2 mm, BVH snap, black Roughness 0.5
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: delete flat +Y tip-disk only (r<0.75, ny>0.45); hemisphere fan 6 rings + tip vert
   - {json.dumps(rad, ensure_ascii=False)}
5. No second edge-polish after radome (that previously smeared the tip)
6. Helpers hidden; GLB use_visible=True

## Checks
- windows OPEN: {checks.get('_open_windows')}/4
- tip_axis: {tip_status}; tip_y={tip_y:.3f}; r_min={checks['tip_r_min']}; r_mean={checks['tip_r_mean']}
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
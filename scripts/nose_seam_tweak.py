# -*- coding: utf-8 -*-
"""Tighten REF nose / fuselage seam by re-matching cut-ring W/H/centers.

Loads current public/models/c919.blend (post nose-replace).
No knife, no boolean join, no bridge.

  blender -b --factory-startup -P scripts/nose_seam_tweak.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import traceback

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT_DIR, "c919.blend")
GLB = os.path.join(OUT_DIR, "c919.glb")
LOG_DIR = os.path.join(ROOT, "scripts", "_nose_seam_logs")
PREV_DIR = os.path.join(OUT_DIR, "nose-seam")
OVERLAP_TARGET = 0.015  # keep ~1.5 cm
BAND = 0.06  # section sample half-thickness (m)

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PREV_DIR, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG_DIR, "console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts


def section_at_y(verts, y0, tol=BAND):
    band = [v for v in verts if abs(v.y - y0) <= tol]
    if len(band) < 6:
        # widen once
        band = [v for v in verts if abs(v.y - y0) <= tol * 2.5]
    if len(band) < 4:
        return None
    xs = [v.x for v in band]
    zs = [v.z for v in band]
    return {
        "y": y0,
        "W": max(xs) - min(xs),
        "H": max(zs) - min(zs),
        "cx": 0.5 * (max(xs) + min(xs)),
        "cz": 0.5 * (max(zs) + min(zs)),
        "n": len(band),
        "xmin": min(xs),
        "xmax": max(xs),
        "zmin": min(zs),
        "zmax": max(zs),
    }


def aft_ring_y(verts, quantile=0.02):
    """Y of the aft-most ring: average of verts in the lowest Y quantile."""
    ys = sorted(v.y for v in verts)
    n = max(1, int(len(ys) * quantile))
    return sum(ys[:n]) / n


def fwd_ring_y(verts, quantile=0.02):
    ys = sorted((v.y for v in verts), reverse=True)
    n = max(1, int(len(ys) * quantile))
    return sum(ys[:n]) / n


def apply_mesh_xform(obj, M: Matrix) -> None:
    """Bake world matrix then apply extra transform M in world space to mesh."""
    mw = obj.matrix_world.copy()
    me = obj.data
    me.transform(mw)
    me.transform(M)
    me.update()
    obj.matrix_world = Matrix.Identity(4)


def shade_smooth(obj) -> None:
    for p in obj.data.polygons:
        p.use_smooth = True


def measure_pair(fuse, nose, sample_y=None):
    fv = mesh_world_verts(fuse)
    nv = mesh_world_verts(nose)
    nose_aft = aft_ring_y(nv)
    fuse_fwd = fwd_ring_y(fv)
    # Prefer shared sample near seam: mid of nose_aft and fuse_fwd, or explicit
    if sample_y is None:
        sample_y = 0.5 * (nose_aft + fuse_fwd)
    # Also measure each at its own ring
    s_nose = section_at_y(nv, nose_aft, tol=0.05)
    s_fuse = section_at_y(fv, fuse_fwd, tol=0.05)
    s_common_n = section_at_y(nv, sample_y, tol=0.08)
    s_common_f = section_at_y(fv, sample_y, tol=0.08)
    return {
        "nose_aft_y": nose_aft,
        "fuse_fwd_y": fuse_fwd,
        "sample_y": sample_y,
        "overlap_m": fuse_fwd - nose_aft,  # positive if fuse extends forward of nose aft? 
        # Actually overlap: nose extends aft of fuse front → nose_aft < fuse_fwd
        "overlap_cm": (fuse_fwd - nose_aft) * 100.0,
        "nose_ring": s_nose,
        "fuse_ring": s_fuse,
        "common_nose": s_common_n,
        "common_fuse": s_common_f,
    }


def delta_from(meas_nose, meas_fuse):
    if not meas_nose or not meas_fuse:
        return None
    return {
        "dW": abs(meas_nose["W"] - meas_fuse["W"]),
        "dH": abs(meas_nose["H"] - meas_fuse["H"]),
        "dcx": abs(meas_nose["cx"] - meas_fuse["cx"]),
        "dcz": abs(meas_nose["cz"] - meas_fuse["cz"]),
        "W_n": meas_nose["W"],
        "W_f": meas_fuse["W"],
        "H_n": meas_nose["H"],
        "H_f": meas_fuse["H"],
        "cx_n": meas_nose["cx"],
        "cx_f": meas_fuse["cx"],
        "cz_n": meas_nose["cz"],
        "cz_f": meas_fuse["cz"],
    }


def setup_cam(loc, look, name):
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.lens = 70
    return cam


def render_seam_views(tag, seam_y, cx, cz):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    try:
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_cavity = True
    except Exception:
        pass
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        ld = bpy.data.lights.new("SeamSun", "SUN")
        ld.energy = 3.5
        lo = bpy.data.objects.new("SeamSun", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))

    look = Vector((cx, seam_y, cz))
    # close-ups on the join
    views = {
        "front": Vector((0.0, seam_y + 6.5, cz + 0.2)),
        "side": Vector((5.5, seam_y, cz + 0.15)),
        "oblique45": Vector((4.2, seam_y + 4.2, cz + 0.8)),
    }
    paths = []
    for o in list(bpy.data.objects):
        if o.name.startswith("SeamCam_"):
            bpy.data.objects.remove(o, do_unlink=True)
    for vname, loc in views.items():
        cam = setup_cam(loc, look, f"SeamCam_{vname}")
        scene.camera = cam
        out = os.path.join(PREV_DIR, f"{tag}_{vname}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        paths.append(out)
        log(f"[QA] {out}")
        bpy.data.objects.remove(cam, do_unlink=True)
    return paths


def main():
    open(os.path.join(LOG_DIR, "console.txt"), "w", encoding="utf-8").close()
    log("=== NOSE SEAM TWEAK ===")
    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    fuse = bpy.data.objects.get("Fuselage")
    nose = bpy.data.objects.get("Nose")
    glass = bpy.data.objects.get("CockpitGlass_REF")
    cabin = bpy.data.objects.get("CockpitCabin")
    if fuse is None or nose is None:
        raise RuntimeError(f"missing Fuselage/Nose: fuse={fuse} nose={nose}")
    group = [o for o in (nose, glass, cabin) if o is not None]
    log(f"group: {[o.name for o in group]}")

    before = measure_pair(fuse, nose)
    # Use ring-vs-ring for corrective scale (most accurate for seam)
    d_before = delta_from(before["nose_ring"], before["fuse_ring"])
    log(
        f"[before] nose_aft={before['nose_aft_y']:.4f} fuse_fwd={before['fuse_fwd_y']:.4f} "
        f"overlap={before['overlap_cm']:.2f} cm"
    )
    log(
        f"[before] ΔW={d_before['dW']*100:.3f} cm ΔH={d_before['dH']*100:.3f} cm "
        f"Wn={d_before['W_n']:.4f} Wf={d_before['W_f']:.4f} "
        f"Hn={d_before['H_n']:.4f} Hf={d_before['H_f']:.4f}"
    )
    log(
        f"[before] dcx={d_before['dcx']*100:.3f} cm dcz={d_before['dcz']*100:.3f} cm"
    )

    Wf, Hf = d_before["W_f"], d_before["H_f"]
    Wn, Hn = d_before["W_n"], d_before["H_n"]
    cxf, czf = d_before["cx_f"], d_before["cz_f"]
    cxn, czn = d_before["cx_n"], d_before["cz_n"]

    # Axis scales about nose aft-ring center, then translate centers
    sx = Wf / Wn if Wn > 1e-6 else 1.0
    sz = Hf / Hn if Hn > 1e-6 else 1.0
    # Prefer keeping windshield aspect: if sx/sz diverge a lot, blend toward mean
    ratio = sx / sz if sz > 1e-9 else 1.0
    if abs(ratio - 1.0) > 0.015:
        # soft blend 70% axis + 30% mean to limit glass warp
        s_mean = 0.5 * (sx + sz)
        sx = 0.7 * sx + 0.3 * s_mean
        sz = 0.7 * sz + 0.3 * s_mean
        mode = "blended_axis"
    else:
        mode = "axis"
    sy = 1.0  # do not stretch length — preserves tip/glass Y layout

    log(f"[scale] mode={mode} sx={sx:.6f} sy={sy:.6f} sz={sz:.6f} (raw sx={Wf/Wn:.6f} sz={Hf/Hn:.6f})")

    # Pivot at nose aft-ring center (cxn, nose_aft, czn)
    pivot = Vector((cxn, before["nose_aft_y"], czn))
    # Scale about pivot in X/Z only
    S = (
        Matrix.Translation(pivot)
        @ Matrix.Diagonal((sx, sy, sz, 1.0))
        @ Matrix.Translation(-pivot)
    )
    # After scale, centers move? Scaling about (cxn,_,czn) keeps cxn/czn fixed.
    # Then translate so nose center matches fuse center.
    # Recompute after scale applied — do translate in same pass using predicted centers
    dx = cxf - cxn  # center already at cxn; after scale still cxn
    dz = czf - czn
    # Also fine-tune overlap: target nose_aft = fuse_fwd - OVERLAP_TARGET
    target_aft = before["fuse_fwd_y"] - OVERLAP_TARGET
    dy = target_aft - before["nose_aft_y"]
    T = Matrix.Translation(Vector((dx, dy, dz)))
    M = T @ S

    for obj in group:
        apply_mesh_xform(obj, M)
        shade_smooth(obj)

    after = measure_pair(fuse, nose)
    d_after = delta_from(after["nose_ring"], after["fuse_ring"])
    log(
        f"[after] nose_aft={after['nose_aft_y']:.4f} fuse_fwd={after['fuse_fwd_y']:.4f} "
        f"overlap={after['overlap_cm']:.2f} cm"
    )
    log(
        f"[after] ΔW={d_after['dW']*100:.3f} cm ΔH={d_after['dH']*100:.3f} cm "
        f"Wn={d_after['W_n']:.4f} Wf={d_after['W_f']:.4f} "
        f"Hn={d_after['H_n']:.4f} Hf={d_after['H_f']:.4f}"
    )
    log(
        f"[after] dcx={d_after['dcx']*100:.3f} cm dcz={d_after['dcz']*100:.3f} cm"
    )

    # Second pass if still > 0.3 cm: pure axis residual correction
    if d_after["dW"] > 0.003 or d_after["dH"] > 0.003:
        Wn2, Hn2 = d_after["W_n"], d_after["H_n"]
        sx2 = Wf / Wn2 if Wn2 > 1e-6 else 1.0
        sz2 = Hf / Hn2 if Hn2 > 1e-6 else 1.0
        # keep sy=1; if residual tiny, apply full axis
        pivot2 = Vector((d_after["cx_n"], after["nose_aft_y"], d_after["cz_n"]))
        S2 = (
            Matrix.Translation(pivot2)
            @ Matrix.Diagonal((sx2, 1.0, sz2, 1.0))
            @ Matrix.Translation(-pivot2)
        )
        dx2 = d_after["cx_f"] - d_after["cx_n"]
        dz2 = d_after["cz_f"] - d_after["cz_n"]
        target_aft2 = after["fuse_fwd_y"] - OVERLAP_TARGET
        dy2 = target_aft2 - after["nose_aft_y"]
        M2 = Matrix.Translation(Vector((dx2, dy2, dz2))) @ S2
        for obj in group:
            apply_mesh_xform(obj, M2)
            shade_smooth(obj)
        after = measure_pair(fuse, nose)
        d_after = delta_from(after["nose_ring"], after["fuse_ring"])
        log(
            f"[pass2] sx={sx2:.6f} sz={sz2:.6f} "
            f"ΔW={d_after['dW']*100:.3f} cm ΔH={d_after['dH']*100:.3f} cm "
            f"overlap={after['overlap_cm']:.2f} cm"
        )
        sx *= sx2
        sz *= sz2
        dy += dy2
        dx += dx2
        dz += dz2

    # Hide leftovers
    for name in ("PilotSeats", "Fuselage_ORIG", "PanelLines"):
        o = bpy.data.objects.get(name)
        if o:
            o.hide_set(True)
            o.hide_render = True
            o.hide_viewport = True

    # backup + export
    if os.path.isfile(GLB):
        bak = GLB + ".bak-nose-seam"
        shutil.copy2(GLB, bak)
        log(f"backup {bak}")
    bpy.ops.export_scene.gltf(
        filepath=GLB,
        export_format="GLB",
        use_visible=True,
        use_selection=False,
        export_apply=True,
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    size = os.path.getsize(GLB)
    log(f"GLB {size} ({size/1e6:.2f} MB)")

    seam_y = 0.5 * (after["nose_aft_y"] + after["fuse_fwd_y"])
    paths = render_seam_views("seam", seam_y, d_after["cx_f"], d_after["cz_f"])

    summary = {
        "before": {"measure": before, "delta": d_before},
        "after": {"measure": after, "delta": d_after},
        "scale_applied": {"sx": sx, "sy": sy, "sz": sz, "mode": mode, "dx": dx, "dy": dy, "dz": dz},
        "overlap_target_m": OVERLAP_TARGET,
        "glb_bytes": size,
        "previews": paths,
    }
    with open(os.path.join(LOG_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    notes = os.path.join(ROOT, "scripts", "NOSE_SEAM_TWEAK_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 机头接缝微调\n\n")
        f.write("## Before → After\n")
        f.write(
            f"- ΔW: {d_before['dW']*100:.3f} cm → **{d_after['dW']*100:.3f} cm**\n"
        )
        f.write(
            f"- ΔH: {d_before['dH']*100:.3f} cm → **{d_after['dH']*100:.3f} cm**\n"
        )
        f.write(
            f"- dcx: {d_before['dcx']*100:.3f} → {d_after['dcx']*100:.3f} cm；"
            f"dcz: {d_before['dcz']*100:.3f} → {d_after['dcz']*100:.3f} cm\n"
        )
        f.write(
            f"- overlap: {before['overlap_cm']:.2f} → {after['overlap_cm']:.2f} cm "
            f"(目标 {OVERLAP_TARGET*100:.1f} cm)\n"
        )
        f.write(
            f"- 本轮累计缩放 sx={sx:.6f} sy={sy:.6f} sz={sz:.6f}（mode={mode}）\n"
        )
        f.write(f"- 平移 dx={dx*1000:.2f} mm dy={dy*1000:.2f} mm dz={dz*1000:.2f} mm\n")
        f.write(f"- GLB: {size/1e6:.2f} MB；备份 `.bak-nose-seam`\n")
        f.write("- 预览: `public/models/nose-seam/seam_{front,side,oblique45}.png`\n\n")
        f.write("## 做法\n")
        f.write("- 在 nose 后缘环与 fuselage 前缘环上测 W/H/中心\n")
        f.write("- Nose+玻璃+驾驶舱一体：绕后缘中心做 X/Z 缩放，再对齐中心与 overlap\n")
        f.write("- 不改 Y 向比例（sy=1），避免风挡前后被拉长\n")
        f.write("- 无 knife / 无布尔拼接 / 无桥接\n\n")
        f.write("## 诚实差距\n")
        if d_after["dW"] > 0.003 or d_after["dH"] > 0.003:
            f.write("- 仍略超 0.3 cm：两边拓扑密度不同，环采样带宽内极值不完全重合\n")
        else:
            f.write("- 截面匹配已达 ≤0.3 cm\n")
        f.write("- 接缝仍靠重叠遮盖，侧视可能有双层皮\n")
        f.write("- REF 与程序化机身分段密度不同，近距能看出接缝线\n")
    log(f"notes -> {notes}")
    log("=== DONE ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise

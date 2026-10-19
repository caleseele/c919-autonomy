# -*- coding: utf-8 -*-
"""STEP A: list objects with AABB tip_dist≥37. STEP B/C: cam self-check + timestamped compare.

  blender -b --factory-startup -P scripts/aft_s5b3_list_and_camcheck.py
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-s5b3")
REFS = os.path.join(ROOT, "refs")

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs


def world_aabb(ob):
    """World AABB from bound_box (includes hidden)."""
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def tip_y():
    nose = bpy.data.objects.get("Nose")
    if not nose:
        # fallback: max Y among all meshes
        ys = []
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            a = world_aabb(o)
            ys += [a["ymin"], a["ymax"]]
        return max(ys)
    return max(v.y for v in mwv(nose))


def list_objects_gt37(tip: float):
    """All mesh objects (incl hidden / .001) whose AABB aftmost tip_dist >= 37."""
    rows = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        # include hidden
        a = world_aabb(ob)
        # aftmost = min Y (forward is +Y)
        aft_y = a["ymin"]
        tip_dist_aft = tip - aft_y
        if tip_dist_aft >= 37.0 - 1e-6:
            rows.append({
                "name": ob.name,
                "hide_viewport": bool(ob.hide_viewport),
                "hide_render": bool(ob.hide_render),
                "hide_get": bool(ob.hide_get()),
                "aabb": a,
                "tip_distance_aftmost": tip_dist_aft,
                "verts": len(ob.data.vertices) if ob.data else 0,
            })
    rows.sort(key=lambda r: -r["tip_distance_aftmost"])
    return rows


def ensure_side_camera(tip: float, tail_y: float):
    """Ortho side cam; adjust until tip_screen_x < tail_screen_x."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    scene.render.film_transparent = False

    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.12
    ymid = 0.5 * (tip + tail_y)
    # Candidate A: cam on +X looking -X, rot (90°, 0, 90°) — historically nose-left
    # Candidate B: flip 180° around Z if needed
    configs = [
        {"loc": (80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, math.pi / 2), "tag": "+X_look_-X"},
        {"loc": (-80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, -math.pi / 2), "tag": "-X_look_+X"},
        {"loc": (80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, -math.pi / 2), "tag": "+X_look_+X_flip"},
        {"loc": (-80.0, ymid, 0.0), "rot": (math.pi / 2, 0.0, math.pi / 2), "tag": "-X_alt"},
    ]
    scene.camera = cam
    tip_pt = Vector((0.0, tip, 0.0))
    tail_pt = Vector((0.0, tail_y, 0.0))

    chosen = None
    for cfg in configs:
        cam.location = cfg["loc"]
        cam.rotation_euler = cfg["rot"]
        bpy.context.view_layer.update()
        tip_ndc = world_to_camera_view(scene, cam, tip_pt)
        tail_ndc = world_to_camera_view(scene, cam, tail_pt)
        tip_sx = tip_ndc.x
        tail_sx = tail_ndc.x
        log(f"[cam-try] {cfg['tag']} tip_sx={tip_sx:.4f} tail_sx={tail_sx:.4f}")
        if tip_sx < tail_sx:
            chosen = {
                "tag": cfg["tag"],
                "tip_screen_x": tip_sx,
                "tail_screen_x": tail_sx,
                "tip_ndc": [tip_ndc.x, tip_ndc.y, tip_ndc.z],
                "tail_ndc": [tail_ndc.x, tail_ndc.y, tail_ndc.z],
                "loc": list(cfg["loc"]),
                "rot": list(cfg["rot"]),
            }
            break
    if chosen is None:
        # force first config and report failure
        cam.location = configs[0]["loc"]
        cam.rotation_euler = configs[0]["rot"]
        bpy.context.view_layer.update()
        tip_ndc = world_to_camera_view(scene, cam, tip_pt)
        tail_ndc = world_to_camera_view(scene, cam, tail_pt)
        chosen = {
            "tag": configs[0]["tag"] + "_FAILED_ORIENT",
            "tip_screen_x": tip_ndc.x,
            "tail_screen_x": tail_ndc.x,
            "orient_ok": False,
            "tip_ndc": [tip_ndc.x, tip_ndc.y, tip_ndc.z],
            "tail_ndc": [tail_ndc.x, tail_ndc.y, tail_ndc.z],
        }
    else:
        chosen["orient_ok"] = True
    return cam, chosen


def find_tail_tip_y(tip: float, listed):
    """Aftmost Y among listed objects (or Fuselage)."""
    if listed:
        return min(r["aabb"]["ymin"] for r in listed)
    fu = bpy.data.objects.get("Fuselage")
    if fu:
        return world_aabb(fu)["ymin"]
    return tip - 38.84


def render_timestamped(tip: float, cam_info: dict):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"side_compare_{stamp}.png"
    # render ours + ref separately then we only need ours for diagnosis? User asked compare.
    # Render ours only to timestamped path first; also build compare if possible.
    ours_name = f"side_ours_{stamp}.png"
    ref_name = f"side_ref_{stamp}.png"
    ours_path = os.path.join(PREV, ours_name)
    ref_path = os.path.join(PREV, ref_name)
    cmp_path = os.path.join(PREV, fname)

    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    bpy.context.scene.render.filepath = ours_path
    bpy.ops.render.render(write_still=True)
    log(f"[render] {ours_path}")

    # REF
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    ref_note = fbx
    if os.path.isfile(fbx):
        bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
        refs = [o for o in bpy.data.objects if o not in before]
        for o in refs:
            o.name = "LengthRef_" + o.name[:50]
        ys = []
        for o in refs:
            if o.type != "MESH":
                continue
            a = world_aabb(o)
            ys += [a["ymin"], a["ymax"]]
        if ys:
            dy = tip - max(ys)
            for o in refs:
                o.location.y += dy
        bpy.context.view_layer.update()
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            o.hide_render = not o.name.startswith("LengthRef_")
        bpy.context.scene.render.filepath = ref_path
        bpy.ops.render.render(write_still=True)
        log(f"[render] {ref_path}")
        for o in list(bpy.data.objects):
            if o.name.startswith("LengthRef_"):
                bpy.data.objects.remove(o, do_unlink=True)
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.hide_render = False
    else:
        ref_path = None
        ref_note = "REF missing"

    # stack with PIL if available else copy ours as compare placeholder note
    try:
        from PIL import Image
        im1 = Image.open(ours_path)
        if ref_path and os.path.isfile(ref_path):
            im2 = Image.open(ref_path)
            w = 1280
            def fit(im, w):
                h = int(round(im.height * w / im.width))
                return im.resize((w, h), Image.Resampling.LANCZOS)
            a = fit(im1, w)
            b = fit(im2, w)
            out = Image.new("RGB", (w, a.height + b.height), (18, 18, 20))
            out.paste(a, (0, 0))
            out.paste(b, (0, a.height))
            out.save(cmp_path)
            im2.close()
        else:
            im1.save(cmp_path)
        im1.close()
    except Exception as e:
        log(f"[stack] PIL fail {e}; copy ours")
        import shutil
        shutil.copy2(ours_path, cmp_path)

    mtime = os.path.getmtime(cmp_path)
    mtime_iso = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    size = os.path.getsize(cmp_path)
    return {
        "compare_path": cmp_path,
        "compare_name": fname,
        "ours_path": ours_path,
        "ref_path": ref_path,
        "mtime_epoch": mtime,
        "mtime_local": mtime_iso,
        "size_bytes": size,
        "ref_note": ref_note,
        "cam": cam_info,
    }


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tip = tip_y()
    log(f"[tip] y={tip:.6f}")

    # STEP A
    listed = list_objects_gt37(tip)
    log(f"[list] n={len(listed)} objects tip_dist_aft≥37")
    for r in listed:
        a = r["aabb"]
        log(
            f"  {r['name']} tip_aft={r['tip_distance_aftmost']:.3f} "
            f"AABB x[{a['xmin']:.3f},{a['xmax']:.3f}] "
            f"y[{a['ymin']:.3f},{a['ymax']:.3f}] "
            f"z[{a['zmin']:.3f},{a['zmax']:.3f}] "
            f"hide_v={r['hide_viewport']} hide_r={r['hide_render']} hide_get={r['hide_get']} verts={r['verts']}"
        )

    out_json = {
        "tip_y": tip,
        "threshold_tip_distance": 37.0,
        "forward_axis": "+Y",
        "aftmost": "min Y",
        "count": len(listed),
        "objects": listed,
        "note": "LIST ONLY — no deletes this turn. User confirm before delete.",
        "forked_claim": None,
        "forked_note": "NOT claiming forked=False/True this turn; list first.",
    }
    path_json = os.path.join(LOG, "aft_tail_objects_gt37.json")
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    log(f"[json] {path_json}")

    zh_lines = [
        "# 尾段 tip_dist≥37 m 物体清单（仅列表，未删除）",
        f"- tip_y = {tip:.4f}（机头 +Y）",
        f"- 判定：世界 AABB 最后缘 tip距离 = tip_y − ymin ≥ 37",
        f"- 共 {len(listed)} 个 mesh（含隐藏 / .001）",
        "",
        "| 名称 | tip距离(最后缘) | ymin..ymax | zmin..zmax | 隐藏 |",
        "|---|---:|---|---|---|",
    ]
    for r in listed:
        a = r["aabb"]
        hid = []
        if r["hide_viewport"]:
            hid.append("viewport")
        if r["hide_render"]:
            hid.append("render")
        if r["hide_get"]:
            hid.append("hide_get")
        zh_lines.append(
            f"| `{r['name']}` | {r['tip_distance_aftmost']:.3f} | "
            f"{a['ymin']:.3f}..{a['ymax']:.3f} | {a['zmin']:.3f}..{a['zmax']:.3f} | "
            f"{','.join(hid) if hid else '可见'} |"
        )
    zh_lines.append("")
    zh_lines.append("下一步需用户确认后再删除多余物体。")
    zh_path = os.path.join(LOG, "aft_tail_objects_gt37.zh-Hans.md")
    with open(zh_path, "w", encoding="utf-8") as f:
        f.write("\n".join(zh_lines) + "\n")
    log(f"[zh] {zh_path}")

    # STEP B + C — diagnosis render with verified screen x
    tail_y = find_tail_tip_y(tip, listed)
    cam, cam_info = ensure_side_camera(tip, tail_y)
    log(
        f"[cam] orient_ok={cam_info.get('orient_ok')} "
        f"tip_screen_x={cam_info['tip_screen_x']:.6f} "
        f"tail_screen_x={cam_info['tail_screen_x']:.6f} tag={cam_info.get('tag')}"
    )
    render_info = render_timestamped(tip, cam_info)

    summary = {
        "tip_y": tip,
        "tail_y": tail_y,
        "tip_screen_x": cam_info["tip_screen_x"],
        "tail_screen_x": cam_info["tail_screen_x"],
        "orient_ok": cam_info.get("orient_ok"),
        "cam_tag": cam_info.get("tag"),
        "object_count_gt37": len(listed),
        "objects_gt37": listed,
        "image": render_info,
        "list_json": path_json,
        "list_zh": zh_path,
        "deleted": False,
        "forked_verified": None,
    }
    with open(os.path.join(LOG, "aft_s5b3_list_cam.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(
        f"[image] {render_info['compare_name']} mtime={render_info['mtime_local']} "
        f"size={render_info['size_bytes']}"
    )
    log("=== LIST+CAM DONE (no deletes) ===")


if __name__ == "__main__":
    main()

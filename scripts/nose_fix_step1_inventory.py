# -*- coding: utf-8 -*-
"""Step 1 — inventory scene for C919 nose fix. blender -b only."""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Prefer running against project on PC; paths may be overridden via env.
PROJ = os.environ.get(
    "C919_PROJ",
    r"C:\Users\希儿\Projects\c919-autonomy",
)
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
REF_METERS = os.path.join(PROJ, "refs", "REF_C919_meters.fbx")
REF_CM = os.path.join(PROJ, "refs", "REF_C919.fbx")
OUT_DIR = os.path.join(PROJ, "public", "models", "nose-fix")
LOG_DIR = os.path.join(PROJ, "scripts", "_nose_fix_logs")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

FORWARD = Vector((0.0, -1.0, 0.0))  # Soft: nose tip +Y, forward travel -Y? Soft tip at +Y so forward looks -Y from tip... wait Soft nose tip is at +Y ~20, so nose points +Y. FORWARD for cutter = direction nose points = +Y? User script says FORWARD=(0,-1,0) for 机头朝向 -Y. Soft model tip at +Y means nose points toward +Y, so forward axis of aircraft is +Y. But user's cutter says -Y. Check Soft: tip_y=20, cabin at lower Y → nose at +Y end. So aircraft forward = +Y. User wrote FORWARD=(0,-1,0) meaning "机头朝向：-Y". There may be confusion. Inventory will report AABB and tip location.


def log(*a):
    print("STEP1", *a, flush=True)


def world_aabb(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    return mn, mx, mx - mn


def ensure_ref_in_scene():
    """Import REF meters mesh if missing; clean helpers."""
    target = None
    for o in bpy.data.objects:
        if "2-287" in o.name:
            target = o
            break
    if target is not None:
        log("REF already in scene:", target.name)
        return target

    path = REF_METERS if os.path.isfile(REF_METERS) else REF_CM
    if not os.path.isfile(path):
        log("REF FBX missing:", path)
        return None

    before = set(bpy.data.objects.keys())
    scale = 1.0 if "meters" in os.path.basename(path).lower() else 0.01
    log("importing REF", path, "global_scale", scale)
    bpy.ops.import_scene.fbx(filepath=path, global_scale=scale, use_image_search=False)
    after = [o for o in bpy.data.objects if o.name not in before]
    for o in list(after):
        if "1-818" in o.name or o.name == "Cube" or (o.type == "MESH" and len(o.data.vertices) < 100):
            log("removing helper", o.name)
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if "2-287" in o.name:
            # Hide REF for procedural renders later; keep for inventory
            o.hide_render = False
            o.hide_viewport = False
            # Wire display optional
            try:
                o.display_type = "WIRE"
            except Exception:
                pass
            log("REF primary:", o.name, "verts", len(o.data.vertices), "faces", len(o.data.polygons))
            return o
    return None


def material_stats(obj):
    if obj is None or obj.type != "MESH":
        return []
    me = obj.data
    slots = []
    for i, slot in enumerate(me.materials):
        name = slot.name if slot else "<empty>"
        slots.append({"index": i, "name": name})
    counts = defaultdict(int)
    for p in me.polygons:
        counts[p.material_index] += 1
    out = []
    for i, info in enumerate(slots):
        mat = me.materials[i] if i < len(me.materials) else None
        base = None
        trans = None
        if mat and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    if "Base Color" in n.inputs:
                        base = list(n.inputs["Base Color"].default_value)
                    for key in ("Transmission Weight", "Transmission"):
                        if key in n.inputs:
                            trans = n.inputs[key].default_value
                            break
                    break
        out.append(
            {
                **info,
                "face_count": counts.get(i, 0),
                "base_color": base,
                "transmission": trans,
            }
        )
    # orphan indices
    for idx, c in counts.items():
        if idx >= len(slots):
            out.append({"index": idx, "name": "<orphan>", "face_count": c})
    return out


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
    except Exception:
        pass
    cam = bpy.data.objects.get("NoseFixCam")
    if cam is None:
        cam_data = bpy.data.cameras.new("NoseFixCam")
        cam = bpy.data.objects.new("NoseFixCam", cam_data)
        bpy.context.collection.objects.link(cam)
    cam.data.lens = 50
    scene.camera = cam
    return cam


def aim_camera(cam, eye, target, lens=50):
    cam.location = eye
    cam.data.lens = lens
    direction = (target - eye).normalized()
    # point -Z toward target
    rot = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()


def find_nose_target():
    """Find a point near procedural nose tip for camera aim."""
    tip = Vector((0.0, 19.5, 0.6))
    for name in ("Nose", "机身", "Fuselage", "FuselageBody"):
        o = bpy.data.objects.get(name)
        if o and o.type == "MESH":
            mn, mx, size = world_aabb(o)
            # Soft tip is +Y max
            tip = Vector((0.5 * (mn.x + mx.x), mx.y - 0.3, mn.z + 0.65 * size.z))
            return tip, o
    return tip, None


def render_nose_views(prefix, only_objects=None, hide_extra=None):
    """Render front / side / 45 of nose. only_objects: if set, hide others."""
    cam = setup_render()
    tip, body = find_nose_target()
    saved = {}
    if only_objects is not None:
        allow = set(only_objects)
        for o in bpy.data.objects:
            if o.type not in {"MESH", "CURVE", "EMPTY"}:
                continue
            saved[o.name] = (o.hide_render, o.hide_viewport, o.hide_get())
            show = o.name in allow or o.name == cam.name
            o.hide_render = not show
            try:
                o.hide_viewport = not show
            except Exception:
                pass
            try:
                o.hide_set(not show)
            except Exception:
                pass
    if hide_extra:
        for n in hide_extra:
            o = bpy.data.objects.get(n)
            if o:
                o.hide_render = True

    shots = [
        ("front", tip + Vector((0.0, 6.5, 0.4)), tip, 55),
        ("side", tip + Vector((7.5, -1.5, 0.8)), tip, 50),
        ("45", tip + Vector((5.0, 4.5, 1.5)), tip, 50),
    ]
    paths = []
    for tag, eye, tgt, lens in shots:
        aim_camera(cam, eye, tgt, lens)
        fp = os.path.join(OUT_DIR, f"{prefix}_{tag}.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        log("rendered", fp)
        paths.append(fp)

    # restore
    for name, (hr, hv, hg) in saved.items():
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        o.hide_render = hr
        try:
            o.hide_viewport = hv
        except Exception:
            pass
        try:
            o.hide_set(hg)
        except Exception:
            pass
    return paths


def main():
    log("loading", BLEND)
    if not os.path.isfile(BLEND):
        raise SystemExit("missing blend: " + BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    ref = ensure_ref_in_scene()

    inventory = []
    outline_objs = []
    body_candidates = []

    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        mn, mx, size = world_aabb(obj) if obj.type in {"MESH", "CURVE", "EMPTY"} and hasattr(obj, "bound_box") else (None, None, None)
        entry = {
            "name": obj.name,
            "type": obj.type,
            "hide_viewport": bool(obj.hide_viewport),
            "hide_render": bool(obj.hide_render),
            "hide_get": bool(obj.hide_get()) if hasattr(obj, "hide_get") else None,
            "parent": obj.parent.name if obj.parent else None,
            "verts": len(obj.data.vertices) if obj.type == "MESH" else None,
            "faces": len(obj.data.polygons) if obj.type == "MESH" else None,
            "aabb_min": list(mn) if mn else None,
            "aabb_max": list(mx) if mx else None,
            "aabb_size": list(size) if size else None,
        }
        if obj.type == "MESH" and obj.data.vertices:
            # tip-ish: max Y vertex
            ys = [v.co.y for v in obj.data.vertices]
            entry["local_y_min"] = min(ys)
            entry["local_y_max"] = max(ys)
        inventory.append(entry)
        log(
            "OBJ",
            obj.name,
            obj.type,
            "size",
            [round(x, 3) for x in size] if size else None,
            "hide",
            entry["hide_viewport"],
            entry["hide_render"],
            "v/f",
            entry["verts"],
            entry["faces"],
        )
        low = obj.name.lower()
        if "windowoutline" in low or "窗户轮廓" in obj.name or "outline" in low:
            outline_objs.append(obj)
        if obj.type == "MESH" and obj.name in ("Nose", "机身", "Fuselage", "FuselageBody", "Body"):
            body_candidates.append(obj.name)
        elif obj.type == "MESH" and size and size.y > 10 and size.x > 2 and "2-287" not in obj.name:
            body_candidates.append(obj.name)

    # Outline detail
    outline_detail = []
    for obj in outline_objs:
        d = {"name": obj.name, "type": obj.type}
        if obj.type == "MESH":
            d["verts"] = len(obj.data.vertices)
            d["edges"] = len(obj.data.edges)
            d["faces"] = len(obj.data.polygons)
            # connected edge components
            bm_verts = len(obj.data.vertices)
            d["segments_guess"] = max(1, len(obj.data.edges) // max(1, bm_verts // 4 or 1))
        elif obj.type == "CURVE":
            d["splines"] = len(obj.data.splines)
            d["points"] = [len(s.points) if hasattr(s, "points") else len(s.bezier_points) for s in obj.data.splines]
        outline_detail.append(d)
        log("OUTLINE", d)

    # REF materials
    ref_mats = material_stats(ref) if ref else []
    log("REF_MAT_COUNT", len(ref_mats))
    for m in ref_mats:
        log("REF_MAT", m)

    # Nose forward axis from procedural Nose
    nose = bpy.data.objects.get("Nose")
    forward_report = {
        "soft_convention": "tip at +Y (max Y), aircraft forward toward +Y",
        "user_cutter_FORWARD": [0.0, -1.0, 0.0],
        "note": "Cutter FORWARD is outward glass normal filter vs body; Soft nose tip is +Y",
    }
    if nose:
        mn, mx, size = world_aabb(nose)
        forward_report["nose_aabb_min"] = list(mn)
        forward_report["nose_aabb_max"] = list(mx)
        forward_report["nose_size"] = list(size)
        forward_report["tip_world"] = [0.0, mx.y, (mn.z + mx.z) * 0.5]
        # glass normal toward outside / forward for front panes points roughly -Y? Front panes face toward +Y (looking forward from cockpit looks +Y). Outward normal of front glass ≈ +Y (or slightly up). User FORWARD=(0,-1,0) with ONLY_FRONT uses n.dot(fwd)>0.35 — if fwd=-Y then front glass needs normal toward -Y which would be wrong for Soft. Will verify in step3.

    result = {
        "blend": BLEND,
        "object_count": len(inventory),
        "objects": inventory,
        "body_candidates": body_candidates,
        "body_best_guess": "Nose" if bpy.data.objects.get("Nose") else (body_candidates[0] if body_candidates else None),
        "forward": forward_report,
        "window_outlines": outline_detail,
        "window_outline_count": len(outline_objs),
        "ref_present": ref.name if ref else None,
        "ref_materials": ref_mats,
        "dark_glass_candidates": [
            m for m in ref_mats
            if m.get("name") and any(tag in m["name"] for tag in ("011", "013", "017", "001"))
        ],
    }

    json_path = os.path.join(LOG_DIR, "step1_inventory.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log("wrote", json_path)

    # Renders: current procedural (hide REF wire), then REF alone
    ref_name = ref.name if ref else None
    hide_ref = [ref_name] if ref_name else []
    # Unhide WindowOutline so current-state shows floating lines
    for o in outline_objs:
        o.hide_render = False
        try:
            o.hide_set(False)
        except Exception:
            pass

    paths_cur = render_nose_views("step1_current", hide_extra=hide_ref)
    paths_ref = []
    if ref_name:
        try:
            ref.display_type = "SOLID"
        except Exception:
            pass
        paths_ref = render_nose_views("step1_ref", only_objects=[ref_name])

    # Save working blend with REF appended (hidden)
    if ref:
        ref.hide_render = True
        ref.hide_viewport = True
        try:
            ref.hide_set(True)
        except Exception:
            pass
    work_blend = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
    bpy.ops.wm.save_as_mainfile(filepath=work_blend)
    log("saved work blend", work_blend)

    print("\n===== STEP1_OK =====")
    print("BODY:", result["body_best_guess"])
    print("FORWARD tip +Y; cutter FORWARD param needs check vs Soft")
    print("WindowOutline count:", result["window_outline_count"], outline_detail)
    print("REF:", result["ref_present"])
    print("REF dark mat candidates:", [m["name"] for m in result["dark_glass_candidates"]])
    print("renders:", paths_cur + paths_ref)
    print("json:", json_path)
    print("===== END STEP1_OK =====\n")


if __name__ == "__main__":
    main()

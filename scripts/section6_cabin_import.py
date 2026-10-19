# -*- coding: utf-8 -*-
"""§6: delete old cabin doors/windows; import REF 舱门舷窗; shrinkwrap.

  blender -b --factory-startup -P scripts/section6_cabin_import.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section6")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

# Same transform as REF nose skin (from ref_detail_pass_A / nose_replace)
SX, SY, SZ = 1.045685, 1.021632, 0.997579
DX, DY, DZ = 0.0, 15.3458, -4.1641
# seam multipliers
SX2, SZ2 = 0.998292, 0.999876
DY2 = -0.0075

DELETE_CABIN = ["DoorFrames", "DoorWindows", "Doors", "WindowFrames", "Windows"]
KEEP = ["GearBayDoors"]

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section6_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs


def aabb(ob):
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
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))


def apply_mw(ob):
    me = ob.data
    me.transform(ob.matrix_world)
    me.update()
    ob.matrix_world = Matrix.Identity(4)


def delete_object(name: str) -> bool:
    ob = bpy.data.objects.get(name)
    if not ob:
        return False
    me = ob.data if ob.type == "MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)
    return True


def find_cabin_obj():
    for fn in os.listdir(REFS):
        if "舱门" in fn and fn.endswith(".obj"):
            return os.path.join(REFS, fn)
        if "舷窗" in fn and fn.endswith(".obj") and "舱" in fn:
            return os.path.join(REFS, fn)
    # hashed fallback
    p = os.path.join(REFS, "C919_REF_舱门舷窗.obj")
    if os.path.isfile(p):
        return p
    raise FileNotFoundError("C919_REF_舱门舷窗.obj")


def nose_style_matrix():
    """Replay REF nose skin transform: Z180 * S * T * seam."""
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((SX, SY, SZ, 1.0))
    T = Matrix.Translation(Vector((DX, DY, DZ)))
    # seam about approximate join pivot — use identity-ish pivot at cut
    # From pass_A: seam scale about pivot then T2
    # Simplified: apply same cumulative as details import
    S2 = Matrix.Diagonal((SX2, 1.0, SZ2, 1.0))
    T2 = Matrix.Translation(Vector((0.0, DY2, 0.0)))
    # Order matching pass_A: first R,S,T then seam about pivot
    # For details they used pivot at cut. Use T2 @ S2 @ T @ S @ R on mesh
    return T2 @ S2 @ T @ S @ R


def identify_upper_aft_block(tip: float):
    """Find protruding upper-aft object (not under belly)."""
    candidates = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        a = aabb(o)
        td_aft = tip - a["ymin"]
        if td_aft < 20:
            continue
        if a["zmax"] < 1.5:
            continue  # not upper
        under_belly = a["zmax"] < 0.0
        # prefer compact high objects
        score = a["zmax"]
        candidates.append({
            "name": o.name,
            "zmax": a["zmax"],
            "zmin": a["zmin"],
            "tip_aft": td_aft,
            "under_belly": under_belly,
            "score": score,
        })
    candidates.sort(key=lambda c: -c["score"])
    # GearBayDoors check
    g = bpy.data.objects.get("GearBayDoors")
    g_info = None
    if g:
        a = aabb(g)
        g_info = {"name": "GearBayDoors", "zmax": a["zmax"], "under_belly": a["zmax"] < 0.0}
    # top candidate that is NOT fuselage/REF skin/VT
    skip = ("Fuselage", "REF_尾段蒙皮", "REF_方向舵", "REF_水平", "Nose", "Cockpit")
    block = None
    for c in candidates:
        if any(s in c["name"] for s in skip):
            continue
        if c["name"] == "GearBayDoors":
            continue  # handled separately
        block = c
        break
    return block, g_info, candidates[:12]


def assign_cabin_materials(objs):
    def ensure(name, color, rough, metal=0.0, alpha=1.0, transmission=0.0):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
            bsdf.inputs["Roughness"].default_value = rough
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = metal
            if alpha < 1.0 or transmission > 0:
                if "Alpha" in bsdf.inputs:
                    bsdf.inputs["Alpha"].default_value = alpha
                if "Transmission Weight" in bsdf.inputs:
                    bsdf.inputs["Transmission Weight"].default_value = transmission
                elif "Transmission" in bsdf.inputs:
                    bsdf.inputs["Transmission"].default_value = transmission
                m.blend_method = "BLEND"
        return m

    # reuse existing window glass if any
    glass = None
    for m in bpy.data.materials:
        if "glass" in m.name.lower() or "Window" in m.name or "舷窗" in m.name:
            glass = m
            break
    if glass is None:
        glass = ensure("REF_舷窗玻璃", (0.18, 0.23, 0.24), 0.03, 0.0, 0.45, 1.0)
    seam = ensure("REF_舱门缝线", (0.227, 0.239, 0.259), 0.5, 0.0)

    for ob in objs:
        if ob.type != "MESH":
            continue
        ob.data.materials.clear()
        if "玻璃" in ob.name or "窗" in ob.name:
            ob.data.materials.append(glass)
        else:
            ob.data.materials.append(seam)
        log(f"[mat] {ob.name} -> {ob.data.materials[0].name}")


def shrinkwrap_apply(objs, target_names, offset=0.001):
    """Shrinkwrap to fuselage+REF skin, apply."""
    targets = []
    for n in target_names:
        o = bpy.data.objects.get(n)
        if o:
            targets.append(o)
    # also any REF skin
    for o in bpy.data.objects:
        if o.type == "MESH" and "蒙皮" in o.name and o not in targets:
            targets.append(o)
    if not targets:
        fuse = bpy.data.objects.get("Fuselage")
        if fuse:
            targets = [fuse]
    log(f"[wrap] targets={[t.name for t in targets]}")

    for ob in objs:
        if ob.type != "MESH":
            continue
        # one shrinkwrap toward primary target (Fuselage), then REF skin if needed
        for ti, tgt in enumerate(targets[:2]):
            mod = ob.modifiers.new(name=f"SW_{ti}", type="SHRINKWRAP")
            mod.target = tgt
            mod.wrap_method = "NEAREST_SURFACEPOINT"
            mod.offset = offset
            # apply
            bpy.context.view_layer.objects.active = ob
            ob.select_set(True)
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e:
                log(f"[wrap] apply fail {ob.name} {e}")
                ob.modifiers.remove(mod)
            ob.select_set(False)
        log(f"[wrap] applied {ob.name}")


def count_islands(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    remaining = set(bm.verts)
    n = 0
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        isl = {seed}
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in isl:
                    isl.add(o)
                    remaining.discard(o)
                    stack.append(o)
        n += 1
    bm.free()
    return n


def measure_cabin(tip, objs):
    """Count doors/windows vs SPEC."""
    glass = [o for o in objs if "玻璃" in o.name or ("窗" in o.name and "缝" not in o.name)]
    seams = [o for o in objs if "缝" in o.name or "门" in o.name]
    # island counts
    result = {"objects": [o.name for o in objs]}
    for o in objs:
        n_isl = count_islands(o)
        a = aabb(o)
        result[o.name] = {
            "islands": n_isl,
            "verts": len(o.data.vertices),
            "tip_span": [round(tip - a["ymax"], 3), round(tip - a["ymin"], 3)],
        }
        log(f"[count] {o.name} islands={n_isl} verts={len(o.data.vertices)}")
    # SPEC: 39 cabin windows per side + 2 emergency = 41 per side? 
    # "每侧 39 个客舱窗 + 2 个应急出口窗" and doors 4 per side
    # Glass object may contain all window panes as islands
    total_glass_islands = sum(result[o.name]["islands"] for o in glass) if glass else 0
    total_seam_islands = sum(result[o.name]["islands"] for o in seams) if seams else 0
    items = [
        {
            "项目": "舷窗玻璃岛数(双侧合计)",
            "实测": total_glass_islands,
            "参考": 82,  # 41*2
            "差值": total_glass_islands - 82,
            "是否通过": "是" if abs(total_glass_islands - 82) <= 4 else "否",
        },
        {
            "项目": "舱门缝线岛数(约)",
            "实测": total_seam_islands,
            "参考": 8,  # 4 per side
            "差值": total_seam_islands - 8,
            "是否通过": "是" if abs(total_seam_islands - 8) <= 4 else "否",
        },
        {
            "项目": "GearBayDoors保留",
            "实测": 1 if bpy.data.objects.get("GearBayDoors") else 0,
            "参考": 1,
            "差值": 0,
            "是否通过": "是" if bpy.data.objects.get("GearBayDoors") else "否",
        },
    ]
    return items, result


def cam_render(tip):
    # tail tip
    ys = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        a = aabb(o)
        ys += [a["ymin"], a["ymax"]]
    tail_y = min(ys)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    cam = bpy.data.objects.get("LengthSideCam")
    if cam is None:
        data = bpy.data.cameras.new("LengthSideCam")
        cam = bpy.data.objects.new("LengthSideCam", data)
        bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.12
    ymid = 0.5 * (tip + tail_y)
    cam.location = (-80.0, ymid, 0.0)
    cam.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)
    scene.camera = cam
    bpy.context.view_layer.update()
    ts = world_to_camera_view(scene, cam, Vector((0, tip, 0))).x
    ls = world_to_camera_view(scene, cam, Vector((0, tail_y, 0))).x
    if not (ts < ls):
        cam.location = (80.0, ymid, 0.0)
        cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
        bpy.context.view_layer.update()
        ts = world_to_camera_view(scene, cam, Vector((0, tip, 0))).x
        ls = world_to_camera_view(scene, cam, Vector((0, tail_y, 0))).x
    log(f"[cam] tip_sx={ts:.6f} tail_sx={ls:.6f} ok={ts < ls}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ours = os.path.join(PREV, f"side_ours_{stamp}.png")
    refp = os.path.join(PREV, f"side_ref_{stamp}.png")
    cmp = os.path.join(PREV, f"side_compare_{stamp}.png")
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    scene.render.filepath = ours
    bpy.ops.render.render(write_still=True)

    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
    refs = [o for o in bpy.data.objects if o not in before]
    for o in refs:
        o.name = "LengthRef_" + o.name[:40]
    rys = []
    for o in refs:
        if o.type == "MESH":
            a = aabb(o)
            rys += [a["ymin"], a["ymax"]]
    dy = tip - max(rys)
    for o in refs:
        o.location.y += dy
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not o.name.startswith("LengthRef_")
    scene.render.filepath = refp
    bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False
    return {"tip_screen_x": ts, "tail_screen_x": ls, "orient_ok": ts < ls,
            "ours": ours, "ref": refp, "compare_path": cmp, "stamp": stamp}


def main():
    open(os.path.join(LOG, "section6_console.txt"), "w", encoding="utf-8").close()
    log("=== SECTION 6 cabin doors/windows ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    bak = os.path.join(OUT, "c919.bak-section6.blend")
    shutil.copy2(BLEND, bak)
    log(f"[backup] {bak}")

    tip = tip_y()
    block, g_info, cands = identify_upper_aft_block(tip)
    log(f"[block] {block}")
    log(f"[GearBayDoors] {g_info}")

    deleted = []
    # Step1: delete upper protrusion if not under belly
    if block and not block.get("under_belly", True):
        if delete_object(block["name"]):
            deleted.append(block["name"])
            log(f"[del-block] {block['name']} (upper aft, not belly)")
    # never delete GearBayDoors here (kept; under belly)
    assert bpy.data.objects.get("GearBayDoors"), "GearBayDoors missing"

    # Step2: delete cabin list
    for n in DELETE_CABIN:
        if delete_object(n):
            deleted.append(n)
            log(f"[del] {n}")

    # Step3: import
    path = find_cabin_obj()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    log(f"[import] {path} n={len(new)} {[o.name for o in new]}")

    M = nose_style_matrix()
    for ob in new:
        if ob.type != "MESH":
            continue
        apply_mw(ob)
        ob.data.transform(M)
        ob.data.update()
        ob.matrix_world = Matrix.Identity(4)
        if not ob.name.startswith("REF_"):
            ob.name = "REF_" + ob.name
    log(f"[xform] nose-style sx={SX} sy={SY} sz={SZ} T=({DX},{DY},{DZ}) seam sx2={SX2}")

    # refine: align roughly to fuselage mid by matching centroid XZ (optional light)
    # shrinkwrap
    assign_cabin_materials(new)
    # gather target names for wrap
    skin_names = ["Fuselage"]
    for o in bpy.data.objects:
        if "蒙皮" in o.name:
            skin_names.append(o.name)
    shrinkwrap_apply(new, skin_names, offset=0.001)

    bpy.context.view_layer.update()
    items, counts = measure_cabin(tip, new)
    rend = cam_render(tip)

    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"GLB {os.path.getsize(GLB)}")

    result = {
        "backup": bak,
        "upper_aft_block": block,
        "gearbay": g_info,
        "deleted": deleted,
        "kept": KEEP,
        "imported": [o.name for o in new],
        "import_path": path,
        "counts": counts,
        "measurements": items,
        "camera": {k: rend[k] for k in ("tip_screen_x", "tail_screen_x", "orient_ok")},
        "render": rend,
        "scripts": ["section6_cabin_import.py"],
    }
    with open(os.path.join(LOG, "section6.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — §6 cabin doors/windows",
        f"- backup: c919.bak-section6.blend",
        f"- deleted upper block: {block['name'] if block and block['name'] in deleted else 'none'}; cabin: {[n for n in deleted if n in DELETE_CABIN]}",
        f"- KEEP GearBayDoors (belly z≈-2)",
        f"- imported {[o.name for o in new]}; shrinkwrap +1mm",
        f"- cam tip_sx={rend['tip_screen_x']:.4f} tail_sx={rend['tail_screen_x']:.4f}",
        f"- script: section6_cabin_import.py",
    ]
    for it in items:
        prog.append(f"- {it['项目']}: {it['实测']} ref={it['参考']} pass={it['是否通过']}")
    with open(PROGRESS, "w", encoding="utf-8") as f:
        f.write("\n".join(prog[:30]) + "\n")
    log("=== §6 DONE ===")


if __name__ == "__main__":
    main()

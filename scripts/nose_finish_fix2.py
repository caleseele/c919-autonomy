# -*- coding: utf-8 -*-
"""Fix finish issues: gap strip poke, radome overpaint, tip floaters, glass EEVEE, cabin inset."""
from __future__ import annotations

import json
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_nose_finish_logs")
PREV = os.path.join(OUT, "nose-finish")
os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)


def log(msg):
    print(msg, flush=True)
    with open(os.path.join(LOG, "console_fix2.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)


def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts


def shade_smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def reset_nose_materials(nose):
    """All faces back to Skin (slot 0); keep RadomePanel as slot 1 for selective use."""
    me = nose.data
    skin = None
    for m in me.materials:
        if m and m.name == "Skin":
            skin = m
            break
    if skin is None:
        skin = bpy.data.materials.get("Skin") or bpy.data.materials.new("Skin")
    panel = bpy.data.materials.get("RadomePanel")
    if panel is None:
        panel = bpy.data.materials.new("RadomePanel")
    panel.use_nodes = True
    bsdf = panel.node_tree.nodes.get("Principled BSDF")
    col = (0xC8 / 255.0, 0xCA / 255.0, 0xCD / 255.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.5
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    me.materials.clear()
    me.materials.append(skin)
    me.materials.append(panel)
    for p in me.polygons:
        p.material_index = 0
    log("[radome] reset all faces to Skin")


def assign_radome_rays_selective(nose):
    """Only faces adjacent to high-angle edges near tip, and only if face is thin (ray strip)."""
    me = nose.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    tip_y = max(v.co.y for v in bm.verts)
    tip_zone = tip_y - 0.85

    # Collect crease edges near tip
    crease_edges = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        ang = e.link_faces[0].normal.angle(e.link_faces[1].normal)
        if ang < math.radians(18):
            continue
        mid = 0.5 * (e.verts[0].co + e.verts[1].co)
        if mid.y < tip_zone:
            continue
        # prefer radial edges (mostly along Y or from tip)
        edge_vec = (e.verts[0].co - e.verts[1].co).normalized()
        # radial in XZ from centerline
        crease_edges.append(e)

    panel_faces = set()
    for e in crease_edges:
        for f in e.link_faces:
            area = f.calc_area()
            # thin face only
            if area > 0.008:
                continue
            c = f.calc_center_median()
            if c.y < tip_zone:
                continue
            lengths = sorted(ed.calc_length() for ed in f.edges)
            # elongated: longest >> shortest
            if lengths[-1] > 2.5 * max(lengths[0], 1e-6) or area < 0.004:
                panel_faces.add(f)

    # Cap count: if still too many, keep only closest to tip
    if len(panel_faces) > 400:
        ranked = sorted(panel_faces, key=lambda f: -f.calc_center_median().y)
        panel_faces = set(ranked[:320])

    for f in bm.faces:
        f.material_index = 0
    for f in panel_faces:
        f.material_index = 1
    n = len(panel_faces)
    bm.to_mesh(me)
    me.update()
    bm.free()
    shade_smooth(nose)
    log(f"[radome] selective panel faces={n}")
    return n


def build_panel_line_curves(nose):
    """Alternative/additive: create thin grey tube ribbons along tip crease edges as separate mesh.

    These are the visible 'rays' colored #C8CACD. Delete old RadomePanelLines if any.
    """
    old = bpy.data.objects.get("RadomePanelLines")
    if old:
        delete_object(old)

    bm_src = bmesh.new()
    bm_src.from_mesh(nose.data)
    bm_src.edges.ensure_lookup_table()
    tip_y = max(v.co.y for v in bm_src.verts)
    tip_zone = tip_y - 0.9
    mw = nose.matrix_world

    segs = []
    for e in bm_src.edges:
        if len(e.link_faces) != 2:
            continue
        ang = e.link_faces[0].normal.angle(e.link_faces[1].normal)
        if ang < math.radians(20):
            continue
        mid = 0.5 * (e.verts[0].co + e.verts[1].co)
        if mid.y < tip_zone:
            continue
        # world coords
        a = mw @ e.verts[0].co
        b = mw @ e.verts[1].co
        # skip very short
        if (a - b).length < 0.04:
            continue
        segs.append((a, b))
    bm_src.free()

    if not segs:
        log("[radome] no crease segs for tubes")
        return None

    bm = bmesh.new()
    radius = 0.004  # 4mm tube — visible but not white flare
    for a, b in segs:
        # create a thin box along segment (4-sided prism)
        direction = b - a
        length = direction.length
        if length < 1e-6:
            continue
        mid = 0.5 * (a + b)
        # local frame
        y_axis = direction.normalized()
        # pick arbitrary perpendicular
        tmp = Vector((1, 0, 0)) if abs(y_axis.x) < 0.9 else Vector((0, 1, 0))
        x_axis = y_axis.cross(tmp).normalized()
        z_axis = x_axis.cross(y_axis).normalized()
        # 8 verts of a box
        hx = radius
        hz = radius * 0.6
        corners_local = [
            Vector((hx, -length / 2, hz)),
            Vector((-hx, -length / 2, hz)),
            Vector((-hx, -length / 2, -hz)),
            Vector((hx, -length / 2, -hz)),
            Vector((hx, length / 2, hz)),
            Vector((-hx, length / 2, hz)),
            Vector((-hx, length / 2, -hz)),
            Vector((hx, length / 2, -hz)),
        ]
        basis = Matrix((
            (x_axis.x, y_axis.x, z_axis.x),
            (x_axis.y, y_axis.y, z_axis.y),
            (x_axis.z, y_axis.z, z_axis.z),
        ))
        vs = []
        for cl in corners_local:
            vs.append(bm.verts.new(mid + basis @ cl))
        bm.verts.ensure_lookup_table()
        faces_idx = [
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ]
        for fi in faces_idx:
            try:
                bm.faces.new([vs[i] for i in fi])
            except ValueError:
                pass

    me = bpy.data.meshes.new("RadomePanelLines")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("RadomePanelLines", me)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.get("RadomePanel")
    if mat is None:
        mat = bpy.data.materials.new("RadomePanel")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        col = (0xC8 / 255.0, 0xCA / 255.0, 0xCD / 255.0)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*col, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.5
    me.materials.append(mat)
    shade_smooth(obj)
    log(f"[radome] tube lines segs={len(segs)} verts={len(me.vertices)}")
    return obj


def remove_tip_spikes(nose):
    """Delete faces/verts that stick past the main tip envelope (floating horizontal line)."""
    bm = bmesh.new()
    bm.from_mesh(nose.data)
    bm.verts.ensure_lookup_table()
    tip_y = max(v.co.y for v in bm.verts)
    # Main tip cluster: verts within 3cm of tip_y
    tip_verts = [v for v in bm.verts if v.co.y >= tip_y - 0.03]
    if not tip_verts:
        bm.free()
        return 0
    # median XZ radius of tip verts
    rs = [math.hypot(v.co.x, v.co.z) for v in tip_verts]
    rs.sort()
    r_med = rs[len(rs) // 2]
    # spike: near tip_y but radius >> median OR isolated protrusion in +Y beyond dense tip
    kill = []
    for v in bm.verts:
        r = math.hypot(v.co.x, v.co.z)
        if v.co.y > tip_y - 0.02 and r > r_med + 0.08:
            kill.append(v)
        # thin finger: high y, few links, far from axis in one direction
        if v.co.y > tip_y - 0.05 and r > 0.15 and len(v.link_edges) <= 2:
            kill.append(v)
    kill = list(set(kill))
    n = len(kill)
    if kill:
        # delete verts and connected faces
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
        bm.to_mesh(nose.data)
        nose.data.update()
    bm.free()
    shade_smooth(nose)
    log(f"[tip] removed spike verts={n} r_med={r_med:.4f}")
    return n


def clear_sharp_white_highlights(nose):
    """Clear sharp edge flags that can render as bright white lines in EEVEE."""
    me = nose.data
    bm = bmesh.new()
    bm.from_mesh(me)
    n = 0
    for e in bm.edges:
        if e.smooth is False:
            e.smooth = True
            n += 1
    bm.to_mesh(me)
    bm.free()
    # also disable auto smooth angle tricks
    try:
        me.use_auto_smooth = False
    except Exception:
        pass
    shade_smooth(nose)
    log(f"[tip] cleared sharp edges={n}")
    return n


def fix_cabin_inset(cabin, glass):
    """Rebuild cabin fully inside glass bbox, clearly behind panes."""
    if cabin is None or glass is None:
        return
    gv = mesh_world_verts(glass)
    xs = [v.x for v in gv]
    ys = [v.y for v in gv]
    zs = [v.z for v in gv]
    # delete old cabin mesh data
    old_me = cabin.data
    # new box
    cx = 0.5 * (min(xs) + max(xs))
    cz = 0.5 * (min(zs) + max(zs))
    # stay inside openings: smaller than glass span
    tw = min((max(xs) - min(xs)) * 0.45, 1.4)
    th = min((max(zs) - min(zs)) * 0.55, 0.45)
    # Y: fully within glass Y, inset from front
    y0 = min(ys) + 0.05
    y1 = max(ys) - 0.25
    if y1 <= y0:
        y0, y1 = min(ys) - 0.1, min(ys) + 0.4
    cy = 0.5 * (y0 + y1)
    hx, hy, hz = tw * 0.5, 0.5 * abs(y1 - y0), th * 0.5

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=list(bm.verts), vec=(hx * 2, hy * 2, hz * 2))
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx, cy, cz))
    me = bpy.data.meshes.new("CockpitCabin_REF")
    bm.to_mesh(me)
    bm.free()
    cabin.data = me
    if old_me.users == 0:
        bpy.data.meshes.remove(old_me)
    mat = bpy.data.materials.get("REF_CabinDark")
    if mat:
        me.materials.append(mat)
    shade_smooth(cabin)
    log(f"[cabin] rebuilt size=({tw:.2f},{abs(y1-y0):.2f},{th:.2f}) center=({cx:.2f},{cy:.2f},{cz:.2f})")


def expand_glass_upper_rim(glass, mm=4.0):
    """Grow only upper-rim verts slightly along +normal / outward radial (~4mm). No new object."""
    dist = mm / 1000.0
    bm = bmesh.new()
    bm.from_mesh(glass.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    zs = [v.co.z for v in bm.verts]
    z_cut = min(zs) + 0.70 * (max(zs) - min(zs))
    moved = 0
    for v in bm.verts:
        if v.co.z < z_cut:
            continue
        n = Vector((0, 0, 0))
        for f in v.link_faces:
            n += f.normal
        if n.length < 1e-8:
            continue
        n.normalize()
        # mostly expand in XY radial + slight +Z for upper edge coverage
        radial = Vector((v.co.x, 0.0, max(0.0, v.co.z)))
        if radial.length > 1e-6:
            outward = (0.6 * n + 0.4 * radial.normalized()).normalized()
        else:
            outward = n
        v.co += outward * dist
        moved += 1
    bm.to_mesh(glass.data)
    glass.data.update()
    bm.free()
    shade_smooth(glass)
    log(f"[glass] expanded upper rim verts={moved} by {mm}mm")
    return moved


def ensure_glass_mat(glass):
    mat = glass.data.materials[0] if glass.data.materials else None
    if mat is None:
        mat = bpy.data.materials.new("REF_CockpitGlass")
        glass.data.materials.append(mat)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = (0xDD / 255.0, 0xEE / 255.0, 0xEB / 255.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        for key, val in (
            ("Transmission Weight", 1.0),
            ("Transmission", 1.0),
            ("Alpha", 0.32),
            ("IOR", 1.5),
            ("Roughness", 0.02),
            ("Metallic", 0.0),
            ("Specular IOR Level", 0.5),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    try:
        mat.use_screen_refraction = True
    except Exception:
        pass
    try:
        mat.refraction_depth = 0.1
    except Exception:
        pass
    return mat


def hide_extra_floaters():
    """Hide known decorative thin planes if they appear as floaters mid-air in some cams — keep Title/TailMark (they're on tail).

    Hunt objects with no faces near nose tip or wire-like.
    """
    deleted = []
    for obj in list(bpy.data.objects):
        if obj.type != "MESH":
            continue
        me = obj.data
        if len(me.polygons) == 0 and len(me.edges) > 0:
            deleted.append(obj.name)
            delete_object(obj)
            continue
        # WindshieldGapStrip from previous pass — remove (replaced by rim expand)
        if obj.name == "WindshieldGapStrip":
            deleted.append(obj.name)
            delete_object(obj)
    # hide PanelLines etc
    for name in ("PilotSeats", "Fuselage_ORIG", "PanelLines"):
        o = bpy.data.objects.get(name)
        if o:
            o.hide_set(True)
            o.hide_render = True
            o.hide_viewport = True
    log(f"[floaters] deleted {deleted}")
    return deleted


def render_views():
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    # enable refraction if available
    try:
        scene.eevee.use_raytracing = True
    except Exception:
        pass
    try:
        scene.eevee.use_ssr = True
        scene.eevee.use_ssr_refraction = True
    except Exception:
        pass
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.18, 0.19, 0.21, 1.0)
        bg.inputs[1].default_value = 0.85
    if not any(o.type == "LIGHT" and "Finish" in o.name for o in bpy.data.objects):
        ld = bpy.data.lights.new("FinishSun2", "SUN")
        ld.energy = 5.0
        lo = bpy.data.objects.new("FinishSun2", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(50), math.radians(12), math.radians(40))

    fuse = bpy.data.objects.get("Fuselage")
    nose = bpy.data.objects.get("Nose")
    verts = []
    for o in (fuse, nose):
        if o:
            verts.extend(mesh_world_verts(o))
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    y_mid = 0.5 * (min(ys) + max(ys))
    z_mid = 0.5 * (min(zs) + max(zs))
    nose_look = Vector((0.0, 17.8, 0.55))
    full_look = Vector((0.0, y_mid, max(0.5, z_mid)))
    span = max(ys) - min(ys)

    views = {
        "oblique45": (Vector((8.5, nose_look.y + 8.5, 2.0)), nose_look, 45),
        "front": (Vector((0.0, nose_look.y + 13.0, 0.9)), nose_look, 45),
        "full_side": (Vector((span * 1.05, y_mid, z_mid + 0.8)), full_look, 35),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        for o in list(bpy.data.objects):
            if o.name.startswith("FinCam_"):
                bpy.data.objects.remove(o, do_unlink=True)
        cd = bpy.data.cameras.new(f"FinCam_{name}")
        cam = bpy.data.objects.new(f"FinCam_{name}", cd)
        bpy.context.scene.collection.objects.link(cam)
        cam.location = loc
        cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens
        scene.camera = cam
        out = os.path.join(PREV, f"{name}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        paths.append(out)
        log(f"[render] {out}")
        bpy.data.objects.remove(cam, do_unlink=True)
    return paths


def main():
    open(os.path.join(LOG, "console_fix2.txt"), "w").close()
    log("=== FINISH FIX2 ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    nose = bpy.data.objects.get("Nose")
    glass = bpy.data.objects.get("CockpitGlass_REF")
    cabin = bpy.data.objects.get("CockpitCabin")

    deleted = hide_extra_floaters()
    clear_sharp_white_highlights(nose)
    spikes = remove_tip_spikes(nose)

    reset_nose_materials(nose)
    n_panel = assign_radome_rays_selective(nose)
    tubes = build_panel_line_curves(nose)

    ensure_glass_mat(glass)
    expand_glass_upper_rim(glass, mm=4.0)
    fix_cabin_inset(cabin, glass)

    # export
    if os.path.isfile(GLB):
        shutil.copy2(GLB, GLB + ".bak-nose-finish")
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
    )
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    size = os.path.getsize(GLB)
    log(f"GLB {size} ({size/1e6:.2f} MB)")
    paths = render_views()

    # update notes
    notes = os.path.join(ROOT, "scripts", "NOSE_FINISH_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# 机头收尾（finish）\n\n")
        f.write("## 1. 玻璃 / 驾驶舱\n")
        f.write("- CockpitGlass_REF: Transmission=1.0, Alpha≈0.32, IOR=1.5, Rough=0.02, Base #DDEEEB, BLEND/BLENDED\n")
        f.write("- CockpitCabin: 已重建为更小内嵌暗盒，避免穿出风挡\n")
        f.write("- 上沿：玻璃上缘顶点外扩 ~4mm（不改整体窗形），并删除上一轮穿出的 WindshieldGapStrip\n\n")
        f.write("## 2. 漂浮细线\n")
        f.write("- 删除前清单见 `_nose_finish_logs/floater_inventory_before.json`\n")
        f.write("- 无独立 edges-only 物体；嫌疑薄片为 TailMark/Title（机尾字标，未删）\n")
        f.write(f"- fix2 删除: {deleted}\n")
        f.write(f"- Nose 尖端尖刺顶点删除: {spikes}；清除 sharp 边高光\n")
        f.write("- 雷达罩十字板线保留，改用 #C8CACD 细管 + 少量折面\n\n")
        f.write("## 3. 风挡上沿黑缝\n")
        f.write("- 采用玻璃上缘外扩 4mm；去掉会穿出的遮挡条\n\n")
        f.write("## 4. 登机门\n")
        f.write("- 已删机身 Doors 前舱门岛（yc≈14.42 与 13.05，左右）；保留 REF 机头上门与机身中/后舱门\n")
        f.write("- 同步裁剪 DoorFrames / DoorWindows 对应前段\n\n")
        f.write("## 5. 雷达罩板线\n")
        f.write(f"- 折面选材（收紧）faces={n_panel}；另建 RadomePanelLines 细管 #C8CACD\n\n")
        f.write("## 6. 导出\n")
        f.write(f"- GLB {size/1e6:.2f} MB；备份 `.bak-nose-finish`\n")
        f.write("- EEVEE 预览: `public/models/nose-finish/{oblique45,front,full_side}.png`\n\n")
        f.write("## 诚实差距\n")
        f.write("- 若仍有白线，可能是法线高光而非网格；已尽量清 sharp / 尖刺\n")
        f.write("- EEVEE 透射观感依赖屏幕空间折射，Three.js 里以 Alpha/Transmission 为准\n")
        f.write("- 机头门与原 Doors 去重靠 Y 岛删除，若 REF 门仅是蒙皮线而不是凹门，前舱门会偏扁\n")
    log(f"notes -> {notes}")
    log("=== DONE FIX2 ===")


if __name__ == "__main__":
    main()

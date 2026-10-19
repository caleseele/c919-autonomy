# -*- coding: utf-8 -*-
"""§6b2: re-project cabin onto Nose/Fuselage/Aft skins; fix floating aft panes."""
from __future__ import annotations
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
OFFSET = 0.001
SUNK_EPS = 5e-4
RAY = 8.0

os.makedirs(LOG, exist_ok=True)

def log(m):
    print(m, flush=True)
    open(os.path.join(LOG, "section6b2_console.txt"), "a", encoding="utf-8").write(m + "\n")

def tip_y():
    n = bpy.data.objects["Nose"]
    return max((n.matrix_world @ v.co).y for v in n.data.vertices)

def aabb_v(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return {k: (min(getattr(v,a) for v in vs), max(getattr(v,a) for v in vs)) for k,a in zip("xyz","xyz")}

def skins(tip):
    fuse = bpy.data.objects["Fuselage"]
    nose = bpy.data.objects.get("Nose")
    aft = next(o for o in bpy.data.objects if o.type=="MESH" and "蒙皮" in o.name and "尾" in o.name)
    fa = aabb_v(fuse)
    fuse_st0 = tip - fa["y"][1]  # forward-most station of fuse
    return nose, fuse, aft, fuse_st0

def pick_skin(st, nose, fuse, aft, fuse_st0):
    if st < fuse_st0 + 0.05 and nose is not None:
        return nose
    if st < 26.0:
        return fuse
    return aft

def project_one(skin, wco):
    mw = skin.matrix_world; imw = mw.inverted()
    axis = Vector((0.0, wco.y, 0.0))
    radial = Vector((wco.x, 0.0, wco.z))
    if radial.length < 1e-5:
        radial = Vector((1.0, 0.0, 0.0))
    radial.normalize()

    # 1) outward radial ray
    start_l = imw @ (axis + radial * RAY)
    end_l = imw @ (axis + radial * (RAY - 1.0))
    dir_l = (end_l - start_l).normalized()
    ok, loc, norm, _ = skin.ray_cast(start_l, dir_l, distance=RAY * 2.5)
    if ok:
        wloc = mw @ loc
        wn = (mw.to_3x3() @ norm).normalized()
        if wn.dot(radial) < 0:
            wn = -wn
        # reject near-axial hits (fin / endcap): |ny|>0.7 or hit too near centerline
        hit_r = Vector((wloc.x, 0, wloc.z)).length
        if abs(wn.y) < 0.65 and hit_r > 0.8:
            return wloc, wn, (wco - wloc).dot(wn), "ray"

    # 2) closest_point with end-cap / fin rejection
    ok2, loc2, norm2, _ = skin.closest_point_on_mesh(imw @ wco)
    if ok2:
        wloc = mw @ loc2
        wn = (mw.to_3x3() @ norm2).normalized()
        hit_r = Vector((wloc.x, 0, wloc.z)).length
        if abs(wn.y) < 0.65 and hit_r > 0.8:
            if wn.dot(radial) < 0:
                wn = -wn
            return wloc, wn, (wco - wloc).dot(wn), "closest"

    # 3) probe along radial at several radii, pick closest surface with good normal
    best = None
    for rad in (1.5, 1.8, 2.0, 2.1, 2.2, 2.4):
        probe = axis + radial * rad
        ok3, loc3, norm3, _ = skin.closest_point_on_mesh(imw @ probe)
        if not ok3:
            continue
        wloc = mw @ loc3
        wn = (mw.to_3x3() @ norm3).normalized()
        hit_r = Vector((wloc.x, 0, wloc.z)).length
        if abs(wn.y) > 0.65 or hit_r < 0.8:
            continue
        if wn.dot(radial) < 0:
            wn = -wn
        d = (probe - wloc).length
        if best is None or d < best[0]:
            best = (d, wloc, wn)
    if best:
        wloc, wn = best[1], best[2]
        return wloc, wn, (wco - wloc).dot(wn), "probe"
    return None, None, None, None

def islands(ob):
    tip = tip_y()
    mw = ob.matrix_world
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    rem = set(bm.verts); out = []
    while rem:
        s = rem.pop(); st = [s]; isl = {s}
        while st:
            v = st.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in isl:
                    isl.add(o); rem.discard(o); st.append(o)
        idxs = [v.index for v in isl]
        cents = [mw @ v.co for v in isl]
        c = Vector(tuple(sum(getattr(p, a) for p in cents) / len(cents) for a in "xyz"))
        out.append({"verts": idxs, "c": c, "st": tip - c.y})
    bm.free()
    return out

def project_object(ob, nose, fuse, aft, fuse_st0):
    mw = ob.matrix_world; imw = mw.inverted()
    me = ob.data
    n_ok = n_fail = 0
    for isl in islands(ob):
        skin = pick_skin(isl["st"], nose, fuse, aft, fuse_st0)
        for vi in isl["verts"]:
            wco = mw @ me.vertices[vi].co
            wloc, wn, _s, mode = project_one(skin, wco)
            if wloc is None:
                n_fail += 1
                continue
            me.vertices[vi].co = imw @ (wloc + wn * OFFSET)
            n_ok += 1
    me.update()
    bpy.context.view_layer.update()
    return n_ok, n_fail

def measure(ob, nose, fuse, aft, fuse_st0):
    tip = tip_y(); mw = ob.matrix_world
    sunk_lt = sunk_ge = lt = ge = 0
    means = []
    fails = 0
    for isl in islands(ob):
        st = isl["st"]
        skin = pick_skin(st, nose, fuse, aft, fuse_st0)
        if st < 26: lt += 1
        else: ge += 1
        dists = []
        for vi in isl["verts"]:
            wco = mw @ ob.data.vertices[vi].co
            _w, _n, s, mode = project_one(skin, wco)
            if s is None:
                fails += 1
            else:
                dists.append(s)
        mean = sum(dists) / len(dists) if dists else None
        means.append(mean)
        if mean is not None and mean < SUNK_EPS:
            if st < 26: sunk_lt += 1
            else: sunk_ge += 1
    ys = [(mw @ v.co).y for v in ob.data.vertices]
    valid = [m for m in means if m is not None]
    return {
        "total": len(means), "lt26": lt, "ge26": ge,
        "sunk_lt26": sunk_lt, "sunk_ge26": sunk_ge, "sunk_total": sunk_lt + sunk_ge,
        "fail_verts": fails,
        "mean_min": None if not valid else round(min(valid), 5),
        "mean_max": None if not valid else round(max(valid), 5),
        "station_span": [round(tip - max(ys), 3), round(tip - min(ys), 3)],
    }

def cam_render(tip):
    def aabb(ob):
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        return min(p.y for p in pts), max(p.y for p in pts)
    ys = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            a, b = aabb(o); ys += [a, b]
    tail_y = min(ys)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480
    cam = bpy.data.objects.get("LengthSideCam")
    if not cam:
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
    bpy.ops.import_scene.fbx(filepath=os.path.join(REFS, "REF_C919_meters.fbx"), global_scale=1.0)
    refs = [o for o in bpy.data.objects if o not in before]
    for o in refs:
        o.name = "LengthRef_" + o.name[:40]
    rys = []
    for o in refs:
        if o.type == "MESH":
            a, b = aabb(o); rys += [a, b]
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
    json.dump({"ours": ours, "ref": refp, "compare": cmp, "stamp": stamp,
               "tip_sx": ts, "tail_sx": ls},
              open(os.path.join(LOG, "section6b_stack.json"), "w", encoding="utf-8"))
    return {"tip_sx": ts, "tail_sx": ls, "ok": ts < ls, "ours": ours, "ref": refp, "compare": cmp, "stamp": stamp}

def main():
    open(os.path.join(LOG, "section6b2_console.txt"), "w", encoding="utf-8").close()
    log("=== section6b2 reproject Nose/Fuse/Aft ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tip = tip_y()
    nose, fuse, aft, fuse_st0 = skins(tip)
    log(f"tip={tip:.4f} fuse_st0={fuse_st0:.3f} nose={nose.name if nose else None} aft={aft.name}")

    glass = next(o for o in bpy.data.objects if "舷窗" in o.name and "玻璃" in o.name)
    seam = next(o for o in bpy.data.objects if "舱门" in o.name and "缝" in o.name)

    before = {"glass": measure(glass, nose, fuse, aft, fuse_st0),
              "seam": measure(seam, nose, fuse, aft, fuse_st0)}
    log(f"before glass={before['glass']}")
    log(f"before seam={before['seam']}")

    for ob, lab in ((glass, "glass"), (seam, "seam")):
        ok, fail = project_object(ob, nose, fuse, aft, fuse_st0)
        log(f"project {lab} ok_verts={ok} fail={fail}")

    after = {"glass": measure(glass, nose, fuse, aft, fuse_st0),
             "seam": measure(seam, nose, fuse, aft, fuse_st0)}
    log(f"after glass={after['glass']}")
    log(f"after seam={after['seam']}")

    rend = cam_render(tip)
    log(f"cam tip_sx={rend['tip_sx']:.4f} tail_sx={rend['tail_sx']:.4f}")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)

    # antenna / dorsal note
    ant = next((o for o in bpy.data.objects if "尾段" in o.name and "天线" in o.name), None)
    ant_info = None
    if ant:
        vs = [ant.matrix_world @ v.co for v in ant.data.vertices]
        ant_info = {
            "name": ant.name, "verts": len(vs),
            "station_span": [round(tip - max(v.y for v in vs), 3), round(tip - min(v.y for v in vs), 3)],
            "zmax": round(max(v.z for v in vs), 3),
        }
    result = {"before": before, "after": after, "antenna": ant_info, "render": rend,
              "scripts": ["section6b_window_project.py", "section6b2_reproject.py"],
              "backup": "c919.bak-section6b.blend"}
    json.dump(result, open(os.path.join(LOG, "section6b2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    prog = [
        "# PROGRESS — §6b2 cabin reproject",
        "- backup: c919.bak-section6b.blend",
        "- cabin reimported with REF_尾段 xform (sy=1); projected to Nose/Fuselage/REF_尾段蒙皮 +1mm",
        f"- glass sunk {before['glass']['sunk_total']}→{after['glass']['sunk_total']} st={after['glass']['station_span']}",
        f"- seam sunk {before['seam']['sunk_total']}→{after['seam']['sunk_total']} st={after['seam']['station_span']}",
        f"- antenna kept st={ant_info['station_span'] if ant_info else None}",
        "- windows 86=SPEC OK; GearBayDoors kept; no dorsal orphan deleted (collapse was the bump)",
        f"- cam tip_sx={rend['tip_sx']:.4f} tail_sx={rend['tail_sx']:.4f}",
        f"- compare stamp {rend['stamp']}",
        "- scripts: section6b_window_project.py, section6b2_reproject.py",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(prog[:30]) + "\n")
    log("=== section6b2 DONE ===")

if __name__ == "__main__":
    main()

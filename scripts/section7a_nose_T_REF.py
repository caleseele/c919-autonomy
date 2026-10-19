# -*- coding: utf-8 -*-
"""§7a: reimport nose+details under T_REF, correct dependents, resume weld→glb.

  blender -b --factory-startup -P scripts/section7a_nose_T_REF.py
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
from mathutils import Matrix, Vector, kdtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
REFS = os.path.join(ROOT, "refs")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "section7")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
BAK_BEFORE = os.path.join(OUT, "c919.bak-before-s7a-nose.blend")

SX = 1.0475227637527205
SY = 1.0
SZ = 1.0104343689231436
DX = 0.0
DY = 15.463823181152343
DZ = -4.239782612001511
TARGET_CUT_Y = -5.427176818847657
REF_CUT_Y_IMPORTED = 20.891
OBJ_FRONT_CUT_Y = 0.5

os.makedirs(LOG, exist_ok=True)
os.makedirs(PREV, exist_ok=True)
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(os.path.join(LOG, "section7a_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]


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


def aabb_overlap(a, b):
    return not (
        a["xmax"] < b["xmin"] or b["xmax"] < a["xmin"]
        or a["ymax"] < b["ymin"] or b["ymax"] < a["ymin"]
        or a["zmax"] < b["zmin"] or b["zmax"] < a["zmin"]
    )


def apply_mw(ob):
    ob.data.transform(ob.matrix_world)
    ob.data.update()
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


def t_ref_matrix():
    R = Matrix.Rotation(math.pi, 4, "Z")
    S = Matrix.Diagonal((SX, SY, SZ, 1.0))
    T = Matrix.Translation(Vector((DX, DY, DZ)))
    return T @ S @ R


def apply_t_ref(ob):
    apply_mw(ob)
    ob.data.transform(t_ref_matrix())
    ob.data.update()
    ob.matrix_world = Matrix.Identity(4)


def find_ref(*parts):
    for fn in os.listdir(REFS):
        if not fn.endswith(".obj"):
            continue
        if all(p in fn for p in parts):
            return os.path.join(REFS, fn)
    raise FileNotFoundError(str(parts))


def tip_y():
    for n in ("REF_机头蒙皮", "Fuselage_REF", "Nose"):
        ob = bpy.data.objects.get(n)
        if ob and ob.type == "MESH":
            return max(v.y for v in mwv(ob))
    raise RuntimeError("no tip")


def cut_world_y(obj_y: float) -> float:
    return (t_ref_matrix() @ Vector((0.0, obj_y, 0.0))).y


def band_verts(ob, y_world, tol=0.01):
    return [v for v in mwv(ob) if abs(v.y - y_world) <= tol]


def end_ring(ob, which, depth=0.02):
    vs = mwv(ob)
    if which == "min":
        y0 = min(v.y for v in vs)
        return [v for v in vs if v.y <= y0 + depth]
    y0 = max(v.y for v in vs)
    return [v for v in vs if v.y >= y0 - depth]


def max_hausdorff(a, b):
    if len(a) < 3 or len(b) < 3:
        return None, len(a), len(b)
    kd = kdtree.KDTree(len(b))
    for i, p in enumerate(b):
        kd.insert(p, i)
    kd.balance()
    d1 = max(kd.find(p)[2] for p in a)
    kd2 = kdtree.KDTree(len(a))
    for i, p in enumerate(a):
        kd2.insert(p, i)
    kd2.balance()
    d2 = max(kd2.find(p)[2] for p in b)
    return max(d1, d2), len(a), len(b)


def cut_deviation(ob_a, ob_b, y_world, tol=0.01):
    a = band_verts(ob_a, y_world, tol)
    b = band_verts(ob_b, y_world, tol)
    # fallback end-ring if band empty on one side
    if len(a) < 3:
        a = end_ring(ob_a, "min" if aabb(ob_a)["ymin"] < y_world else "max", 0.03)
    if len(b) < 3:
        b = end_ring(ob_b, "max" if aabb(ob_b)["ymax"] > y_world - 0.05 else "min", 0.03)
    mx, na, nb = max_hausdorff(a, b)
    return {
        "y_world": y_world,
        "tol": tol,
        "n_a": na,
        "n_b": nb,
        "max_m": mx,
        "max_mm": None if mx is None else mx * 1000.0,
    }


def record_mats(ob):
    rows = []
    if not ob or ob.type != "MESH":
        return rows
    for i, m in enumerate(ob.data.materials):
        if not m:
            continue
        info = {"slot": i, "name": m.name, "blend": getattr(m, "blend_method", None)}
        if m.use_nodes:
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                def g(k):
                    if k not in bsdf.inputs:
                        return None
                    v = bsdf.inputs[k].default_value
                    try:
                        return list(v)
                    except TypeError:
                        return float(v)
                info["base"] = g("Base Color")
                info["metallic"] = g("Metallic")
                info["roughness"] = g("Roughness")
                info["alpha"] = g("Alpha")
                info["ior"] = g("IOR")
                for tk in ("Transmission Weight", "Transmission"):
                    if tk in bsdf.inputs:
                        info["transmission"] = g(tk)
                        info["transmission_key"] = tk
                        break
        rows.append(info)
    return rows


def ensure_mat_from_rec(rec, fallback_name=None):
    name = rec.get("name") or fallback_name or "Mat"
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if rec.get("base"):
            bsdf.inputs["Base Color"].default_value = tuple(rec["base"][:3]) + (1.0,)
        if rec.get("metallic") is not None and "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = rec["metallic"]
        if rec.get("roughness") is not None:
            bsdf.inputs["Roughness"].default_value = rec["roughness"]
        if rec.get("alpha") is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = rec["alpha"]
        if rec.get("ior") is not None and "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = rec["ior"]
        tk = rec.get("transmission_key")
        if tk and rec.get("transmission") is not None and tk in bsdf.inputs:
            bsdf.inputs[tk].default_value = rec["transmission"]
    if rec.get("blend"):
        m.blend_method = rec["blend"]
    return m


def assign_mats(ob, recs):
    if not recs:
        return
    ob.data.materials.clear()
    for r in recs:
        ob.data.materials.append(ensure_mat_from_rec(r))


def ensure_mat(name, color, metallic, roughness, transmission=None, alpha=None, blend=None):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if transmission is not None:
            for key in ("Transmission Weight", "Transmission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = transmission
                    break
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if transmission and "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.5
    if blend:
        m.blend_method = blend
    return m


def find_white_mat():
    for n in ("Skin", "REF_尾段蒙皮_含垂尾", "REF_中机身蒙皮", "Fuselage_REF"):
        if n in bpy.data.materials:
            return bpy.data.materials[n]
        ob = bpy.data.objects.get(n)
        if ob and ob.type == "MESH" and ob.data.materials:
            return ob.data.materials[0]
    return ensure_mat("FuselageWhite_S7", (0.85, 0.85, 0.87), 0.0, 0.35)


def fit_similarity(src_pts, dst_pts):
    """Fit C (4x4) mapping src→dst using Umeyama similarity (R,s,t)."""
    n = min(len(src_pts), len(dst_pts))
    # sample up to 2000 corresponding indices
    step = max(1, n // 2000)
    idxs = list(range(0, n, step))
    S = [src_pts[i] for i in idxs]
    D = [dst_pts[i] for i in idxs]
    n = len(S)
    cs = Vector((sum(p.x for p in S) / n, sum(p.y for p in S) / n, sum(p.z for p in S) / n))
    cd = Vector((sum(p.x for p in D) / n, sum(p.y for p in D) / n, sum(p.z for p in D) / n))
    # variance
    var_s = sum((p - cs).length_squared for p in S) / n
    # covariance 3x3
    cov = Matrix.Diagonal((0.0, 0.0, 0.0)).to_3x3()
    # build manually
    c00 = c01 = c02 = c10 = c11 = c12 = c20 = c21 = c22 = 0.0
    for a, b in zip(S, D):
        x, y, z = (a - cs).xyz if hasattr((a - cs), "xyz") else (a - cs)
        # Vector subtract
        da = a - cs
        db = b - cd
        c00 += db.x * da.x; c01 += db.x * da.y; c02 += db.x * da.z
        c10 += db.y * da.x; c11 += db.y * da.y; c12 += db.y * da.z
        c20 += db.z * da.x; c21 += db.z * da.y; c22 += db.z * da.z
    cov = Matrix(((c00 / n, c01 / n, c02 / n),
                  (c10 / n, c11 / n, c12 / n),
                  (c20 / n, c21 / n, c22 / n)))
    # SVD via Blender mathutils if available; else use translation-only fallback
    try:
        U, s_vals, V = cov.svd()
        # R = U @ V^T with reflection fix
        R = U @ V.transposed()
        if R.determinant() < 0:
            U_fix = Matrix((U[0], U[1], -U[2]))
            # rebuild: flip last column of U
            Ucol = Matrix(((U[0][0], U[0][1], -U[0][2]),
                           (U[1][0], U[1][1], -U[1][2]),
                           (U[2][0], U[2][1], -U[2][2])))
            R = Ucol @ V.transposed()
            s_vals = (s_vals[0], s_vals[1], -s_vals[2]) if hasattr(s_vals, "__getitem__") else s_vals
        scale = 1.0
        if var_s > 1e-12:
            # trace(diag(s) @ d) / var
            # approximate scale from singular values sum
            try:
                tr = s_vals[0] + s_vals[1] + s_vals[2]
            except Exception:
                tr = sum(s_vals)
            scale = tr / var_s
        t = cd - scale * (R @ cs)
        C = Matrix.Translation(t) @ Matrix.Diagonal((scale, scale, scale, 1.0)) @ R.to_4x4()
        return C, {"scale": scale, "method": "umeyama", "n": n}
    except Exception as e:
        # translation + uniform scale from tip/cut only
        log(f"[fit] svd failed ({e}); translation+scale fallback")
        # scale from bounding diagonal
        def span(pts):
            xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
            return Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
        ss, sd = span(S), span(D)
        scales = []
        for i in range(3):
            if abs(ss[i]) > 1e-6:
                scales.append(sd[i] / ss[i])
        sc = sum(scales) / len(scales) if scales else 1.0
        t = cd - sc * cs
        C = Matrix.Translation(t) @ Matrix.Diagonal((sc, sc, sc, 1.0))
        return C, {"scale": sc, "method": "scale_translate", "n": n, "error": str(e)}


def fit_affine_ls(src_pts, dst_pts):
    """Least-squares affine 3x4: dst = A @ src_h. Prefer when topology matches."""
    n = min(len(src_pts), len(dst_pts))
    step = max(1, n // 3000)
    idxs = list(range(0, n, step))
    # Solve for each row of A independently via normal equations is heavy in pure py;
    # use similarity if n large. For exact same topology + linear xform, 4 points suffice.
    # Use 8 well-spread points for exact linear solve of affine.
    # Pick extremes
    S = [src_pts[i] for i in idxs]
    D = [dst_pts[i] for i in idxs]
    # Build overdetermined system with numpy if present
    try:
        import numpy as np
        X = np.array([[p.x, p.y, p.z, 1.0] for p in S], dtype=float)
        Y = np.array([[p.x, p.y, p.z] for p in D], dtype=float)
        # Y = X @ A.T  => A.T = lstsq(X, Y)
        AT, residuals, rank, sing = np.linalg.lstsq(X, Y, rcond=None)
        A = AT.T  # 3x4
        C = Matrix((
            (A[0, 0], A[0, 1], A[0, 2], A[0, 3]),
            (A[1, 0], A[1, 1], A[1, 2], A[1, 3]),
            (A[2, 0], A[2, 1], A[2, 2], A[2, 3]),
            (0.0, 0.0, 0.0, 1.0),
        ))
        # residual rms
        pred = X @ AT
        err = float(np.sqrt(np.mean(np.sum((pred - Y) ** 2, axis=1))))
        return C, {"method": "affine_ls", "n": len(S), "rms_m": err, "rank": int(rank)}
    except Exception as e:
        log(f"[fit] numpy affine failed: {e}")
        return fit_similarity(src_pts, dst_pts)


def apply_matrix_to_mesh(ob, M):
    apply_mw(ob)
    ob.data.transform(M)
    ob.data.update()
    ob.matrix_world = Matrix.Identity(4)


def weld_fuselage(nose, mid, aft, front_y, aft_y):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in (nose, mid, aft):
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = nose
    bpy.ops.object.join()
    fus = bpy.context.view_layer.objects.active
    fus.name = "Fuselage_REF"
    if fus.data:
        fus.data.name = "Fuselage_REF"
    apply_mw(fus)

    bm = bmesh.new()
    bm.from_mesh(fus.data)
    bm.verts.ensure_lookup_table()
    ring = [v for v in bm.verts if abs(v.co.y - front_y) < 0.06 or abs(v.co.y - aft_y) < 0.06]
    if ring:
        bmesh.ops.remove_doubles(bm, verts=ring, dist=0.001)
    bm.to_mesh(fus.data)
    fus.data.update()
    bm.free()

    for p in fus.data.polygons:
        p.use_smooth = True
    bpy.ops.object.select_all(action="DESELECT")
    fus.select_set(True)
    bpy.context.view_layer.objects.active = fus
    if hasattr(bpy.ops.object, "shade_auto_smooth"):
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(30.0))
        except Exception:
            bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_smooth()
        if hasattr(fus.data, "use_auto_smooth"):
            fus.data.use_auto_smooth = True
            fus.data.auto_smooth_angle = math.radians(30.0)
    return fus


def gear_bay_decision(fuse):
    gbd = bpy.data.objects.get("GearBayDoors")
    if not gbd:
        return {"name": "GearBayDoors", "action": "absent", "reason": "not in scene"}
    ga = aabb(gbd)
    overlapped = []
    for n in ("REF_前起落架", "REF_主起落架"):
        ob = bpy.data.objects.get(n)
        if ob and aabb_overlap(ga, aabb(ob)):
            overlapped.append(n)
    imw = fuse.matrix_world.inverted()
    mw = fuse.matrix_world
    dists = []
    vs = mwv(gbd)
    step = max(1, len(vs) // 40)
    for v in vs[::step]:
        ok, loc, norm, _ = fuse.closest_point_on_mesh(imw @ v)
        if ok:
            dists.append((v - (mw @ loc)).length)
    mean_d = sum(dists) / len(dists) if dists else 999.0
    max_d = max(dists) if dists else 999.0
    on_surface = mean_d < 0.05 and max_d < 0.12
    if overlapped or not on_surface:
        delete_object("GearBayDoors")
        return {
            "name": "GearBayDoors", "action": "deleted",
            "reason": f"overlap={overlapped}; mean_d={mean_d:.4f} max_d={max_d:.4f} on_surface={on_surface}",
            "overlap": overlapped, "mean_d": mean_d, "max_d": max_d,
        }
    return {
        "name": "GearBayDoors", "action": "kept",
        "reason": f"no gear overlap; mean_d={mean_d:.4f} max_d={max_d:.4f}",
        "mean_d": mean_d, "max_d": max_d,
    }


def measure_stations(tip):
    items = []

    def add(name, ours, ref, tol):
        d = None if ours is None else ours - ref
        ok = d is not None and abs(d) <= tol
        items.append({
            "项目": name,
            "实测": None if ours is None else round(ours, 3),
            "参考": ref,
            "差值": None if d is None else round(d, 3),
            "是否通过": "是" if ok else "否",
        })

    aft = min(aabb(o)["ymin"] for o in bpy.data.objects if o.type == "MESH" and not o.hide_get())
    add("全长", tip - aft, 38.84, 0.10)

    wing_le = None
    for n in ("REF_机翼_左", "REF_机翼_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        vs = mwv(ob)
        root = [v for v in vs if abs(v.x) < 2.5] or vs
        le = tip - max(v.y for v in root)
        wing_le = le if wing_le is None else min(wing_le, le)
    add("翼根前缘", wing_le, 13.18, 0.25)

    nac_le = None
    for n in ("REF_发动机_左", "REF_发动机_右"):
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        le = tip - aabb(ob)["ymax"]
        nac_le = le if nac_le is None else min(nac_le, le)
    add("短舱前缘", nac_le, 12.27, 0.25)

    main = bpy.data.objects.get("REF_主起落架")
    main_st = track = None
    if main:
        vs = mwv(main)
        zmin = min(v.z for v in vs)
        wheels = [v for v in vs if v.z < zmin + 0.35] or [v for v in vs if v.z < zmin + 0.8]
        if wheels:
            main_st = tip - sum(v.y for v in wheels) / len(wheels)
            left = [v for v in wheels if v.x < -0.5]
            right = [v for v in wheels if v.x > 0.5]
            if left and right:
                track = abs(sum(v.x for v in right) / len(right) - sum(v.x for v in left) / len(left))
            else:
                track = max(v.x for v in wheels) - min(v.x for v in wheels)
    add("主轮中心", main_st, 17.58, 0.30)
    add("主轮轮距", track, 6.83, 0.30)

    nose_g = bpy.data.objects.get("REF_前起落架")
    nose_st = None
    if nose_g:
        vs = mwv(nose_g)
        zmin = min(v.z for v in vs)
        wheels = [v for v in vs if v.z < zmin + 0.35] or vs
        nose_st = tip - sum(v.y for v in wheels) / len(wheels)
    add("前轮中心", nose_st, 5.18, 0.30)

    skin = bpy.data.objects.get("Fuselage_REF") or bpy.data.objects.get("REF_尾段蒙皮_含垂尾")
    vt_le = None
    if skin:
        vs = mwv(skin)
        fin = [v for v in vs if v.z > 1.5 and abs(v.x) < 0.8]
        if fin:
            zmin_f = min(v.z for v in fin)
            root = [v for v in fin if v.z < zmin_f + 1.2]
            if root:
                vt_le = tip - max(v.y for v in root)
    add("垂尾根部前缘", vt_le, 31.46, 0.20)
    return items


def stack_images(top_path, bot_path, out_path):
    try:
        from PIL import Image
        t = Image.open(top_path).convert("RGB")
        b = Image.open(bot_path).convert("RGB")
        w = min(1280, max(t.width, b.width))

        def resize(im):
            if im.width == w:
                return im
            h = int(im.height * (w / im.width))
            return im.resize((w, h), Image.Resampling.LANCZOS)

        t, b = resize(t), resize(b)
        out = Image.new("RGB", (w, t.height + b.height), (30, 30, 30))
        out.paste(t, (0, 0))
        out.paste(b, (0, t.height))
        out.save(out_path)
        log(f"[collage] PIL {out_path} {out.size}")
        return True
    except Exception as e:
        log(f"[collage] PIL failed: {e}")
        shutil.copy2(top_path, out_path)
        return False


def render_collage(tip):
    ys = []
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_get():
            a = aabb(o)
            ys += [a["ymin"], a["ymax"]]
    tail = min(ys)
    ymid = 0.5 * (tip + tail)
    zmid = 0.0
    fus = bpy.data.objects.get("Fuselage_REF")
    if fus:
        a = aabb(fus)
        zmid = 0.5 * (a["zmin"] + a["zmax"])

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 480

    cam = bpy.data.objects.get("S7Cam")
    if cam is None:
        data = bpy.data.cameras.new("S7Cam")
        cam = bpy.data.objects.new("S7Cam", data)
        bpy.context.collection.objects.link(cam)
    scene.camera = cam
    tip_pt = Vector((0.0, tip, zmid))
    tail_pt = Vector((0.0, tail, zmid))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # side ortho
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 38.84 * 1.15
    ts = ls = 0.0
    ok1 = False
    for loc, rot in (
        (Vector((-80.0, ymid, zmid)), (math.pi / 2, 0.0, -math.pi / 2)),
        (Vector((80.0, ymid, zmid)), (math.pi / 2, 0.0, math.pi / 2)),
    ):
        cam.location = loc
        cam.rotation_euler = rot
        bpy.context.view_layer.update()
        ts = world_to_camera_view(scene, cam, tip_pt).x
        ls = world_to_camera_view(scene, cam, tail_pt).x
        log(f"[cam-side] tip_sx={ts:.4f} tail_sx={ls:.4f}")
        if ts < ls:
            ok1 = True
            break
    side_path = os.path.join(PREV, f"side_{stamp}.png")
    scene.render.filepath = side_path
    bpy.ops.render.render(write_still=True)

    # 45°
    cam.data.type = "PERSP"
    cam.data.lens = 50
    ok2 = False
    ts2 = ls2 = 0.0
    dist = 70.0
    for sign in (-1.0, 1.0):
        loc = Vector((
            sign * dist * math.sin(math.radians(45)),
            ymid + dist * math.cos(math.radians(45)) * 0.35,
            zmid + 8.0,
        ))
        direction = Vector((0.0, ymid, zmid)) - loc
        cam.location = loc
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        ts2 = world_to_camera_view(scene, cam, tip_pt).x
        ls2 = world_to_camera_view(scene, cam, tail_pt).x
        log(f"[cam-45] sign={sign} tip_sx={ts2:.4f} tail_sx={ls2:.4f}")
        if ts2 < ls2:
            ok2 = True
            break
    ang_path = os.path.join(PREV, f"ang45_{stamp}.png")
    scene.render.filepath = ang_path
    bpy.ops.render.render(write_still=True)

    coll_name = f"collage_{stamp}.png"
    coll_path = os.path.join(PREV, coll_name)
    stack_images(side_path, ang_path, coll_path)
    return {
        "stamp": stamp,
        "side": side_path,
        "ang45": ang_path,
        "collage": coll_path,
        "collage_name": coll_name,
        "side_tip_sx": ts,
        "side_tail_sx": ls,
        "side_ok": ok1,
        "ang_tip_sx": ts2,
        "ang_tail_sx": ls2,
        "ang_ok": ok2,
    }


def export_glb():
    bpy.ops.object.select_all(action="DESELECT")
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.hide_get() or o.hide_render:
            continue
        o.select_set(True)
        n += 1
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
    log(f"[glb] {n} meshes → {GLB}")
    return n


def resolve_name(*cands):
    for n in cands:
        if bpy.data.objects.get(n):
            return n
    return None


def main():
    open(os.path.join(LOG, "section7a_console.txt"), "w", encoding="utf-8").close()
    log("=== §7a nose T_REF reimport + resume weld ===")

    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    shutil.copy2(BLEND, BAK_BEFORE)
    log(f"[bak] → {BAK_BEFORE}")
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # --- 1. record ---
    role_map = {
        "skin": resolve_name("REF_机头蒙皮", "Nose"),
        "glass": resolve_name("CockpitGlass_REF", "REF_风挡玻璃"),
        "frame": resolve_name("REF_风挡窗框", "REF_WindshieldFrame"),
        "wipers": resolve_name("REF_雨刮器", "REF_Wipers"),
        "probes": resolve_name("REF_探头天线", "REF_ProbesAntennas"),
        "interior": resolve_name("REF_驾驶舱内饰", "REF_CockpitInterior"),
    }
    log(f"[roles] {role_map}")
    records = {}
    for role, name in role_map.items():
        ob = bpy.data.objects.get(name) if name else None
        records[role] = {
            "scene_name": name,
            "mats": record_mats(ob),
            "mw": [list(r) for r in ob.matrix_world] if ob else None,
            "verts": len(ob.data.vertices) if ob and ob.type == "MESH" else 0,
        }
    skin_name = role_map["skin"]
    skin_ob = bpy.data.objects[skin_name]
    M_old_nose = skin_ob.matrix_world.copy()
    # snapshot old skin for correspondence fit (baked geometry)
    old_skin = skin_ob.copy()
    old_skin.data = skin_ob.data.copy()
    old_skin.name = "_S7A_OLD_NOSE"
    bpy.context.collection.objects.link(old_skin)
    old_skin.hide_set(True)
    old_skin.hide_render = True

    # --- 2. delete six ---
    deleted = []
    for role, name in role_map.items():
        if name and delete_object(name):
            deleted.append(name)
            log(f"[del] {name}")

    # --- 3. import nose + details, T_REF only ---
    imported = []
    # nose
    path_nose = find_ref("机头")
    # prefer exact 机头.obj not 机头细节
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "机头" in fn and "细节" not in fn and "extra" not in fn.lower():
            if "机头" in fn:
                path_nose = os.path.join(REFS, fn)
                if fn.endswith("机头.obj") or fn == "C919_REF_机头.obj":
                    break
    # disambiguate: shortest name containing 机头 without 细节
    cands = [fn for fn in os.listdir(REFS) if fn.endswith(".obj") and "机头" in fn and "细节" not in fn]
    cands = [fn for fn in cands if "extra" not in fn.lower() and "nose" not in fn.lower()]
    if cands:
        path_nose = os.path.join(REFS, sorted(cands, key=len)[0])
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path_nose)
    new_nose = [o for o in bpy.data.objects if o not in before]
    log(f"[import nose] {path_nose} → {[o.name for o in new_nose]}")
    for ob in new_nose:
        if ob.type != "MESH":
            continue
        apply_t_ref(ob)
        imported.append(ob.name)

    # rename
    skin_new = next((o for o in new_nose if "蒙皮" in o.name or "机头" in o.name), None)
    glass_new = next((o for o in new_nose if "玻璃" in o.name or "风挡" in o.name), None)
    if skin_new is None:
        # pick larger
        meshes = [o for o in new_nose if o.type == "MESH"]
        meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
        skin_new = meshes[0]
        glass_new = meshes[1] if len(meshes) > 1 else None
    skin_new.name = "REF_机头蒙皮"
    if glass_new:
        glass_new.name = "CockpitGlass_REF"

    # details
    path_det = None
    for fn in os.listdir(REFS):
        if fn.endswith(".obj") and "机头" in fn and "细节" in fn:
            path_det = os.path.join(REFS, fn)
            break
    if not path_det:
        raise FileNotFoundError("C919_REF_机头细节.obj")
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path_det)
    new_det = [o for o in bpy.data.objects if o not in before]
    log(f"[import detail] {path_det} → {[o.name for o in new_det]}")
    rename_det = {
        "风挡窗框": "REF_风挡窗框",
        "雨刮": "REF_雨刮器",
        "探头": "REF_探头天线",
        "内饰": "REF_驾驶舱内饰",
        "窗框": "REF_风挡窗框",
    }
    for ob in new_det:
        if ob.type != "MESH":
            continue
        apply_t_ref(ob)
        for key, dest in rename_det.items():
            if key in ob.name:
                ob.name = dest
                break
        if not ob.name.startswith("REF_"):
            ob.name = "REF_" + ob.name
        imported.append(ob.name)

    # restore materials by role
    assign_mats(bpy.data.objects["REF_机头蒙皮"], records["skin"]["mats"] or [
        {"name": "Skin", "base": [0.96, 0.97, 0.98, 1], "metallic": 0.04, "roughness": 0.34, "blend": "HASHED"}
    ])
    glass_ob = bpy.data.objects.get("CockpitGlass_REF")
    if glass_ob:
        gmats = records["glass"]["mats"]
        if not gmats:
            gmats = [{
                "name": "REF_CockpitGlass", "blend": "BLEND",
                "base": [0x2E / 255, 0x3A / 255, 0x3E / 255, 1],
                "metallic": 0.0, "roughness": 0.03, "alpha": 0.45,
                "ior": 1.5, "transmission": 1.0, "transmission_key": "Transmission Weight",
            }]
        assign_mats(glass_ob, gmats)

    role_obj = {
        "frame": ("REF_风挡窗框", "REF_WindshieldFrame"),
        "wipers": ("REF_雨刮器", "REF_Wipers"),
        "probes": ("REF_探头天线", "REF_ProbesAntennas"),
        "interior": ("REF_驾驶舱内饰", "REF_CockpitInterior"),
    }
    for role, cands in role_obj.items():
        ob = None
        for n in cands:
            ob = bpy.data.objects.get(n)
            if ob:
                # canonicalize Chinese name
                if n != cands[0]:
                    ob.name = cands[0]
                break
        if ob:
            mats = records[role]["mats"]
            if not mats:
                # SPEC §4 defaults
                defaults = {
                    "frame": {"name": "REF_风挡窗框", "base": [0x0E / 255] * 3 + [1], "metallic": 0, "roughness": 0.4},
                    "wipers": {"name": "REF_雨刮器", "base": [0x2A / 255] * 3 + [1], "metallic": 0.5, "roughness": 0.4},
                    "probes": {"name": "REF_探头天线", "base": [0x8E / 255, 0x91 / 255, 0x96 / 255, 1], "metallic": 0.8, "roughness": 0.3},
                    "interior": {"name": "REF_驾驶舱内饰", "base": [0x1A / 255, 0x1C / 255, 0x1F / 255, 1], "metallic": 0, "roughness": 0.8},
                }
                mats = [defaults[role]]
            assign_mats(ob, mats)

    # --- 4. correct dependents: C = map old_skin → new_skin ---
    new_skin = bpy.data.objects["REF_机头蒙皮"]
    old_pts = mwv(old_skin)
    new_pts = mwv(new_skin)
    log(f"[fit] old_n={len(old_pts)} new_n={len(new_pts)}")
    if len(old_pts) == len(new_pts):
        C, fit_info = fit_affine_ls(old_pts, new_pts)
    else:
        C, fit_info = fit_similarity(old_pts, new_pts)
    # Also compute T_REF @ inv(M_old_nose) for report (M_old may be I if baked)
    Tref = t_ref_matrix()
    C_formula = Tref @ M_old_nose.inverted()
    log(f"[fit] info={fit_info}")
    log(f"[fit] C_formula (T_REF@inv(M_old)) translation={[C_formula[i][3] for i in range(3)]}")
    log(f"[fit] C_fit translation={[C[i][3] for i in range(3)]}")

    # Use fitted C (handles baked geometry). If fit failed badly, use landmark delta.
    corrected = []
    for n in ("RadomePanelLines", "CockpitDarkPlane"):
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        before_a = aabb(ob)
        apply_matrix_to_mesh(ob, C)
        after_a = aabb(ob)
        corrected.append({"name": n, "before": before_a, "after": after_a})
        log(f"[corr] {n} ymin {before_a['ymin']:.4f}→{after_a['ymin']:.4f}")

    delete_object("_S7A_OLD_NOSE")

    # --- 5. measure cuts + weld ---
    nose = bpy.data.objects["REF_机头蒙皮"]
    mid = bpy.data.objects["REF_中机身蒙皮"]
    aft = bpy.data.objects["REF_尾段蒙皮_含垂尾"]
    front_y = cut_world_y(OBJ_FRONT_CUT_Y)
    aft_y = cut_world_y(REF_CUT_Y_IMPORTED)
    log(f"[cut] front_y={front_y:.6f} aft_y={aft_y:.6f}")

    # use tight band first; also report end-ring
    dev_front = cut_deviation(nose, mid, front_y, tol=0.01)
    if dev_front["max_mm"] is None or dev_front["n_a"] < 3:
        # end-ring fallback
        a = end_ring(nose, "min", 0.02)
        b = end_ring(mid, "max", 0.02)
        mx, na, nb = max_hausdorff(a, b)
        dev_front = {
            "y_world": front_y, "tol": "end_ring_20mm",
            "n_a": na, "n_b": nb,
            "max_m": mx, "max_mm": None if mx is None else mx * 1000.0,
            "axial_gap_mm": (aabb(mid)["ymax"] - aabb(nose)["ymin"]) * 1000.0,
        }
    # also compute end-ring always for report
    a = end_ring(nose, "min", 0.02)
    b = end_ring(mid, "max", 0.02)
    mx, na, nb = max_hausdorff(a, b)
    dev_front_end = {
        "max_mm": None if mx is None else mx * 1000.0,
        "n_a": na, "n_b": nb,
        "axial_gap_mm": (aabb(mid)["ymax"] - aabb(nose)["ymin"]) * 1000.0,
    }

    dev_aft = cut_deviation(mid, aft, aft_y, tol=0.01)
    log(f"[dev-front] {dev_front}")
    log(f"[dev-front-end] {dev_front_end}")
    log(f"[dev-aft] {dev_aft}")

    aft_mm = dev_aft.get("max_mm")
    # Prefer tight band when both sides have ring verts; else end-ring
    if dev_front.get("max_mm") is not None and dev_front.get("n_a", 0) >= 8 and dev_front.get("n_b", 0) >= 8:
        front_mm = dev_front["max_mm"]
        front_method = "band_tol_10mm"
    else:
        front_mm = dev_front_end.get("max_mm")
        front_method = "end_ring_20mm"
    result_front_method = front_method
    log(f"[gate] front_mm={front_mm} via {front_method}; aft_mm={aft_mm}")

    weld_ok = (
        front_mm is not None and aft_mm is not None
        and front_mm < 5.0 and aft_mm < 5.0
    )

    result = {
        "front_method": front_method,
        "T_REF": {
            "sx": SX, "sy": SY, "sz": SZ,
            "tx": DX, "ty": DY, "tz": DZ,
            "matrix_order": "T @ S(sx,1,sz) @ R(Z180)",
        },
        "M_old_nose": [list(r) for r in M_old_nose],
        "C_fit": [list(r) for r in C],
        "C_formula_Tref_invMold": [list(r) for r in C_formula],
        "fit_info": fit_info,
        "records": records,
        "deleted_nose_pack": deleted,
        "imported_nose_pack": imported,
        "corrected": corrected,
        "dev_front": dev_front,
        "dev_front_end": dev_front_end,
        "dev_aft": dev_aft,
        "weld_ok": weld_ok,
        "backup": BAK_BEFORE,
        "scripts": ["section7a_nose_T_REF.py"],
    }

    if not weld_ok:
        log("[STOP] cut ≥ 5 mm")
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        result["stopped"] = True
        json.dump(result, open(os.path.join(LOG, "section7a.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump(result, open(os.path.join(ROOT, "logs", "section7a.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        open(PROGRESS, "w", encoding="utf-8").write("\n".join([
            "# PROGRESS — §7a STOPPED (weld gate)",
            f"- backup: c919.bak-before-s7a-nose.blend",
            f"- nose+details reimported with T_REF; dependents corrected via fit C",
            f"- front_mm={front_mm} aft_mm={aft_mm}",
            "- script: section7a_nose_T_REF.py",
        ]) + "\n")
        return result

    white = find_white_mat()
    mid.data.materials.clear()
    mid.data.materials.append(white)

    fus = weld_fuselage(nose, mid, aft, front_y, aft_y)
    fus.data.materials.clear()
    fus.data.materials.append(white)
    log(f"[weld] Fuselage_REF verts={len(fus.data.vertices)}")

    # --- materials 7.5.6 ---
    eng = ensure_mat("REF_EngineMetal", (0xB8 / 255, 0xBB / 255, 0xBF / 255), 0.6, 0.35)
    gear = ensure_mat("REF_GearDark", (0x3A / 255, 0x3D / 255, 0x42 / 255), 0.5, 0.45)
    door = ensure_mat("REF_舱门缝线", (0x3A / 255, 0x3D / 255, 0x42 / 255), 0.0, 0.5)
    glass_cabin = bpy.data.materials.get("REF_舷窗玻璃")
    if glass_cabin is None:
        # reuse windshield-like or existing
        for m in bpy.data.materials:
            if "窗" in m.name and m.name != "REF_CockpitGlass":
                glass_cabin = m
                break
    if glass_cabin is None:
        glass_cabin = ensure_mat(
            "REF_舷窗玻璃", (0x2E / 255, 0x3A / 255, 0x3E / 255), 0.0, 0.03,
            transmission=1.0, alpha=0.45, blend="BLEND",
        )

    for n in ("REF_机翼_左", "REF_机翼_右", "REF_吊挂_左", "REF_吊挂_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.data.materials.clear(); ob.data.materials.append(white)
    for n in ("REF_发动机_左", "REF_发动机_右"):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.data.materials.clear(); ob.data.materials.append(eng)
    for n in ("REF_前起落架", "REF_主起落架"):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.data.materials.clear(); ob.data.materials.append(gear)
    g = bpy.data.objects.get("REF_舷窗玻璃")
    if g:
        g.data.materials.clear(); g.data.materials.append(glass_cabin)
    s = bpy.data.objects.get("REF_舱门缝线")
    if s:
        s.data.materials.clear(); s.data.materials.append(door)

    # GearBayDoors
    gbd = gear_bay_decision(fus)
    result["GearBayDoors"] = gbd
    log(f"[GearBayDoors] {gbd}")

    tip = tip_y()
    measures = measure_stations(tip)
    result["tip"] = tip
    result["measurements"] = measures
    for m in measures:
        log(f"[meas] {m}")

    visible = sorted(o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_get())
    result["visible_meshes"] = visible

    rend = render_collage(tip)
    result["render"] = rend
    n_glb = export_glb()
    result["glb"] = GLB
    result["glb_mesh_count"] = n_glb
    result["stopped"] = False
    result["front_mm"] = front_mm
    result["aft_mm"] = aft_mm

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bak_done = os.path.join(OUT, "c919.bak-section7.blend")
    shutil.copy2(BLEND, bak_done)
    result["backup_done"] = bak_done

    json.dump(result, open(os.path.join(LOG, "section7a.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(result, open(os.path.join(ROOT, "logs", "section7a.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = [
        "# PROGRESS — §7 COMPLETE (via §7a nose T_REF)",
        "- backup: c919.bak-before-s7a-nose.blend → c919.bak-section7.blend",
        f"- T_REF sx={SX:.6f} sy=1 sz={SZ:.6f} ty={DY:.6f} tz={DZ:.6f}",
        f"- nose reimported T_REF; RadomePanelLines/CockpitDarkPlane corrected",
        f"- cuts front_mm={front_mm:.3f} aft_mm={aft_mm:.3f} → Fuselage_REF",
        f"- GearBayDoors={gbd.get('action')}; glb meshes={n_glb}",
        f"- collage={rend.get('collage_name')} tip_sx={rend.get('side_tip_sx'):.4f}",
        "- scripts: section7_ref_batch.py, section7a_nose_T_REF.py",
    ]
    for m in measures:
        lines.append(f"- {m['项目']}: {m['实测']} (ref {m['参考']}) {m['是否通过']}")
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines[:30]) + "\n")
    log("=== §7a DONE ===")
    return result


if __name__ == "__main__":
    main()

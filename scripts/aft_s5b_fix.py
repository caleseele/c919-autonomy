# -*- coding: utf-8 -*-
"""Fix APU tip diameter + raise VT/Rudder onto fuselage back after s5b."""
import json, math, os, shutil
import bmesh, bpy
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-s5b")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
APU_DIAM = 0.35
TABLE = [
    (26.00, 0.00, 4.16, 1.98),
    (27.00, 0.11, 4.16, 1.98),
    (28.00, 0.20, 4.16, 1.97),
    (29.00, 0.36, 4.15, 1.93),
    (30.00, 0.55, 4.14, 1.86),
    (31.00, 0.74, 4.14, 1.77),
    (32.00, 0.96, 4.14, 1.64),
    (33.00, 1.21, 4.05, 1.44),
    (34.00, 1.44, 3.98, 1.19),
    (35.00, 1.73, 3.95, 1.00),
    (36.00, 1.99, 3.90, 0.93),
    (37.00, 2.31, 3.69, 0.77),
    (38.84, 2.875, 3.225, 0.175),
]

def log(msg):
    print(msg, flush=True)
    with open(os.path.join(LOG, "aft_s5b_fix_console.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(d)
    m = e.to_mesh()
    vs = [ob.matrix_world @ v.co.copy() for v in m.vertices]
    e.to_mesh_clear()
    return vs

def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))

def const_belly_z(tip):
    fu = mwv(bpy.data.objects["Fuselage"])
    band = [v for v in fu if 20.0 <= (tip - v.y) <= 26.0]
    return min(v.z for v in band)

def lerp_table(td):
    if td <= TABLE[0][0]:
        return TABLE[0][1], TABLE[0][2], TABLE[0][3]
    if td >= TABLE[-1][0]:
        return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]
    for i in range(len(TABLE) - 1):
        t0, b0, k0, w0 = TABLE[i]
        t1, b1, k1, w1 = TABLE[i + 1]
        if t0 <= td <= t1:
            u = (td - t0) / (t1 - t0)
            return b0 + u * (b1 - b0), k0 + u * (k1 - k0), w0 + u * (w1 - w0)
    return TABLE[-1][1], TABLE[-1][2], TABLE[-1][3]

def fix_apu_tip(tip, z0):
    """Force TailCone verts near tip onto smooth APU circle diam=0.35."""
    ob = bpy.data.objects["TailCone"]
    mw = ob.matrix_world
    imw = mw.inverted()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    cx, cz = 0.0, z0 + 3.05
    r = APU_DIAM * 0.5
    n = 0
    for v in bm.verts:
        w = mw @ v.co
        td = tip - w.y
        if td < 37.0:
            continue
        # blend factor from 37 → 38.84
        u = max(0.0, min(1.0, (td - 37.0) / (38.84 - 37.0)))
        # target ellipse/circle section from table, then blend to APU circle
        bh, kh, hw = lerp_table(td)
        z_b, z_k = z0 + bh, z0 + kh
        # current direction in XZ from section center
        zc = 0.5 * (z_b + z_k)
        dx, dz = w.x - 0.0, w.z - zc
        dist = math.hypot(dx, dz)
        if dist < 1e-8:
            # assign by index-ish: use original co as seed
            ang = (v.index * 0.7) % (2 * math.pi)
            dx, dz = math.cos(ang), math.sin(ang)
            dist = 1.0
        # section target radius varies: use hw horizontally, (kh-bh)/2 vertically approx
        # map onto unit then scale to target rounded rect-ish → near tip to circle
        nx, nz = dx / dist, dz / dist
        # elliptical target at this station
        rx, rz = hw, 0.5 * (kh - bh)
        # point on ellipse in direction
        # x=rx*nx, z=zc+rz*nz (approx)
        x_ell = rx * nx
        z_ell = zc + rz * nz
        x_cir = cx + r * nx
        z_cir = cz + r * nz
        x_new = x_ell * (1 - u) + x_cir * u
        z_new = z_ell * (1 - u) + z_cir * u
        v.co = imw @ Vector((x_new, w.y, z_new))
        n += 1
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    log(f"[apu-fix] TailCone verts touched={n}")
    return n

def raise_vt_to_back():
    """Translate VT+Rudder so root sits on fuselage back (no shape change)."""
    vt = bpy.data.objects["VerticalTail"]
    fu = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])
    vv = mwv(vt)
    zmin = min(v.z for v in vv)
    low = [v for v in vv if v.z < zmin + 0.5]
    gaps = []
    for v in low[:: max(1, len(low) // 15)]:
        col = [p for p in fu if abs(p.y - v.y) < 0.4 and abs(p.x) < 1.0]
        if col:
            gaps.append(max(p.z for p in col) - v.z)  # how much to raise VT
    if not gaps:
        log("[vt-fix] no samples")
        return 0.0
    dz = sum(gaps) / len(gaps) + 0.02  # sit just on top
    if abs(dz) < 0.02:
        log(f"[vt-fix] already ok dz~{dz:.4f}")
        return 0.0
    for name in ("VerticalTail", "Rudder"):
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        mw = ob.matrix_world
        imw = mw.inverted()
        w0 = mw @ Vector((0, 0, 0))
        local = imw @ (w0 + Vector((0, 0, dz))) - imw @ w0
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        for v in bm.verts:
            v.co += local
        bm.to_mesh(ob.data)
        ob.data.update()
        bm.free()
        log(f"[vt-fix] {name} dz={dz:.4f}")
    bpy.context.view_layer.update()
    return dz

def measure_station(tip, z0, td, half=0.45):
    verts = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])
    band = [v for v in verts if abs((tip - v.y) - td) <= half]
    if len(band) < 6:
        band = [v for v in verts if abs((tip - v.y) - td) <= half * 2]
    if not band:
        return None
    zs = [v.z for v in band]
    xs = [abs(v.x) for v in band]
    return min(zs) - z0, max(zs) - z0, max(xs)

def measure_apu(tip, z0):
    tc = mwv(bpy.data.objects["TailCone"])
    tc_end = min(v.y for v in tc)
    # use last 0.4 m and prefer verts away from pure tip pole
    band = [v for v in tc if v.y < tc_end + 0.35]
    cx, cz = 0.0, z0 + 3.05
    rs = [math.hypot(v.x - cx, v.z - cz) for v in band]
    mean_d = 2.0 * (sum(rs) / len(rs))
    # also section at tip_dist 38.5
    band2 = [v for v in tc if abs((tip - v.y) - 38.5) < 0.25]
    if band2:
        rs2 = [math.hypot(v.x - cx, v.z - cz) for v in band2]
        d2 = 2.0 * (sum(rs2) / len(rs2))
    else:
        d2 = mean_d
    return {"mean_diam_tipband": mean_d, "diam_at_38.5": d2, "n": len(band), "center_z_target": cz}

def check_vt():
    vt = mwv(bpy.data.objects["VerticalTail"])
    fu = mwv(bpy.data.objects["Fuselage"]) + mwv(bpy.data.objects["TailCone"])
    zmin = min(v.z for v in vt)
    low = [v for v in vt if v.z < zmin + 0.5]
    gaps = []
    for v in low[:: max(1, len(low) // 12)]:
        col = [p for p in fu if abs(p.y - v.y) < 0.35 and abs(p.x) < 0.8]
        if col:
            gaps.append(v.z - max(p.z for p in col))
    avg = sum(gaps) / len(gaps) if gaps else None
    ok = avg is not None and -0.08 <= avg <= 0.25
    return {"status": "OK" if ok else "GAP", "gap_avg": avg}

def bb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

def render_compare(tip):
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
    cam.location = (80.0, tip - 38.84 * 0.5, -0.5)
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
    scene.camera = cam
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name.startswith("LengthRef_")
    scene.render.filepath = os.path.join(PREV, "side_ours.png")
    bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    fbx = os.path.join(REFS, "REF_C919_meters.fbx")
    bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)
    ref_objs = [o for o in bpy.data.objects if o not in before]
    for o in ref_objs:
        o.name = "LengthRef_" + o.name[:50]
    ys = []
    for o in ref_objs:
        if o.type != "MESH":
            continue
        b = bb(o)
        ys += [b["ymin"], b["ymax"]]
    dy = tip - max(ys)
    for o in ref_objs:
        o.location.y += dy
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        o.hide_render = not o.name.startswith("LengthRef_")
    scene.render.filepath = os.path.join(PREV, "side_ref.png")
    bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False
    return fbx + " (no C919_REF_整机.obj)"

def main():
    open(os.path.join(LOG, "aft_s5b_fix_console.txt"), "w", encoding="utf-8").close()
    log("=== AFT S5b FIX ===")
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tip = tip_y()
    z0 = const_belly_z(tip)
    log(f"tip={tip:.4f} z0={z0:.4f}")
    fix_apu_tip(tip, z0)
    dz = raise_vt_to_back()
    bpy.context.view_layer.update()
    vt = check_vt()
    apu = measure_apu(tip, z0)
    log(f"[vt] {vt}")
    log(f"[apu] {apu}")

    rows = []
    for td, bh, kh, hw in [(26,0,4.16,1.98),(27,0.11,4.16,1.98),(28,0.20,4.16,1.97),(29,0.36,4.15,1.93),(30,0.55,4.14,1.86),(31,0.74,4.14,1.77),(32,0.96,4.14,1.64),(33,1.21,4.05,1.44),(34,1.44,3.98,1.19),(35,1.73,3.95,1.00),(36,1.99,3.90,0.93),(37,2.31,3.69,0.77),(38.84,2.875,3.225,0.175)]:
        m = measure_station(tip, z0, td if td < 38 else tip - min(v.y for v in mwv(bpy.data.objects["TailCone"])))
        if not m:
            rows.append({"项目": f"站位 tip={td}", "实测": "—", "参考": f"{bh}/{kh}/{hw}", "差值": "—", "是否通过": "否"})
            continue
        mb, mk, mw_ = m
        db, dk, dw = mb - bh, mk - kh, mw_ - hw
        tol_b = 0.15 if td < 37 else 0.20
        tol_k = 0.18 if td < 37 else 0.25
        tol_w = 0.12 if td < 37 else 0.10
        # sparse-mesh note: if nearest ring shared, loosen
        ok = abs(db) <= tol_b and abs(dk) <= tol_k and abs(dw) <= tol_w
        rows.append({
            "项目": f"站位 tip={td:g} belly/back/half_w",
            "实测": f"{mb:.3f}/{mk:.3f}/{mw_:.3f}",
            "参考": f"{bh:.3f}/{kh:.3f}/{hw:.3f}",
            "差值": f"{db:+.3f}/{dk:+.3f}/{dw:+.3f}",
            "是否通过": "是" if ok else "否",
        })
        log(f"[meas] td={td} {mb:.3f}/{mk:.3f}/{mw_:.3f} tgt {bh}/{kh}/{hw} pass={ok}")

    # APU: prefer diam_at_38.5 or tipband — pass if either close
    d_apu = apu["diam_at_38.5"]
    rows.append({
        "项目": "APU排气口直径",
        "实测": round(d_apu, 3),
        "参考": APU_DIAM,
        "差值": round(d_apu - APU_DIAM, 3),
        "是否通过": "是" if abs(d_apu - APU_DIAM) <= 0.10 else "否",
    })
    rows.append({
        "项目": "垂尾根部贴背上",
        "实测": f"gap_avg={None if vt['gap_avg'] is None else round(vt['gap_avg'],3)}; dz_applied={round(dz,3)}",
        "参考": "坐在背上",
        "差值": "—",
        "是否通过": "是" if vt["status"] == "OK" else "否",
    })
    rows.append({
        "项目": "方向舵",
        "实测": "随垂尾平移，未改形",
        "参考": "根部随背上",
        "差值": "—",
        "是否通过": "是" if vt["status"] == "OK" else "否",
    })

    ref_note = render_compare(tip)
    for o in list(bpy.data.objects):
        if o.name.startswith("LengthRef_"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log(f"GLB {os.path.getsize(GLB)}")

    # merge into aft_s5b.json
    jp = os.path.join(LOG, "aft_s5b.json")
    d = {}
    if os.path.isfile(jp):
        d = json.load(open(jp, encoding="utf-8"))
    d["fix"] = {"vt_dz": dz, "vt": vt, "apu": apu}
    d["measurements"] = rows
    d["scripts"] = ["aft_s5b_reshape.py", "aft_s5b_fix.py"]
    d["ref_source"] = ref_note
    json.dump(d, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    prog = [
        "# PROGRESS — AFT s5b (§5b shape finish)",
        "- backup: c919.bak-aft-s5b.blend",
        "- Fuselage+TailCone tip_dist>26 remapped; Nose untouched",
        f"- APU diam@38.5≈{d_apu:.3f} (target 0.35); VT raised dz={dz:.3f} status={vt['status']}",
        "- scripts: aft_s5b_reshape.py, aft_s5b_fix.py",
        f"- compare: aft-s5b/; REF={ref_note}",
        "- no §6 windows/doors",
    ]
    for r in rows:
        if "站位" in r["项目"] or "APU" in r["项目"] or "垂尾" in r["项目"]:
            prog.append(f"- {r['项目']}: {r['实测']} ref={r['参考']} pass={r['是否通过']}")
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(prog[:30]) + "\n")
    log("=== FIX DONE ===")

if __name__ == "__main__":
    main()

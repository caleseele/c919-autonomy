# -*- coding: utf-8 -*-
import bpy, bmesh
from mathutils import Vector

def mwv(ob):
    d = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    me = ev.to_mesh()
    mat = ob.matrix_world
    vs = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return vs

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\public\models\c919.blend")
tip = max(v.y for v in mwv(bpy.data.objects["Nose"]))
for side, pn, wn in [("R", "Pylon_R", "Wing_R"), ("L", "Pylon_L", "Wing_L")]:
    pv = mwv(bpy.data.objects[pn])
    wv = mwv(bpy.data.objects[wn])
    pyl_zmax = max(v.z for v in pv)
    top = [v for v in pv if v.z >= pyl_zmax - 0.08]
    txs = [v.x for v in top]
    tys = [v.y for v in top]
    print(f"[{side}] pyl_zmax={pyl_zmax:.3f} top_n={len(top)} x=[{min(txs):.2f},{max(txs):.2f}] y=[{min(tys):.2f},{max(tys):.2f}]")
    near = [v for v in wv if min(txs) - 0.3 <= v.x <= max(txs) + 0.3 and min(tys) - 0.3 <= v.y <= max(tys) + 0.3]
    print(f"  wing_near_n={len(near)}")
    if near:
        print(f"  wing_near z=[{min(v.z for v in near):.3f},{max(v.z for v in near):.3f}]")
        gaps = []
        above = below = 0
        step = max(1, len(top) // 20)
        for t in top[::step]:
            best = min(near, key=lambda w: (w.x - t.x) ** 2 + (w.y - t.y) ** 2)
            gaps.append(t.z - best.z)
            local = [v for v in near if abs(v.x - t.x) < 0.4 and abs(v.y - t.y) < 0.4]
            if local:
                if t.z > max(v.z for v in local) + 0.05:
                    above += 1
                if t.z < min(v.z for v in local) - 0.05:
                    below += 1
        print(f"  dz avg={sum(gaps)/len(gaps):.3f} min={min(gaps):.3f} max={max(gaps):.3f} above={above} below={below}")
    # Also: wing underside at same XY — is pylon top within 0.05 of underside?
    # underside ≈ min Z in local columns
    if near:
        unders = []
        for t in top[::step]:
            col = [v for v in near if abs(v.x - t.x) < 0.35 and abs(v.y - t.y) < 0.35]
            if col:
                unders.append(t.z - min(v.z for v in col))
        if unders:
            print(f"  vs_underside (pyl-wing_zmin) avg={sum(unders)/len(unders):.3f}")

nose = bpy.data.objects["Nose"]
bm = bmesh.new()
bm.from_mesh(nose.data)
bm.edges.ensure_lookup_table()
be = [e for e in bm.edges if e.is_boundary]
print(f"[Nose] boundary_edges_after_fill={len(be)}")
bm.free()
eng = mwv(bpy.data.objects["Engine_R"])
print(f"tip_nac={tip - max(v.y for v in eng):.4f}")
print("pylon_y", min(v.y for v in mwv(bpy.data.objects["Pylon_R"])), max(v.y for v in mwv(bpy.data.objects["Pylon_R"])))
print("wing_y", min(v.y for v in mwv(bpy.data.objects["Wing_R"])), max(v.y for v in mwv(bpy.data.objects["Wing_R"])))

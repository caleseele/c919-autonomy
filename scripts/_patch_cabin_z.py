from pathlib import Path
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
t = p.read_text(encoding="utf-8")
old = """    for y in ys:
        rx, rz = _section_at_y(y)
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            # a_canopy uses 0=crown from +Z; here full circle from +X
            x = math.cos(a) * rx * scale
            z = math.sin(a) * rz * scale
            ring.append(bm.verts.new((x, y, z)))
"""
new = """    for y in ys:
        rx, rz, z0 = _section_full_at_y(y)
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            # a_canopy uses 0=crown from +Z; here full circle from +X
            x = math.cos(a) * rx * scale
            z = math.sin(a) * rz * scale + z0
            ring.append(bm.verts.new((x, y, z)))
"""
assert old in t, "cabin shell loop not found"
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("cabin z_off OK")

from pathlib import Path
p = Path("scripts/build_c919.py")
t = p.read_text(encoding="utf-8")

old = '''def cockpit_pilot_seats():
    """Dual blocky pilot seats (red) — readable through clear windshield."""
    bm = bmesh.new()
    for sx in (-0.50, 0.50):
        # Cushion
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.36, 0.40, 0.11))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.58, 0.18))
        # Backrest
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.34, 0.11, 0.52))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.35, 0.50))
        # Headrest
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.26, 0.09, 0.13))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.33, 0.88))
        # Armrests
        for ax in (-0.22, 0.22):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.06, 0.28, 0.05))
            bmesh.ops.translate(bm, verts=created, vec=(sx + ax, 16.55, 0.32))
    return finish(bm)'''

new = '''def cockpit_pilot_seats():
    """Dual blocky pilot seats (red) — headrests poke above glare shield."""
    bm = bmesh.new()
    for sx in (-0.48, 0.48):
        # Cushion (slightly aft so readable behind glare shelf)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.38, 0.42, 0.12))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.42, 0.22))
        # Tall backrest — top clears glare shield (~z0.95)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.36, 0.12, 0.62))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.18, 0.62))
        # Headrest above glare line
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.28, 0.10, 0.16))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.16, 1.18))
        # Armrests
        for ax in (-0.24, 0.24):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.07, 0.30, 0.055))
            bmesh.ops.translate(bm, verts=created, vec=(sx + ax, 16.40, 0.36))
    return finish(bm)'''

if old not in t:
    raise SystemExit("seats block not found")
t = t.replace(old, new, 1)

# Also shrink glare shield Y depth so it doesn't fully block seats
old_g = '''    bmesh.ops.scale(bm, verts=created, vec=(1.55, 0.48, 0.07))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.92, 0.95))'''
new_g = '''    bmesh.ops.scale(bm, verts=created, vec=(1.50, 0.36, 0.06))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 17.05, 0.98))'''
if old_g not in t:
    raise SystemExit("glare scale not found")
t = t.replace(old_g, new_g, 1)

# Make overwing door panel slightly darker for clay readability
# (keep as is — instead add bold outline cubes projected? skip)

p.write_text(t, encoding="utf-8")
print("SEATS_RAISED")

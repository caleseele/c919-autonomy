# -*- coding: utf-8 -*-
"""door2b: single skin seal (no dual ring) + more visible plug panel."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

new_frames = '''def cabin_door_frames():
    """Dark seal loft on skin — continuous rounded rectangle, all four sides.

    door2: NEVER emit planar add_rounded_frame for overwing (that floated as
    thick hollow wireframes off the cylinder). All doors are skin-projected.
    door2b: single loft only (dual lofts read as double ghost frames).
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            if kind == "overwing":
                # One continuous seal, slightly proud of skin — plug rim
                _add_skin_seal_loft(
                    bm, y, z, w + 0.06, h + 0.06, corner + 0.015, side,
                    border=0.055, r_off=0.012, segs=10, rings=5,
                )
            else:
                _add_skin_seal_loft(
                    bm, y, z, w + 0.05, h + 0.05, corner + 0.015, side,
                    border=0.050, r_off=0.013, segs=8, rings=5,
                )
    _orient_faces_outward(bm)
    return finish(bm)
'''

new_doors = '''def cabin_doors():
    """Plug-door panels following fuselage curvature (slightly proud of skin)."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Fill seal throat; overwing a bit fuller so center is not empty skin
            scale = 0.93 if kind == "overwing" else 0.90
            _add_skin_shell_grid(
                bm, y, z, w * scale, h * scale, corner * 0.85, side,
                r_off=0.007 if kind == "overwing" else 0.005,
                ny=14 if kind != "overwing" else 12,
                nz=18 if kind != "overwing" else 16,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

# Darken DoorSkin slightly so plug reads vs white fuselage
old_mat = 'door_skin = material("DoorSkin", (0.86, 0.87, 0.88), 0.42, 0.04)'
new_mat = 'door_skin = material("DoorSkin", (0.72, 0.74, 0.76), 0.48, 0.05)'
if old_mat not in t:
    # maybe already darkened
    if 'door_skin = material("DoorSkin", (0.72, 0.74, 0.76)' in t:
        print("MAT_ALREADY")
    else:
        raise SystemExit("DoorSkin material line not found")
else:
    t = t.replace(old_mat, new_mat, 1)
    print("MAT_DARKENED")

pat_frames = re.compile(r"def cabin_door_frames\(\):.*?return finish\(bm\)\n", re.S)
if not pat_frames.search(t):
    raise SystemExit("cabin_door_frames missing")
t = pat_frames.sub(new_frames + "\n", t, count=1)
print("FRAMES_OK")

pat_doors = re.compile(r"def cabin_doors\(\):.*?return finish\(bm\)\n", re.S)
if not pat_doors.search(t):
    raise SystemExit("cabin_doors missing")
t = pat_doors.sub(new_doors + "\n", t, count=1)
print("DOORS_OK")

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
start = tt.find("def cabin_door_frames")
end = tt.find("def cabin_door_windows")
block = tt[start:end]
assert "add_rounded_frame(" not in block
assert "door2b: single loft" in block
assert block.count("_add_skin_seal_loft") == 2  # overwing once + else once in source text... wait loop
# Actually in source there are 2 calls in the function body
assert "_add_skin_seal_loft" in block
# Ensure only one overwing call (no dual)
assert "Inner plug rim" not in block
assert "Outer seal near-flush" not in block
print("DOOR2B_PATCH_OK", p.stat().st_size)

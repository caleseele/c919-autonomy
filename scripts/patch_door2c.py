# -*- coding: utf-8 -*-
"""door2c: thin seal groove + filled plug panel (still skin-projected only)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

new_frames = '''def cabin_door_frames():
    """Thin dark seal on skin — continuous rounded rectangle, all four sides.

    door2: NEVER emit planar add_rounded_frame (floated as thick hollow frames).
    door2c: thin border (~28–35 mm) so seal reads as groove/rim, not a tube.
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            if kind == "overwing":
                _add_skin_seal_loft(
                    bm, y, z, w + 0.04, h + 0.04, corner + 0.012, side,
                    border=0.032, r_off=0.008, segs=10, rings=4,
                )
            else:
                _add_skin_seal_loft(
                    bm, y, z, w + 0.04, h + 0.04, corner + 0.012, side,
                    border=0.030, r_off=0.008, segs=8, rings=4,
                )
    _orient_faces_outward(bm)
    return finish(bm)
'''

new_doors = '''def cabin_doors():
    """Plug-door panels on skin — fill seal throat, slight proud, readable tone."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Nearly fill seal inner (seal outer=w+0.04, border~0.03 → inner≈w+0.01)
            scale = 0.97 if kind == "overwing" else 0.95
            _add_skin_shell_grid(
                bm, y, z, w * scale, h * scale, corner * 0.88, side,
                r_off=0.004, ny=14, nz=18,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

pat_frames = re.compile(r"def cabin_door_frames\(\):.*?return finish\(bm\)\n", re.S)
if not pat_frames.search(t):
    raise SystemExit("cabin_door_frames missing")
t = pat_frames.sub(new_frames + "\n", t, count=1)

pat_doors = re.compile(r"def cabin_doors\(\):.*?return finish\(bm\)\n", re.S)
if not pat_doors.search(t):
    raise SystemExit("cabin_doors missing")
t = pat_doors.sub(new_doors + "\n", t, count=1)

# Keep darkened door skin
if 'door_skin = material("DoorSkin", (0.72, 0.74, 0.76)' not in t:
    t = t.replace(
        'door_skin = material("DoorSkin", (0.86, 0.87, 0.88), 0.42, 0.04)',
        'door_skin = material("DoorSkin", (0.72, 0.74, 0.76), 0.48, 0.05)',
        1,
    )

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
start, end = tt.find("def cabin_door_frames"), tt.find("def cabin_door_windows")
assert "add_rounded_frame(" not in tt[start:end]
assert "door2c: thin border" in tt
assert "border=0.032" in tt
print("DOOR2C_OK", p.stat().st_size)

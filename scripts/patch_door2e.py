# -*- coding: utf-8 -*-
"""door2e: proud visible plug panel (never negative r_off) + thin flush seal."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

new_frames = '''def cabin_door_frames():
    """Thin dark seal on skin — continuous rounded rectangle.

    door2: never planar add_rounded_frame (floated as thick hollow frames).
    door2e: thin near-skin seal; panel is slightly PROUD so it stays visible
    (negative r_off hides the panel inside the fuselage shell).
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            ow, oh = w + 0.030, h + 0.030
            cr = corner + 0.010
            border = 0.028 if kind == "overwing" else 0.026
            _add_skin_seal_loft(
                bm, y, z, ow, oh, cr, side,
                border=border, r_off=0.009, segs=10, rings=4,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

new_doors = '''def cabin_doors():
    """Plug panels slightly PROUD of skin (must stay outside fuselage shell)."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Fill seal throat: outer=w+0.030, border~0.027 → inner≈w+0.003
            pw = (w + 0.030) - 2 * 0.027 - 0.008
            ph = (h + 0.030) - 2 * 0.027 - 0.008
            pc = max(0.045, corner - 0.015)
            _add_skin_shell_grid(
                bm, y, z, pw, ph, pc, side,
                r_off=0.005, ny=14, nz=18,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

pat_frames = re.compile(r"def cabin_door_frames\(\):.*?return finish\(bm\)\n", re.S)
pat_doors = re.compile(r"def cabin_doors\(\):.*?return finish\(bm\)\n", re.S)
if not pat_frames.search(t) or not pat_doors.search(t):
    raise SystemExit("blocks missing")
t = pat_frames.sub(new_frames + "\n", t, count=1)
t = pat_doors.sub(new_doors + "\n", t, count=1)
t = re.sub(
    r'door_skin = material\("DoorSkin", \([^)]+\),[^)]+\)',
    'door_skin = material("DoorSkin", (0.58, 0.60, 0.62), 0.52, 0.05)',
    t,
    count=1,
)
p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
assert "door2e:" in tt
assert "r_off=0.005" in tt
assert "r_off=-0.006" not in tt[tt.find("def cabin_doors"):tt.find("def cabin_door_frames")+800]
assert "add_rounded_frame(" not in tt[tt.find("def cabin_door_frames"):tt.find("def cabin_door_windows")]
print("DOOR2E_OK", p.stat().st_size)

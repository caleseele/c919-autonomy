# -*- coding: utf-8 -*-
"""door2d: recessed plug panel + near-flush thin seal; matched sizes."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

new_frames = '''def cabin_door_frames():
    """Thin dark seal groove on skin — continuous rounded rectangle.

    door2: no planar add_rounded_frame (that floated as thick hollow frames).
    door2d: near-flush thin border; pairs with slightly recessed door panel.
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Shared sizing with cabin_doors panel fill
            ow, oh = w + 0.028, h + 0.028
            cr = corner + 0.008
            border = 0.026 if kind == "overwing" else 0.024
            _add_skin_seal_loft(
                bm, y, z, ow, oh, cr, side,
                border=border, r_off=0.002, segs=10, rings=4,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

new_doors = '''def cabin_doors():
    """Plug panels: slightly recessed into seal throat, matched corner/size."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Match frame: outer=w+0.028, border~0.025 → inner≈w+0.003
            # Panel fills inner with ~8 mm margin so dark seal reads continuous
            pw = w + 0.028 - 2 * 0.025 - 0.010  # ≈ w - 0.032
            ph = h + 0.028 - 2 * 0.025 - 0.010
            pc = max(0.04, corner - 0.02)
            _add_skin_shell_grid(
                bm, y, z, pw, ph, pc, side,
                r_off=-0.006, ny=14, nz=18,
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

# Darker recessed panel so plug reads clearly vs white skin
t2 = t
t = re.sub(
    r'door_skin = material\("DoorSkin", \([^)]+\),[^)]+\)',
    'door_skin = material("DoorSkin", (0.62, 0.64, 0.66), 0.55, 0.06)',
    t,
    count=1,
)
if t == t2:
    raise SystemExit("DoorSkin replace failed")

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
assert "door2d: near-flush" in tt
assert "add_rounded_frame(" not in tt[tt.find("def cabin_door_frames"):tt.find("def cabin_door_windows")]
assert "r_off=-0.006" in tt
print("DOOR2D_OK", p.stat().st_size)

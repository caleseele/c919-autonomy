# -*- coding: utf-8 -*-
"""door2: remove planar overwing bezel; skin-only plug doors."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
if not p.exists():
    # When copied next to build script
    p = Path(__file__).resolve().parent / "build_c919.py"
t = p.read_text(encoding="utf-8")

new_frames = '''def cabin_door_frames():
    """Dark seal loft on skin — continuous rounded rectangle, all four sides.

    door2: NEVER emit planar add_rounded_frame for overwing (that floated as
    thick hollow wireframes off the cylinder). All doors are skin-projected.
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            if kind == "overwing":
                # Outer seal near-flush (groove against fuselage skin)
                _add_skin_seal_loft(
                    bm, y, z, w + 0.08, h + 0.08, corner + 0.02, side,
                    border=0.062, r_off=0.003, segs=10, rings=4,
                )
                # Inner plug rim slightly proud — reads as door edge, stays on skin
                _add_skin_seal_loft(
                    bm, y, z, w + 0.02, h + 0.02, corner + 0.01, side,
                    border=0.038, r_off=0.014, segs=10, rings=4,
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
            # Overwing: fill more of the seal throat so hollow center is not empty
            scale = 0.94 if kind == "overwing" else 0.90
            _add_skin_shell_grid(
                bm, y, z, w * scale, h * scale, corner * 0.85, side,
                r_off=0.006 if kind == "overwing" else 0.005,
                ny=14 if kind != "overwing" else 12,
                nz=18 if kind != "overwing" else 16,
            )
    _orient_faces_outward(bm)
    return finish(bm)
'''

pat_frames = re.compile(r"def cabin_door_frames\(\):.*?return finish\(bm\)\n", re.S)
m = pat_frames.search(t)
if not m:
    raise SystemExit("cabin_door_frames block not found")
block = m.group(0)
if "add_rounded_frame" not in block and "door2: NEVER emit planar" in block:
    print("ALREADY_PATCHED_FRAMES")
else:
    if "add_rounded_frame" not in block:
        raise SystemExit("expected add_rounded_frame in overwing cabin_door_frames")
    t = pat_frames.sub(new_frames + "\n", t, count=1)
    print("FRAMES_REPLACED")

pat_doors = re.compile(r"def cabin_doors\(\):.*?return finish\(bm\)\n", re.S)
m = pat_doors.search(t)
if not m:
    raise SystemExit("cabin_doors block not found")
if "scale = 0.94 if kind == \"overwing\"" in m.group(0):
    print("ALREADY_PATCHED_DOORS")
else:
    t = pat_doors.sub(new_doors + "\n", t, count=1)
    print("DOORS_REPLACED")

if "door2: skin-only seals" not in t:
    t = t.replace(
        "def _door_specs():\n    # y, z, w, h, corner, kind\n",
        "def _door_specs():\n    # y, z, w, h, corner, kind\n"
        "    # door2: skin-only seals (no planar add_rounded_frame)\n",
        1,
    )
    print("SPEC_NOTE_ADDED")

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
start = tt.find("def cabin_door_frames")
end = tt.find("def cabin_door_windows")
assert start > 0 and end > start
assert "add_rounded_frame" not in tt[start:end]
assert "door2: NEVER emit planar" in tt
print("DOOR2_PATCH_OK", p, p.stat().st_size)

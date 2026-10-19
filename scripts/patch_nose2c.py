# -*- coding: utf-8 -*-
"""nose2c: kill fairing/glass z-fight; softer radome ring; clearer layer offsets."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

# Move crown fairings away from glass Y bands
old_f = '''    # nose2b: crown sill fairing — fills top-down "shelf" between radome & glass
    # Single-sided, barely proud, skin-like (still cockpit metal — thin ribbon)
    _add_shell_sector(
        bm,
        [18.05, 17.85, 17.68, 17.55],
        -math.radians(42),
        math.radians(42),
        0.0012,
        segs_a=18,
    )
    # Soft brow fairing aft of glass (crown)
    _add_shell_sector(
        bm,
        [16.35, 16.18, 16.00],
        -math.radians(40),
        math.radians(40),
        0.0010,
        segs_a=16,
    )
'''

new_f = '''    # nose2c: crown fairings ONLY ahead of sill / aft of brow — no glass overlap
    # (nose2b bands z-fought panes → sawtooth in top-down Cycles)
    _add_shell_sector(
        bm,
        [18.22, 18.08, 17.95, 17.82],
        -math.radians(38),
        math.radians(38),
        0.0020,
        segs_a=20,
    )
    _add_shell_sector(
        bm,
        [16.02, 15.88, 15.72],
        -math.radians(36),
        math.radians(36),
        0.0015,
        segs_a=16,
    )
'''

if "nose2c: crown fairings ONLY" in t:
    print("FAIRING already")
elif old_f in t:
    t = t.replace(old_f, new_f, 1)
    print("FAIRING exact")
else:
    # regex fallback between nose2b comment and return finish of frames
    pat = re.compile(
        r"    # nose2b: crown sill fairing.*?\n(?:    .*\n)*?        segs_a=16,\n    \)\n",
        re.S,
    )
    if not pat.search(t):
        raise SystemExit("fairing block not found")
    t = pat.sub(new_f, t, count=1)
    print("FAIRING regex")

# Soften radome parting further
t2 = t
t = t.replace(
    "(18.48, 0.014, 0.010),  # nose2: softer radome parting (less top-down step)",
    "(18.48, 0.008, 0.005),  # nose2c: hairline radome parting",
    1,
)
if t == t2:
    if "nose2c: hairline radome parting" in t:
        print("RING already")
    else:
        t = re.sub(
            r"\(18\.48, [^)]+\),[^\n]*",
            "(18.48, 0.008, 0.005),  # nose2c: hairline radome parting",
            t,
            count=1,
        )
        print("RING regex")
else:
    print("RING exact")

# Glass / frame layering with clearer separation from skin
t = re.sub(
    r'_add_canopy_pane\(bm, pane, r_off=0\.003\)',
    '_add_canopy_pane(bm, pane, r_off=0.004)',
    t,
    count=1,
)
t = re.sub(
    r"    r_off = 0\.006  # nose2b: glass at \+0\.003; thin flush ribbons\n",
    "    r_off = 0.008  # nose2c: thin ribbons clear of glass (+0.004)\n",
    t,
    count=1,
)
print("LAYERS")

# Flange outer even closer to skin (was -0.001)
t = t.replace(
    "outer = [bm.verts.new(_canopy_point(a, y, -0.001)) for a, y in outline]",
    "outer = [bm.verts.new(_canopy_point(a, y, -0.0005)) for a, y in outline]",
    1,
)
print("FLANGE_OUTER")

# door guard
start, end = t.find("def cabin_door_frames"), t.find("def cabin_door_windows")
assert not re.search(r"(?m)^\s*add_rounded_frame\(", t[start:end])

p.write_text(t, encoding="utf-8")
assert "nose2c: crown fairings ONLY" in p.read_text(encoding="utf-8")
print("NOSE2C_OK", p.stat().st_size)

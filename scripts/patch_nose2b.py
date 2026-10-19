# -*- coding: utf-8 -*-
"""nose2b: less-sunken glass, smaller punch, smoother flange, crown sill blend."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

# 1) Glass closer to flush
old_ws = '''def cockpit_windshield():
    """Four double-curved C919 panes, slightly recessed under thin frames.

    ws1: modest recess (r_off~0.004) so glass sits behind flush metallic
    ribbons; dense sampling for continuous double curvature.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.006)
    return finish(bm)
'''

new_ws = '''def cockpit_windshield():
    """Four double-curved C919 panes, nearly flush under thin frames.

    nose2b: r_off~0.003 — less sunken vs radome in top-down (was 0.006).
    Dense sampling for continuous double curvature; no pipe frames.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 28)
        pane["segs_y"] = max(pane["segs_y"], 20)
        _add_canopy_pane(bm, pane, r_off=0.003)
    return finish(bm)
'''

if "nose2b: r_off~0.003" in t:
    print("WS already")
elif old_ws in t:
    t = t.replace(old_ws, new_ws, 1)
    print("WS exact")
else:
    pat = re.compile(r"def cockpit_windshield\(\):.*?return finish\(bm\)\n", re.S)
    if not pat.search(t):
        raise SystemExit("cockpit_windshield missing")
    t = pat.sub(new_ws + "\n", t, count=1)
    print("WS regex")

# 2) Frames slightly less proud; keep thin (no pipes)
t2 = t
t = t.replace(
    "    r_off = 0.009  # glass at +0.004\n",
    "    r_off = 0.006  # nose2b: glass at +0.003; thin flush ribbons\n",
    1,
)
if t == t2:
    if "nose2b: glass at +0.003" in t:
        print("FRAME_ROFF already")
    else:
        # broader replace
        t = re.sub(
            r"    r_off = 0\.009[^\n]*\n",
            "    r_off = 0.006  # nose2b: glass at +0.003; thin flush ribbons\n",
            t,
            count=1,
        )
        print("FRAME_ROFF regex")
else:
    print("FRAME_ROFF exact")

# 3) Punch: smaller hole, shallower flange, denser outline, stronger dissolve
old_punch_head = '''    panes = _cockpit_pane_defs()
    A_INSET = math.radians(1.05)
    Y_INSET = 0.045
'''
new_punch_head = '''    panes = _cockpit_pane_defs()
    # nose2b: leave more skin under frames — smaller hole, less top-down ledge
    A_INSET = math.radians(1.45)
    Y_INSET = 0.058
'''
if "nose2b: leave more skin" in t:
    print("PUNCH_HEAD already")
elif old_punch_head in t:
    t = t.replace(old_punch_head, new_punch_head, 1)
    print("PUNCH_HEAD exact")
else:
    raise SystemExit("punch insets not found")

t = t.replace(
    "    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.012]",
    "    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.024]",
    1,
)
print("DISSOLVE_THRESH")

t = t.replace(
    "    FLANGE_DEPTH = 0.028\n    SEGS_A = 20\n    SEGS_Y = 12\n",
    "    FLANGE_DEPTH = 0.016  # nose2b: shallower reveal, less cliff\n"
    "    SEGS_A = 28\n    SEGS_Y = 16\n",
    1,
)
print("FLANGE")

# 4) After cheek blend in cockpit_frames, add crown sill fairing (smooth radome→glass)
old_cheek_end = '''    # nose2: wider/longer cheek blend — softs WS-to-nose shoulder in plan/3/4
    for sign in (-1.0, 1.0):
        ys = [17.35, 16.90, 16.40, 15.95, 15.55]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(105),
            sign * math.radians(122),
            0.0015,
            segs_a=6,
        )

    return finish(bm)
'''

new_cheek_end = '''    # nose2: wider/longer cheek blend — softs WS-to-nose shoulder in plan/3/4
    for sign in (-1.0, 1.0):
        ys = [17.35, 16.90, 16.40, 15.95, 15.55]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(105),
            sign * math.radians(122),
            0.0015,
            segs_a=6,
        )

    # nose2b: crown sill fairing — fills top-down "shelf" between radome & glass
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

    return finish(bm)
'''

if "nose2b: crown sill fairing" in t:
    print("FAIRING already")
elif old_cheek_end in t:
    t = t.replace(old_cheek_end, new_cheek_end, 1)
    print("FAIRING exact")
else:
    # insert before "return finish(bm)" of cockpit_frames only
    idx = t.find("nose2: wider/longer cheek blend")
    if idx < 0:
        raise SystemExit("cheek block missing")
    # find return finish after cheek
    ret = t.find("    return finish(bm)\n", idx)
    if ret < 0:
        raise SystemExit("return after cheek missing")
    insert = '''
    # nose2b: crown sill fairing — fills top-down "shelf" between radome & glass
    _add_shell_sector(
        bm,
        [18.05, 17.85, 17.68, 17.55],
        -math.radians(42),
        math.radians(42),
        0.0012,
        segs_a=18,
    )
    _add_shell_sector(
        bm,
        [16.35, 16.18, 16.00],
        -math.radians(40),
        math.radians(40),
        0.0010,
        segs_a=16,
    )

'''
    t = t[:ret] + insert + t[ret:]
    print("FAIRING inserted")

# Guard doors
start, end = t.find("def cabin_door_frames"), t.find("def cabin_door_windows")
assert "add_rounded_frame(" not in t[start:end] or "never planar add_rounded_frame" in t[start:end]
# stricter: no call
import re as _re
assert not _re.search(r"(?m)^\s*add_rounded_frame\(", t[start:end])

p.write_text(t, encoding="utf-8")
assert "nose2b: r_off~0.003" in p.read_text(encoding="utf-8")
assert "nose2b: leave more skin" in p.read_text(encoding="utf-8")
print("NOSE2B_OK", p.stat().st_size)

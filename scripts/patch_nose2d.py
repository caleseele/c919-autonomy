# -*- coding: utf-8 -*-
"""nose2d: flange covers jagged punch rim (visible through glass in top-down)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

old = '''    panes = _cockpit_pane_defs()
    # nose2b: leave more skin under frames — smaller hole, less top-down ledge
    A_INSET = math.radians(1.45)
    Y_INSET = 0.058

    def _in_inset_pane(a, y, pane):
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        if not (lo + A_INSET <= a <= hi - A_INSET):
            return False
        y_fwd = pane["y_fwd"](a)
        y_aft = pane["y_aft"](a)
        y_lo, y_hi = (y_aft, y_fwd) if y_aft <= y_fwd else (y_fwd, y_aft)
        return (y_lo + Y_INSET) <= y <= (y_hi - Y_INSET)
'''

new = '''    panes = _cockpit_pane_defs()
    # nose2d: kill inset (hole) vs flange inset (cover) — flange MUST be larger
    # so opaque rim hides jagged lathe-boundary seen through glass in top-down.
    A_INSET_KILL = math.radians(1.55)
    Y_INSET_KILL = 0.062
    A_INSET = A_INSET_KILL  # used by _in_inset_pane for kill
    Y_INSET = Y_INSET_KILL

    def _in_inset_pane(a, y, pane):
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        if not (lo + A_INSET <= a <= hi - A_INSET):
            return False
        y_fwd = pane["y_fwd"](a)
        y_aft = pane["y_aft"](a)
        y_lo, y_hi = (y_aft, y_fwd) if y_aft <= y_fwd else (y_fwd, y_aft)
        return (y_lo + Y_INSET) <= y <= (y_hi - Y_INSET)
'''

if "nose2d: kill inset" in t:
    print("KILL already")
elif old in t:
    t = t.replace(old, new, 1)
    print("KILL exact")
else:
    raise SystemExit("kill inset block not found")

# Replace _outline to use near-zero inset (covers kill jaggedness)
old_outline = '''    def _outline(pane):
        """CCW outline of inset pane in (a,y) space: fwd → right → aft → left."""
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        a_lo, a_hi = lo + A_INSET, hi - A_INSET
        pts = []
        # forward edge a_lo → a_hi
        for i in range(SEGS_A + 1):
            a = _lerp(a_lo, a_hi, i / float(SEGS_A))
            pts.append((a, pane["y_fwd"](a) - Y_INSET))
        # right edge aftward
        for j in range(1, SEGS_Y + 1):
            t = j / float(SEGS_Y)
            a = a_hi
            y = _lerp(pane["y_fwd"](a) - Y_INSET, pane["y_aft"](a) + Y_INSET, t)
            pts.append((a, y))
        # aft edge a_hi → a_lo
        for i in range(1, SEGS_A + 1):
            a = _lerp(a_hi, a_lo, i / float(SEGS_A))
            pts.append((a, pane["y_aft"](a) + Y_INSET))
        # left edge forward
        for j in range(1, SEGS_Y):
            t = j / float(SEGS_Y)
            a = a_lo
            y = _lerp(pane["y_aft"](a) + Y_INSET, pane["y_fwd"](a) - Y_INSET, t)
            pts.append((a, y))
        return pts
'''

new_outline = '''    def _outline(pane, a_ins, y_ins):
        """CCW outline in (a,y): fwd → right → aft → left."""
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        a_lo, a_hi = lo + a_ins, hi - a_ins
        pts = []
        for i in range(SEGS_A + 1):
            a = _lerp(a_lo, a_hi, i / float(SEGS_A))
            pts.append((a, pane["y_fwd"](a) - y_ins))
        for j in range(1, SEGS_Y + 1):
            tt = j / float(SEGS_Y)
            a = a_hi
            y = _lerp(pane["y_fwd"](a) - y_ins, pane["y_aft"](a) + y_ins, tt)
            pts.append((a, y))
        for i in range(1, SEGS_A + 1):
            a = _lerp(a_hi, a_lo, i / float(SEGS_A))
            pts.append((a, pane["y_aft"](a) + y_ins))
        for j in range(1, SEGS_Y):
            tt = j / float(SEGS_Y)
            a = a_lo
            y = _lerp(pane["y_aft"](a) + y_ins, pane["y_fwd"](a) - y_ins, tt)
            pts.append((a, y))
        return pts
'''

if "def _outline(pane, a_ins, y_ins):" in t:
    print("OUTLINE already")
elif old_outline in t:
    t = t.replace(old_outline, new_outline, 1)
    print("OUTLINE exact")
else:
    # encoding arrows may differ
    pat = re.compile(
        r"    def _outline\(pane\):\n.*?        return pts\n",
        re.S,
    )
    if not pat.search(t):
        raise SystemExit("_outline not found")
    t = pat.sub(new_outline, t, count=1)
    print("OUTLINE regex")

# Replace flange construction loop to use cover outline + kill-sized inner
old_loop = '''    for pane in panes:
        outline = _outline(pane)
        n = len(outline)
        if n < 8:
            continue
        outer = [bm.verts.new(_canopy_point(a, y, -0.0005)) for a, y in outline]
        inner = [bm.verts.new(_canopy_point(a, y, -FLANGE_DEPTH)) for a, y in outline]
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
            except ValueError:
                pass
'''

new_loop = '''    # nose2d: COVER ring near pane edge (hides jagged kill), inner at kill size
    A_COVER, Y_COVER = math.radians(0.35), 0.014
    for pane in panes:
        cover = _outline(pane, A_COVER, Y_COVER)
        kill_o = _outline(pane, A_INSET_KILL, Y_INSET_KILL)
        n = len(cover)
        if n < 8 or len(kill_o) != n:
            continue
        # Outer opaque lip on skin — covers stairstep hole edge under glass
        outer = [bm.verts.new(_canopy_point(a, y, 0.0008)) for a, y in cover]
        mid = [bm.verts.new(_canopy_point(a, y, -0.002)) for a, y in cover]
        inner = [bm.verts.new(_canopy_point(a, y, -FLANGE_DEPTH)) for a, y in kill_o]
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((outer[i], outer[j], mid[j], mid[i]))
                bm.faces.new((mid[i], mid[j], inner[j], inner[i]))
            except ValueError:
                pass
'''

if "nose2d: COVER ring" in t:
    print("LOOP already")
elif old_loop in t:
    t = t.replace(old_loop, new_loop, 1)
    print("LOOP exact")
else:
    pat = re.compile(
        r"    for pane in panes:\n        outline = _outline\(pane\).*?except ValueError:\n                pass\n",
        re.S,
    )
    if not pat.search(t):
        raise SystemExit("flange loop not found")
    t = pat.sub(new_loop, t, count=1)
    print("LOOP regex")

# Stronger dissolve of jagged boundary
t = t.replace(
    "    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.024]",
    "    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.038]",
    1,
)

# door guard
start, end = t.find("def cabin_door_frames"), t.find("def cabin_door_windows")
assert not re.search(r"(?m)^\s*add_rounded_frame\(", t[start:end])

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
assert "nose2d: COVER ring" in tt
assert "def _outline(pane, a_ins, y_ins):" in tt
print("NOSE2D_OK", p.stat().st_size)

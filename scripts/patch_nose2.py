# -*- coding: utf-8 -*-
"""nose2: soften windshield–nose top-down step; denser elliptical stations.

Does NOT touch doors, wings, engines, gear, or tail1.
Keeps inside1 punch + thin WS frames (no pipe tubes, no full cavity).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

# --- 1) Denser NOSE_PROFILE through windshield belt (smoother planform) ---
old_nose = '''NOSE_PROFILE = [
    # nose4b: fuller blunt tip (commercial dome, not missile) — DO NOT CHANGE tip
    # tip rx/rz 0.55/0.50 vs nose3 0.22/0.19 (~2.5x)
    (19.88, 0.55, 0.50),
    (19.75, 0.70, 0.63),
    (19.58, 0.86, 0.78),
    (19.38, 1.00, 0.92),
    (19.15, 1.13, 1.05),
    (18.88, 1.26, 1.18),
    (18.58, 1.38, 1.30),
    (18.25, 1.49, 1.41),
    (17.88, 1.59, 1.52),
    (17.48, 1.68, 1.62),
    (17.05, 1.77, 1.71),
    (16.58, 1.85, 1.80),
    (16.08, 1.92, 1.88),
    (15.58, 1.98, 1.95),
    (15.15, 2.02, 2.01),
    (14.95, 2.05, 2.05),
    (14.85, 2.06, 2.06),
]'''

new_nose = '''NOSE_PROFILE = [
    # nose4b tip kept (commercial dome) — nose2 densifies windshield belt only
    # tip rx/rz 0.55/0.50 — DO NOT sharpen tip
    (19.88, 0.55, 0.50),
    (19.75, 0.70, 0.63),
    (19.58, 0.86, 0.78),
    (19.38, 1.00, 0.92),
    (19.15, 1.13, 1.05),
    (18.88, 1.26, 1.18),
    (18.58, 1.38, 1.30),
    (18.40, 1.44, 1.36),  # nose2: denser into radome/WS
    (18.25, 1.49, 1.41),
    (18.05, 1.55, 1.47),
    (17.88, 1.59, 1.52),
    (17.68, 1.64, 1.57),  # windshield sill band
    (17.48, 1.68, 1.62),
    (17.28, 1.72, 1.66),
    (17.05, 1.77, 1.71),
    (16.82, 1.81, 1.75),
    (16.58, 1.85, 1.80),
    (16.32, 1.89, 1.84),  # brow / aft glass
    (16.08, 1.92, 1.88),
    (15.82, 1.95, 1.92),
    (15.58, 1.98, 1.95),
    (15.35, 2.00, 1.98),
    (15.15, 2.02, 2.01),
    (14.95, 2.05, 2.05),
    (14.85, 2.06, 2.06),
]'''

# Tolerate encoding of em-dash / comments via regex replace of the list body
pat_nose = re.compile(
    r"NOSE_PROFILE = \[(?:.|\n)*?\n\]",
    re.M,
)
m = pat_nose.search(t)
if not m:
    raise SystemExit("NOSE_PROFILE not found")
# Safety: must still start near tip 19.88 / 0.55
if "(19.88, 0.55, 0.50)" not in m.group(0):
    raise SystemExit("unexpected tip station; abort")
if "nose2 densifies" in m.group(0):
    print("NOSE_PROFILE already patched")
else:
    t = pat_nose.sub(new_nose, t, count=1)
    print("NOSE_PROFILE densified")

# --- 2) Softer pane Y curves: reduce outboard-forward jut (top-down step) ---
old_panes = '''def _cockpit_pane_defs():
    """C919 four load-bearing windshield panes (not a six-pane A320/737).

    Two large forward panes + two cheek panes. Edges hug the elliptical
    fuselage; gaps between panes are only ~2 deg so white skin does not
    read as oversized frames. Angle 0 = crown (+Z). L/R exact mirrors.
    """

    def fwd_y_fwd(a):
        t = abs(a) / math.radians(48)
        return _lerp(17.48, 17.68, min(1.0, t))

    def fwd_y_aft(a):
        t = abs(a) / math.radians(48)
        return _lerp(16.12, 16.35, min(1.0, t))

    def side_y_fwd(a):
        t = (abs(a) - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(17.58, 16.88, t)

    def side_y_aft(a):
        t = (abs(a) - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.22, 15.48, 0.30 * t * t + 0.70 * t)
'''

new_panes = '''def _cockpit_pane_defs():
    """C919 four load-bearing windshield panes (not a six-pane A320/737).

    Two large forward panes + two cheek panes. Edges hug the elliptical
    fuselage; gaps between panes are only ~2 deg so white skin does not
    read as oversized frames. Angle 0 = crown (+Z). L/R exact mirrors.

    nose2: sill/brow Y curves are smooth convex in plan (center slightly
    more forward than cheeks) so top-down no longer reads as a stepped
    windshield block sitting on the radome.
    """

    def fwd_y_fwd(a):
        # Center proud, cheeks gently aft — ogive wrap, not outboard jut
        t = abs(a) / math.radians(48)
        t = min(1.0, t)
        # smoothstep for continuous silhouette
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.62, 17.52, s)

    def fwd_y_aft(a):
        t = abs(a) / math.radians(48)
        t = min(1.0, t)
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(16.18, 16.32, s)

    def side_y_fwd(a):
        t = (abs(a) - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        # Continue from fwd cheek (~17.52) aft-sweeping smoothly
        return _lerp(17.50, 16.92, s)

    def side_y_aft(a):
        t = (abs(a) - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(16.30, 15.55, s)
'''

if "nose2: sill/brow Y curves" in t:
    print("PANES already patched")
else:
    if old_panes not in t:
        # Try regex on function header through side_y_aft
        pat = re.compile(
            r"def _cockpit_pane_defs\(\):\n(?:.*\n)*?    def side_y_aft\(a\):\n(?:.*\n)*?        return _lerp\(16\.22, 15\.48, 0\.30 \* t \* t \+ 0\.70 \* t\)\n",
            re.M,
        )
        m = pat.search(t)
        if not m:
            raise SystemExit("_cockpit_pane_defs Y helpers not found for replace")
        t = pat.sub(new_panes, t, count=1)
        print("PANES replaced via regex")
    else:
        t = t.replace(old_panes, new_panes, 1)
        print("PANES replaced exact")

# --- 3) Match cockpit_frames sill/brow helpers to the new pane curves ---
old_sill = '''    def sill_y(a):
        aa = abs(a)
        if aa <= math.radians(48):
            t = aa / math.radians(48)
            return _lerp(17.48, 17.68, t)
        t = (aa - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(17.58, 16.88, t)

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(48):
            t = aa / math.radians(48)
            return _lerp(16.12, 16.35, t)
        t = (aa - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.22, 15.48, 0.30 * t * t + 0.70 * t)
'''

new_sill = '''    def sill_y(a):
        # nose2: match pane fwd edges (smoothstep, center-forward)
        aa = abs(a)
        if aa <= math.radians(48):
            t = min(1.0, aa / math.radians(48))
            s = t * t * (3.0 - 2.0 * t)
            return _lerp(17.62, 17.52, s)
        t = (aa - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.50, 16.92, s)

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(48):
            t = min(1.0, aa / math.radians(48))
            s = t * t * (3.0 - 2.0 * t)
            return _lerp(16.18, 16.32, s)
        t = (aa - math.radians(50)) / (math.radians(110) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(16.30, 15.55, s)
'''

if "nose2: match pane fwd edges" in t:
    print("SILL/BROW already patched")
else:
    if old_sill not in t:
        pat = re.compile(
            r"    def sill_y\(a\):\n(?:.*\n)*?    def brow_y\(a\):\n(?:.*\n)*?        return _lerp\(16\.22, 15\.48, 0\.30 \* t \* t \+ 0\.70 \* t\)\n",
            re.M,
        )
        m = pat.search(t)
        if not m:
            raise SystemExit("sill_y/brow_y not found")
        t = pat.sub(new_sill, t, count=1)
        print("SILL/BROW replaced via regex")
    else:
        t = t.replace(old_sill, new_sill, 1)
        print("SILL/BROW replaced exact")

# --- 4) Stronger cheek blend strip (skin-like, fills WS/nose step in plan) ---
old_cheek = '''    # Very flat cheek blend (skin-like, not a raised tube)
    for sign in (-1.0, 1.0):
        ys = [16.80, 16.35, 15.90, 15.50]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(108),
            sign * math.radians(118),
            0.002,
            segs_a=4,
        )
'''

new_cheek = '''    # nose2: wider/longer cheek blend — softs WS-to-nose shoulder in plan/3/4
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
'''

if "nose2: wider/longer cheek blend" in t:
    print("CHEEK already patched")
else:
    if old_cheek not in t:
        pat = re.compile(
            r"    # Very flat cheek blend.*?\n(?:    .*\n)*?            segs_a=4,\n        \)\n",
            re.M,
        )
        m = pat.search(t)
        if not m:
            raise SystemExit("cheek blend block not found")
        t = pat.sub(new_cheek, t, count=1)
        print("CHEEK replaced via regex")
    else:
        t = t.replace(old_cheek, new_cheek, 1)
        print("CHEEK replaced exact")

# --- 5) Soften radome parting ring (less hard step at y=18.48 in top view) ---
# Keep it but slightly thinner / lower
old_ring = "(18.48, 0.020, 0.016),  # DISTINCT radome parting only"
new_ring = "(18.48, 0.014, 0.010),  # nose2: softer radome parting (less top-down step)"
if new_ring in t:
    print("RING already patched")
elif old_ring in t:
    t = t.replace(old_ring, new_ring, 1)
    print("RING softened")
else:
    print("WARN: radome ring line not found (skip)")

# Safety: door2e markers must remain
if "door2e:" not in t and "door2: never planar" not in t.lower() and "door2: NEVER emit planar" not in t and "never planar add_rounded_frame" not in t:
    # accept door2e docstring variants
    if "r_off=0.005" not in t or "cabin_door_frames" not in t:
        raise SystemExit("door2 markers missing — abort to protect doors")
print("DOOR2_PRESERVED_OK")

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
assert "(17.68, 1.64, 1.57)" in tt
assert "nose2: sill/brow Y curves" in tt or "ogive wrap" in tt
assert "add_rounded_frame(" not in tt[tt.find("def cabin_door_frames"):tt.find("def cabin_door_windows")]
print("NOSE2_PATCH_OK", p.stat().st_size)

from pathlib import Path
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = p.read_text(encoding="utf-8")

old_prof = '''NOSE_PROFILE = [
    (20.05, 0.20, 0.17),
    (19.88, 0.30, 0.26),
    (19.68, 0.42, 0.36),
    (19.46, 0.54, 0.47),
    (19.22, 0.66, 0.58),
    (18.96, 0.78, 0.70),
    (18.68, 0.90, 0.82),
    (18.38, 1.02, 0.94),
    (18.05, 1.15, 1.08),
    (17.70, 1.28, 1.22),
    (17.32, 1.42, 1.36),
    (16.90, 1.55, 1.50),
    (16.45, 1.68, 1.64),
    (15.98, 1.80, 1.77),
    (15.50, 1.91, 1.89),
    (15.10, 1.99, 1.98),
    (14.85, 2.06, 2.06),
]
'''

# Tangent-ogive-like stations: soft tip, continuous curvature (not linear cone, not ball).
# Base L≈5.15 (y 20.0→14.85), R=2.06. Slightly wider than tall forward.
new_prof = '''NOSE_PROFILE = [
    # Soft rounded tip (not needle, not hemisphere)
    (20.08, 0.22, 0.19),
    (19.92, 0.34, 0.29),
    (19.72, 0.48, 0.42),
    (19.50, 0.62, 0.55),
    (19.25, 0.76, 0.69),
    (18.98, 0.90, 0.83),
    (18.68, 1.04, 0.97),
    (18.35, 1.18, 1.12),
    (18.00, 1.32, 1.26),
    (17.62, 1.45, 1.40),
    (17.20, 1.58, 1.54),
    (16.75, 1.70, 1.66),
    (16.28, 1.81, 1.78),
    (15.78, 1.90, 1.88),
    (15.30, 1.98, 1.97),
    (14.98, 2.03, 2.03),
    (14.85, 2.06, 2.06),
]
'''

if old_prof not in text:
    raise SystemExit("PROF2_NOT_FOUND")
text = text.replace(old_prof, new_prof, 1)

old_panes = '''def _cockpit_pane_defs():
    """C919 four load-bearing windshield panes (not a six-pane A320/737).

    Two large forward panes + two cheek panes. All edges follow the
    elliptical fuselage so glass is a curved shell, not flat black patches.
    Angle 0 = crown (+Z). L/R are exact mirrors.
    """
    # Forward pair: slightly raked sill (lower toward centerline) and brow
    # that drops a little toward the center post — matches the real bow.

    def fwd_y_fwd(a):
        t = abs(a) / math.radians(46)
        return _lerp(17.55, 17.72, min(1.0, t))

    def fwd_y_aft(a):
        t = abs(a) / math.radians(46)
        return _lerp(16.18, 16.38, min(1.0, t))

    def side_y_fwd(a):
        # From the side-post (~50 deg) down the cheek: leading edge rakes aft.
        t = (abs(a) - math.radians(54)) / (math.radians(108) - math.radians(54) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(17.62, 16.95, t)

    def side_y_aft(a):
        t = (abs(a) - math.radians(54)) / (math.radians(108) - math.radians(54) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.28, 15.55, t * t * 0.35 + t * 0.65)

    return [
        {
            "name": "side_L",
            "a0": -math.radians(108),
            "a1": -math.radians(54),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 20,
            "segs_y": 14,
        },
        {
            "name": "fwd_L",
            "a0": -math.radians(46),
            "a1": -math.radians(5.5),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 16,
            "segs_y": 12,
        },
        {
            "name": "fwd_R",
            "a0": math.radians(5.5),
            "a1": math.radians(46),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 16,
            "segs_y": 12,
        },
        {
            "name": "side_R",
            "a0": math.radians(54),
            "a1": math.radians(108),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 20,
            "segs_y": 14,
        },
    ]
'''

new_panes = '''def _cockpit_pane_defs():
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

    return [
        {
            "name": "side_L",
            "a0": -math.radians(110),
            "a1": -math.radians(50),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 22,
            "segs_y": 14,
        },
        {
            "name": "fwd_L",
            "a0": -math.radians(48),
            "a1": -math.radians(2.8),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 18,
            "segs_y": 12,
        },
        {
            "name": "fwd_R",
            "a0": math.radians(2.8),
            "a1": math.radians(48),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 18,
            "segs_y": 12,
        },
        {
            "name": "side_R",
            "a0": math.radians(50),
            "a1": math.radians(110),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 22,
            "segs_y": 14,
        },
    ]
'''

if old_panes not in text:
    raise SystemExit("PANES2_NOT_FOUND")
text = text.replace(old_panes, new_panes, 1)

old_frames = '''    # Center post, two side posts, outer cheek posts — narrow azimuth.
    mullions = [
        (-math.radians(109.2), -math.radians(106.8), [16.95, 16.55, 16.15, 15.75, 15.52]),
        (math.radians(106.8), math.radians(109.2), [16.95, 16.55, 16.15, 15.75, 15.52]),
        (-math.radians(51.2), -math.radians(48.8), [17.68, 17.25, 16.85, 16.50, 16.32]),
        (math.radians(48.8), math.radians(51.2), [17.68, 17.25, 16.85, 16.50, 16.32]),
        (-math.radians(2.6), math.radians(2.6), [17.58, 17.15, 16.75, 16.40, 16.16]),
    ]
'''

new_frames = '''    # Center / side / outer posts — ~2 deg wide so they read as thin lines.
    mullions = [
        (-math.radians(111.0), -math.radians(109.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.0), math.radians(111.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (-math.radians(50.0), -math.radians(48.0), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.0), math.radians(50.0), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (-math.radians(2.0), math.radians(2.0), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
'''

if old_frames not in text:
    raise SystemExit("FRAMES2_NOT_FOUND")
text = text.replace(old_frames, new_frames, 1)

# Update sill/brow spans to match new pane extents
text2 = text
old_spans = '''    spans = [
        (-math.radians(108), -math.radians(54)),
        (-math.radians(46), math.radians(46)),
        (math.radians(54), math.radians(108)),
    ]
'''
new_spans = '''    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), math.radians(48)),
        (math.radians(50), math.radians(110)),
    ]
'''
if old_spans not in text2:
    raise SystemExit("SPANS_NOT_FOUND")
text2 = text2.replace(old_spans, new_spans, 1)

# Update sill/brow y_fn thresholds to 48/50/110
old_sill = '''    def sill_y(a):
        aa = abs(a)
        if aa <= math.radians(46):
            t = aa / math.radians(46)
            return _lerp(17.55, 17.72, t)
        t = (aa - math.radians(54)) / (math.radians(108) - math.radians(54) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(17.62, 16.95, t)

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(46):
            t = aa / math.radians(46)
            return _lerp(16.18, 16.38, t)
        t = (aa - math.radians(54)) / (math.radians(108) - math.radians(54) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.28, 15.55, t * t * 0.35 + t * 0.65)
'''
new_sill = '''    def sill_y(a):
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
if old_sill not in text2:
    raise SystemExit("SILL_NOT_FOUND")
text2 = text2.replace(old_sill, new_sill, 1)

p.write_text(text2, encoding="utf-8")
print("PATCH2_OK")

from pathlib import Path
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = p.read_text(encoding="utf-8")

old_nose = '''def nose_with_cap(profile, segments=None):
    """Lathe nose + shallow rounded tip (no full-hemisphere equator cusp)."""
    segs = segments or SEGMENTS
    bm = bmesh.new()
    rings = []
    for y, radius in profile:
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * radius, y, math.sin(ang) * radius))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    # Denser tip rings: smoother ogive taper into a soft blunt face.
    y0, r0 = profile[0]
    tip_spec = [
        (y0 + 0.04, r0 * 0.90),
        (y0 + 0.08, r0 * 0.78),
        (y0 + 0.12, r0 * 0.64),
        (y0 + 0.16, r0 * 0.50),
        (y0 + 0.195, max(0.13, r0 * 0.36)),
    ]
    prev = rings[0]
    for yy, rr in tip_spec:
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rr, yy, math.sin(ang) * rr))
            )
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    r_last = max(0.13, r0 * 0.36)
    pole = bm.verts.new((0.0, y0 + 0.195 + r_last * 0.30, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)
'''

new_nose = '''def nose_with_cap(profile, segments=None):
    """Elliptical-station nose + soft rounded radome tip (not a hemisphere).

    Each station is (y, rx, rz). rx is lateral half-width, rz is vertical
    half-height. The tip continues the same ellipse ratio instead of a ball.
    """
    segs = segments or SEGMENTS
    bm = bmesh.new()

    def ring_at(y, rx, rz):
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rx, y, math.sin(ang) * rz))
            )
        return ring

    rings = [ring_at(y, rx, rz) for y, rx, rz in profile]
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    # Soft tip: same ellipse ratio, short axial cap. Not a sphere, not a needle.
    y0, rx0, rz0 = profile[0]
    tip_spec = [
        (0.045, 0.86),
        (0.085, 0.70),
        (0.120, 0.54),
        (0.150, 0.38),
        (0.172, 0.24),
    ]
    prev = rings[0]
    for dy, s in tip_spec:
        ring = ring_at(y0 + dy, rx0 * s, rz0 * s)
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    # Pole slightly proud of last ring so the tip stays rounded, not conical.
    pole = bm.verts.new((0.0, y0 + 0.172 + min(rx0, rz0) * 0.24 * 0.55, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)
'''

if old_nose not in text:
    raise SystemExit("NOSE_FN_NOT_FOUND")
text = text.replace(old_nose, new_nose, 1)

old_prof = '''# Shared nose+fuselage lathe stations. Tip is a ROUNDED radome (not a needle).
# Y increases toward the nose (+Y). Radius is circular cross-section radius.
NOSE_PROFILE = [
    # Softer ogive denser near tip; subtle break approaching fuselage join.
    (19.72, 0.34),
    (19.58, 0.48),
    (19.42, 0.64),
    (19.24, 0.80),
    (19.02, 0.96),
    (18.76, 1.12),
    (18.45, 1.28),
    (18.08, 1.44),
    (17.65, 1.58),
    (17.15, 1.72),
    (16.55, 1.86),
    (15.95, 1.96),
    (15.40, 2.02),
    (15.05, 2.05),
    (14.85, 2.06),
]
'''

new_prof = '''# Nose stations: (y, rx, rz). Y toward the nose (+Y).
# rx = lateral half-width, rz = vertical half-height.
# Elongated C919 radome: less spherical mid-bulge, tip stays softly rounded.
# Join at y=14.85 matches the circular fuselage (rx=rz=2.06).
NOSE_PROFILE = [
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

if old_prof not in text:
    raise SystemExit("PROFILE_NOT_FOUND")
text = text.replace(old_prof, new_prof, 1)

old_rad = '''def _radius_at_y(y):
    """Fuselage/nose radius from the lathe stations used in build()."""
    stations = RADIUS_STATIONS
    if y >= stations[0][0]:
        return stations[0][1]
    if y <= stations[-1][0]:
        return stations[-1][1]
    for (y0, r0), (y1, r1) in zip(stations, stations[1:]):
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1 + 1e-9)
            return r0 + (r1 - r0) * t
    return 2.08
'''

new_rad = '''def _section_at_y(y):
    """(rx, rz) at station y. Nose stations are elliptical; fuselage is circular."""
    stations = RADIUS_STATIONS
    if y >= stations[0][0]:
        s = stations[0]
        return (s[1], s[2] if len(s) > 2 else s[1])
    if y <= stations[-1][0]:
        s = stations[-1]
        return (s[1], s[2] if len(s) > 2 else s[1])
    for s0, s1 in zip(stations, stations[1:]):
        y0, y1 = s0[0], s1[0]
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1 + 1e-9)
            rx0, rz0 = s0[1], (s0[2] if len(s0) > 2 else s0[1])
            rx1, rz1 = s1[1], (s1[2] if len(s1) > 2 else s1[1])
            return (rx0 + (rx1 - rx0) * t, rz0 + (rz1 - rz0) * t)
    return (2.08, 2.08)


def _radius_at_y(y):
    """Mean radius (legacy callers: panel rings, antennas, gear doors)."""
    rx, rz = _section_at_y(y)
    return 0.5 * (rx + rz)
'''

if old_rad not in text:
    raise SystemExit("RADIUS_NOT_FOUND")
text = text.replace(old_rad, new_rad, 1)

old_canopy = '''def _canopy_point(a, y, r_off):
    """Point on the circular nose cross-section. a=0 is crown (+Z)."""
    r = _radius_at_y(y) + r_off
    return (math.sin(a) * r, y, math.cos(a) * r)
'''

new_canopy = '''def _canopy_point(a, y, r_off):
    """Point on the elliptical nose section. a=0 is crown (+Z).

    Offset is along the section normal so glass/frames hug the skin
    instead of inflating into a larger circle.
    """
    rx, rz = _section_at_y(y)
    # Unit ellipse param (a measured from +Z): x = rx*sin(a), z = rz*cos(a)
    sx, sz = math.sin(a), math.cos(a)
    # Outward normal of ellipse x^2/rx^2 + z^2/rz^2 = 1
    nx, nz = sx / max(rx, 1e-6), sz / max(rz, 1e-6)
    nlen = math.hypot(nx, nz) or 1.0
    nx, nz = nx / nlen, nz / nlen
    return (sx * rx + nx * r_off, y, sz * rz + nz * r_off)
'''

if old_canopy not in text:
    raise SystemExit("CANOPY_NOT_FOUND")
text = text.replace(old_canopy, new_canopy, 1)

old_panes = '''def _cockpit_pane_defs():
    """Real C919 front photo: 2 large central windshields + 2 aft-raked side panes.

    Side panes sweep aft and taper toward the rear along the nose curve
    (leading edge also rakes back as azimuth increases). Thin gaps for mullions.
    Angle 0 = crown (+Z).
    """
    # Forward panes — large central pair; sill sits below radome dome
    fwd_y0, fwd_y1 = 18.05, 16.30

    def side_y_fwd(a, a_upper, a_lower):
        t = abs((abs(a) - abs(a_upper)) / (abs(a_lower) - abs(a_upper) + 1e-9))
        # Leading edge rakes aft down the flank (front photo wrap)
        return _lerp(17.98, 17.25, t)

    def side_y_aft(a, a_upper, a_lower):
        t = abs((abs(a) - abs(a_upper)) / (abs(a_lower) - abs(a_upper) + 1e-9))
        # Trailing edge sweeps further aft and tapers
        return _lerp(16.40, 15.30, t)

    return [
        {
            "name": "side_L",
            "a0": -math.radians(118),
            "a1": -math.radians(54),
            "y_fwd": lambda a: side_y_fwd(a, math.radians(52), math.radians(120)),
            "y_aft": lambda a: side_y_aft(a, math.radians(52), math.radians(120)),
            "segs_a": 24,
            "segs_y": 16,
        },
        {
            "name": "fwd_L",
            "a0": -math.radians(48),
            "a1": -math.radians(7),
            "y_fwd": lambda a: fwd_y0,
            "y_aft": lambda a: fwd_y1,
            "segs_a": 18,
            "segs_y": 14,
        },
        {
            "name": "fwd_R",
            "a0": math.radians(7),
            "a1": math.radians(48),
            "y_fwd": lambda a: fwd_y0,
            "y_aft": lambda a: fwd_y1,
            "segs_a": 18,
            "segs_y": 14,
        },
        {
            "name": "side_R",
            "a0": math.radians(54),
            "a1": math.radians(118),
            "y_fwd": lambda a: side_y_fwd(a, math.radians(52), math.radians(120)),
            "y_aft": lambda a: side_y_aft(a, math.radians(52), math.radians(120)),
            "segs_a": 24,
            "segs_y": 16,
        },
    ]
'''

new_panes = '''def _cockpit_pane_defs():
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

if old_panes not in text:
    raise SystemExit("PANES_NOT_FOUND")
text = text.replace(old_panes, new_panes, 1)

old_ws = '''def cockpit_windshield():
    """Four smooth panoramic canopy panes fused to the radome silhouette.

    Slightly proud of the skin so dark glass reads as panes (not holes).
    No boolean cuts — no floating shards.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        _add_canopy_pane(bm, pane, r_off=0.016)
    return finish(bm)
'''

new_ws = '''def cockpit_windshield():
    """Four curved C919 windshield panes sampled on the fuselage ellipse.

    Thin proud offset so dark glass reads as panes without looking pasted.
    No boolean cuts.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        _add_canopy_pane(bm, pane, r_off=0.012)
    return finish(bm)
'''

if old_ws not in text:
    raise SystemExit("WS_NOT_FOUND")
text = text.replace(old_ws, new_ws, 1)

old_frames = '''def cockpit_frames():
    """Flush dark mullions + brow/sill; cheek fairing into fuselage.

    Real C919 frames are slim lines flush with the canopy, not tubular bars.
    Side mullions follow the aft-raked side-pane edges from the front photo.
    """
    bm = bmesh.new()
    r_off = 0.026  # just proud of glass (glass at +0.016)

    # Vertical mullions — narrower azimuth for sharper frame read
    mullions = [
        (-math.radians(119.5), -math.radians(117.2), [17.25, 16.8, 16.35, 15.9, 15.5, 15.28]),
        (math.radians(117.2), math.radians(119.5), [17.25, 16.8, 16.35, 15.9, 15.5, 15.28]),
        (-math.radians(51.6), -math.radians(50.0), [18.02, 17.45, 16.9, 16.5, 16.30]),
        (math.radians(50.0), math.radians(51.6), [18.02, 17.45, 16.9, 16.5, 16.30]),
        (-math.radians(3.6), math.radians(3.6), [18.08, 17.45, 16.9, 16.55, 16.28]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=3)

    def sill_y(a):
        tt = min(1.0, abs(a) / math.radians(118))
        return _lerp(18.08, 17.28, tt * tt)

    def brow_y(a):
        tt = min(1.0, abs(a) / math.radians(118))
        return _lerp(16.30, 15.32, tt)

    a_list = [_lerp(-math.radians(118), math.radians(118), i / 60.0) for i in range(61)]
    for y_fn, half in ((sill_y, 0.022), (brow_y, 0.022)):
        row_u, row_l = [], []
        for a in a_list:
            y = y_fn(a)
            row_u.append(bm.verts.new(_canopy_point(a, y + half, r_off)))
            row_l.append(bm.verts.new(_canopy_point(a, y - half, r_off)))
        for i in range(len(a_list) - 1):
            bm.faces.new((row_u[i], row_u[i + 1], row_l[i + 1], row_l[i]))

    # Cheek fairing ribbons: soften windshield→fuselage "pasted" look
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(100)
        a1 = sign * math.radians(125)
        ys = [17.6, 17.1, 16.5, 15.9, 15.35]
        _add_shell_sector(bm, ys, min(a0, a1), max(a0, a1), 0.012, segs_a=6)
        # Brow cheek blend above side panes
        ys2 = [16.45, 16.05, 15.55, 15.15]
        _add_shell_sector(
            bm, ys2,
            sign * math.radians(48),
            sign * math.radians(70),
            0.010,
            segs_a=5,
        )

    return finish(bm)
'''

new_frames = '''def cockpit_frames():
    """Thin mullions + brow/sill that follow the four curved panes.

    Frames sit just proud of the glass and track the same y(a) edges,
    so there is no stepped break between glass and structure.
    """
    bm = bmesh.new()
    r_off = 0.020  # just proud of glass (glass at +0.012)

    # Center post, two side posts, outer cheek posts — narrow azimuth.
    mullions = [
        (-math.radians(109.2), -math.radians(106.8), [16.95, 16.55, 16.15, 15.75, 15.52]),
        (math.radians(106.8), math.radians(109.2), [16.95, 16.55, 16.15, 15.75, 15.52]),
        (-math.radians(51.2), -math.radians(48.8), [17.68, 17.25, 16.85, 16.50, 16.32]),
        (math.radians(48.8), math.radians(51.2), [17.68, 17.25, 16.85, 16.50, 16.32]),
        (-math.radians(2.6), math.radians(2.6), [17.58, 17.15, 16.75, 16.40, 16.16]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=2)

    def sill_y(a):
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

    # Two arcs: forward pair, then each cheek (gap at the side post).
    spans = [
        (-math.radians(108), -math.radians(54)),
        (-math.radians(46), math.radians(46)),
        (math.radians(54), math.radians(108)),
    ]
    for a0, a1 in spans:
        a_list = [_lerp(a0, a1, i / 28.0) for i in range(29)]
        for y_fn, half in ((sill_y, 0.016), (brow_y, 0.016)):
            row_u, row_l = [], []
            for a in a_list:
                y = y_fn(a)
                row_u.append(bm.verts.new(_canopy_point(a, y + half, r_off)))
                row_l.append(bm.verts.new(_canopy_point(a, y - half, r_off)))
            for i in range(len(a_list) - 1):
                bm.faces.new((row_u[i], row_u[i + 1], row_l[i + 1], row_l[i]))

    # Low cheek blend just outside the side panes — thin, on-surface.
    for sign in (-1.0, 1.0):
        ys = [16.85, 16.40, 15.95, 15.50]
        _add_shell_sector(
            bm, ys,
            sign * math.radians(100),
            sign * math.radians(114),
            0.008,
            segs_a=4,
        )

    return finish(bm)
'''

if old_frames not in text:
    raise SystemExit("FRAMES_NOT_FOUND")
text = text.replace(old_frames, new_frames, 1)

old_note = 'print("C919_NOTE nose-engine=ogive120+radome-seam+cheek-frames+leap-lip-fan18+pylon-fairing")'
new_note = 'print("C919_NOTE nose3=ellipse-ogive+4pane-curved-ws")'
if old_note not in text:
    raise SystemExit("NOTE_NOT_FOUND")
text = text.replace(old_note, new_note, 1)

# Pitot positions: slightly lower/aft so they stay on the slimmer nose
old_pitot = '''    specs = [
        (1.05, 18.55, -0.35, 0.035, 0.22),
        (-1.05, 18.55, -0.35, 0.035, 0.22),
        (0.95, 18.85, -0.55, 0.028, 0.18),
        (-0.95, 18.85, -0.55, 0.028, 0.18),
    ]'''
new_pitot = '''    specs = [
        (0.92, 18.15, -0.42, 0.032, 0.20),
        (-0.92, 18.15, -0.42, 0.032, 0.20),
        (0.78, 18.55, -0.58, 0.026, 0.16),
        (-0.78, 18.55, -0.58, 0.026, 0.16),
    ]'''
if old_pitot not in text:
    raise SystemExit("PITOT_NOT_FOUND")
text = text.replace(old_pitot, new_pitot, 1)

p.write_text(text, encoding="utf-8")
print("PATCH_OK", len(text))

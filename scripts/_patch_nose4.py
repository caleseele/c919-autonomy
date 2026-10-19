# -*- coding: utf-8 -*-
"""nose4: blunter radome, parting ring, soft WS, door/window bezels, static ports."""
from pathlib import Path

p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = p.read_text(encoding="utf-8")
orig = text

# --- 1. nose_with_cap: blunter parabolic tip cap ---
old_nose_fn = '''def nose_with_cap(profile, segments=None):
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

new_nose_fn = '''def nose_with_cap(profile, segments=None):
    """Elliptical-station nose + blunt parabolic radome tip (commercial jet).

    Each station is (y, rx, rz). Tip cap is short and fat — not a missile cone,
    not a sphere. Ratio stays elliptical through the pole.
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
    # Blunt parabolic tip: larger scale factors, short axial throw.
    y0, rx0, rz0 = profile[0]
    tip_spec = [
        (0.028, 0.94),
        (0.052, 0.86),
        (0.072, 0.74),
        (0.088, 0.58),
        (0.100, 0.40),
    ]
    prev = rings[0]
    for dy, s in tip_spec:
        ring = ring_at(y0 + dy, rx0 * s, rz0 * s)
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    # Pole close to last ring → rounded dome, not conical spike.
    pole = bm.verts.new((0.0, y0 + 0.100 + min(rx0, rz0) * 0.40 * 0.72, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)
'''

if old_nose_fn not in text:
    raise SystemExit("NOSE_FN_NOT_FOUND")
text = text.replace(old_nose_fn, new_nose_fn, 1)

# --- 2. NOSE_PROFILE: blunter tip stations ---
old_prof = '''NOSE_PROFILE = [
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

new_prof = '''NOSE_PROFILE = [
    # nose4: blunter parabolic tip (commercial, not missile cone)
    # tip rx/rz ~0.42/0.38 vs nose3 0.22/0.19; overall still elongated
    (19.95, 0.42, 0.38),
    (19.82, 0.56, 0.50),
    (19.65, 0.72, 0.65),
    (19.45, 0.88, 0.80),
    (19.22, 1.03, 0.95),
    (18.95, 1.17, 1.09),
    (18.65, 1.30, 1.22),
    (18.32, 1.42, 1.34),
    (17.95, 1.54, 1.46),
    (17.55, 1.65, 1.57),
    (17.12, 1.75, 1.68),
    (16.65, 1.84, 1.78),
    (16.15, 1.91, 1.87),
    (15.65, 1.97, 1.94),
    (15.20, 2.02, 2.01),
    (14.95, 2.05, 2.05),
    (14.85, 2.06, 2.06),
]
'''

if old_prof not in text:
    raise SystemExit("PROF_NOT_FOUND")
text = text.replace(old_prof, new_prof, 1)

# --- 3. cabin windows: recessed panes + thicker bezels ---
old_win = '''def cabin_windows():
    """Rounded flush cabin panes as thin decals (no protruding bricks)."""
    bm = bmesh.new()
    pane_w, pane_h = 0.30, 0.36
    corner = 0.08
    x_off = 2.086
    z = 0.58
    for y in _fuselage_window_ys():
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_decal(bm, pane_w, pane_h, corner, segs=6, matrix=m)
    return finish(bm)


def cabin_window_frames():
    """Hollow dark rounded frames as flush decals around each pane."""
    bm = bmesh.new()
    x_off = 2.083
    z = 0.58
    for y in _fuselage_window_ys():
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            # Use very thin slab frame rim (border) — depth tiny to avoid Lego look
            add_rounded_frame(
                bm, 0.38, 0.44, 0.004, 0.09, border=0.032, segs=6, matrix=m
            )
    return finish(bm)
'''

new_win = '''def cabin_windows():
    """Slightly recessed cabin panes with real depth (not flush black holes)."""
    bm = bmesh.new()
    pane_w, pane_h = 0.28, 0.34
    corner = 0.085
    x_off = 2.055  # recessed into skin (skin ~2.08)
    z = 0.58
    for y in _fuselage_window_ys():
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_slab(bm, pane_w, pane_h, 0.018, corner, segs=6, matrix=m)
    return finish(bm)


def cabin_window_frames():
    """Dark bezels with recess depth around each pane."""
    bm = bmesh.new()
    x_off = 2.078
    z = 0.58
    for y in _fuselage_window_ys():
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_frame(
                bm, 0.40, 0.46, 0.016, 0.095, border=0.038, segs=6, matrix=m
            )
    return finish(bm)
'''

if old_win not in text:
    raise SystemExit("WIN_NOT_FOUND")
text = text.replace(old_win, new_win, 1)

# --- 4. Windshield: denser double-curve + softer frames ---
old_ws = '''def cockpit_windshield():
    """Four curved C919 windshield panes sampled on the fuselage ellipse.

    Thin proud offset so dark glass reads as panes without looking pasted.
    No boolean cuts.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        _add_canopy_pane(bm, pane, r_off=0.012)
    return finish(bm)


def cockpit_frames():
    """Thin mullions + brow/sill that follow the four curved panes.

    Frames sit just proud of the glass and track the same y(a) edges,
    so there is no stepped break between glass and structure.
    """
    bm = bmesh.new()
    r_off = 0.020  # just proud of glass (glass at +0.012)

    # Center / side / outer posts — ~2 deg wide so they read as thin lines.
    mullions = [
        (-math.radians(111.0), -math.radians(109.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.0), math.radians(111.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (-math.radians(50.0), -math.radians(48.0), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.0), math.radians(50.0), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (-math.radians(2.0), math.radians(2.0), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=2)

    def sill_y(a):
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

    # Two arcs: forward pair, then each cheek (gap at the side post).
    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), math.radians(48)),
        (math.radians(50), math.radians(110)),
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

new_ws = '''def cockpit_windshield():
    """Four double-curved C919 windshield panes blended into the fuselage.

    Dense shell sampling for continuous double curvature. Soft proud offset.
    No boolean cuts.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        # denser grid → smoother double-curve shading
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 24)
        pane["segs_y"] = max(pane["segs_y"], 16)
        _add_canopy_pane(bm, pane, r_off=0.010)
    return finish(bm)


def cockpit_frames():
    """Soft thin mullions + brow/sill following the four curved panes.

    Narrow angular width and continuous ribbons — no hard stepped frames.
    """
    bm = bmesh.new()
    r_off = 0.016  # just proud of glass (glass at +0.010)

    # Narrow posts (~1.2 deg) — soft thin lines, not thick bars.
    mullions = [
        (-math.radians(110.6), -math.radians(109.4), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.4), math.radians(110.6), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (-math.radians(49.6), -math.radians(48.4), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.4), math.radians(49.6), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (-math.radians(1.2), math.radians(1.2), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=3)

    def sill_y(a):
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

    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), math.radians(48)),
        (math.radians(50), math.radians(110)),
    ]
    for a0, a1 in spans:
        a_list = [_lerp(a0, a1, i / 36.0) for i in range(37)]
        for y_fn, half in ((sill_y, 0.012), (brow_y, 0.012)):
            # Continuous ribbon with slight radial thickness for soft blend
            _add_curve_ribbon(bm, a_list, y_fn, half, r_in=0.006, r_out=r_off)

    # Soft cheek blend outside side panes
    for sign in (-1.0, 1.0):
        ys = [16.85, 16.40, 15.95, 15.50]
        _add_shell_sector(
            bm, ys,
            sign * math.radians(100),
            sign * math.radians(114),
            0.006,
            segs_a=5,
        )

    return finish(bm)
'''

if old_ws not in text:
    raise SystemExit("WS_NOT_FOUND")
text = text.replace(old_ws, new_ws, 1)

# --- 5. Pitot + static ports ---
old_pitot = '''def pitot_probes():
    """Small pitot/AOA probes on nose flanks (front-photo detail)."""
    bm = bmesh.new()
    # Short cylinders sticking out sideways below windshield sill
    specs = [
        (0.92, 18.15, -0.42, 0.032, 0.20),
        (-0.92, 18.15, -0.42, 0.032, 0.20),
        (0.78, 18.55, -0.58, 0.026, 0.16),
        (-0.78, 18.55, -0.58, 0.026, 0.16),
    ]
    for x, y, z, r, length in specs:
        # Build along +X then rotate toward outward
        tip = bm.verts.new((0, 0, 0))
        ring0, ring1 = [], []
        for i in range(8):
            ang = math.tau * i / 8
            ring0.append(bm.verts.new((0.0, math.cos(ang) * r, math.sin(ang) * r)))
            ring1.append(bm.verts.new((length, math.cos(ang) * r * 0.7, math.sin(ang) * r * 0.7)))
        for i in range(8):
            j = (i + 1) % 8
            bm.faces.new((tip, ring0[j], ring0[i]))
            bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        # Place: tip at fuselage, shaft pointing mostly +X (or -X)
        side = 1 if x > 0 else -1
        # Approximate surface point + outward offset already in x
        # Translate all new verts for this probe
        # (simpler: transform the last 1+8+8 verts)
        n_new = 1 + 8 + 8
        verts = list(bm.verts)[-n_new:]
        # Rotate so local +X points outward (±X) with slight down/aft
        rot = Matrix.Rotation(math.radians(8), 4, "Z") @ Matrix.Rotation(
            math.radians(-6), 4, "Y"
        )
        if side < 0:
            rot = Matrix.Rotation(math.pi, 4, "Z") @ rot
        bmesh.ops.transform(bm, verts=verts, matrix=rot)
        bmesh.ops.transform(
            bm, verts=verts, matrix=Matrix.Translation((x, y, z))
        )
    return finish(bm)
'''

new_pitot = '''def pitot_probes():
    """Pitot/AOA probes + flush static ports on nose cheeks."""
    bm = bmesh.new()
    # Place on skin via canopy sampler; fuller tip → cheek stations
    specs = [
        (18.05, 78.0, 0.030, 0.18),  # y, cheek_a_deg, radius, length
        (18.45, 82.0, 0.024, 0.15),
    ]
    for y, a_deg, r, length in specs:
        for side in (1, -1):
            a = math.radians(a_deg) * side
            x, yy, z = _canopy_point(a, y, 0.01)
            tip = bm.verts.new((0, 0, 0))
            ring0, ring1 = [], []
            for i in range(8):
                ang = math.tau * i / 8
                ring0.append(bm.verts.new((0.0, math.cos(ang) * r, math.sin(ang) * r)))
                ring1.append(
                    bm.verts.new((length, math.cos(ang) * r * 0.7, math.sin(ang) * r * 0.7))
                )
            for i in range(8):
                j = (i + 1) % 8
                bm.faces.new((tip, ring0[j], ring0[i]))
                bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
            n_new = 1 + 8 + 8
            verts = list(bm.verts)[-n_new:]
            rot = Matrix.Rotation(math.radians(8), 4, "Z") @ Matrix.Rotation(
                math.radians(-6), 4, "Y"
            )
            if side < 0:
                rot = Matrix.Rotation(math.pi, 4, "Z") @ rot
            bmesh.ops.transform(bm, verts=verts, matrix=rot)
            bmesh.ops.transform(bm, verts=verts, matrix=Matrix.Translation((x, yy, z)))

    # Static ports: small flush discs on cheeks (use canopy sampler)
    for y, a_deg, r_disk in (
        (17.85, 70.0, 0.028),
        (17.55, 75.0, 0.024),
        (17.25, 68.0, 0.022),
    ):
        for sign in (1.0, -1.0):
            a = math.radians(a_deg) * sign
            cx, cy, cz = _canopy_point(a, y, 0.006)
            before = set(bm.verts)
            segs = 10
            center = bm.verts.new((0, 0, 0))
            ring = []
            for i in range(segs):
                ang = math.tau * i / segs
                ring.append(
                    bm.verts.new((0.003, math.cos(ang) * r_disk, math.sin(ang) * r_disk))
                )
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((center, ring[i], ring[j]))
            created = [v for v in bm.verts if v not in before]
            # local +X → roughly outward (±X on cheeks)
            rot = Matrix.Rotation(a, 4, "Y")
            bmesh.ops.transform(bm, verts=created, matrix=rot)
            bmesh.ops.transform(
                bm, verts=created, matrix=Matrix.Translation((cx, cy, cz))
            )
    return finish(bm)
'''

if old_pitot not in text:
    raise SystemExit("PITOT_NOT_FOUND")
text = text.replace(old_pitot, new_pitot, 1)

# --- 6. Doors: deeper recess, rounder corners, seal lip ---
old_doors = '''def _door_specs():
    return [
        (12.95, 0.05, 0.95, 1.95, 0.12),   # forward passenger
        (1.35, 0.20, 0.72, 1.40, 0.10),    # overwing exit
        (-11.6, 0.05, 0.95, 1.95, 0.12),   # aft passenger
        (14.55, 0.15, 0.70, 1.55, 0.10),   # crew/service behind cockpit
    ]


def cabin_doors():
    """Slightly recessed door panels so seams read against white skin."""
    bm = bmesh.new()
    for y, z, w, h, corner in _door_specs():
        for side in (1, -1):
            m = Matrix.Translation((side * 2.040, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_slab(bm, w, h, 0.035, corner, segs=6, matrix=m)
    return finish(bm)


def cabin_door_frames():
    """Hollow dark rounded door outlines (rim only — not solid dark panels)."""
    bm = bmesh.new()
    for y, z, w, h, corner in _door_specs():
        for side in (1, -1):
            m = Matrix.Translation((side * 2.080, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_frame(
                bm, w + 0.06, h + 0.06, 0.012, corner + 0.02,
                border=0.045, segs=6, matrix=m,
            )
    return finish(bm)
'''

new_doors = '''def _door_specs():
    # y, z, w, h, corner — larger corners for L1 / exits
    return [
        (12.95, 0.05, 0.95, 1.95, 0.16),   # L1 forward passenger
        (1.35, 0.20, 0.72, 1.40, 0.14),    # overwing emergency exit
        (-11.6, 0.05, 0.95, 1.95, 0.16),   # aft passenger
        (14.55, 0.15, 0.70, 1.55, 0.14),   # crew/service behind cockpit
    ]


def cabin_doors():
    """Recessed door panels with depth so seams read against white skin."""
    bm = bmesh.new()
    for y, z, w, h, corner in _door_specs():
        for side in (1, -1):
            m = Matrix.Translation((side * 2.018, y, z))  # deeper recess
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_slab(bm, w, h, 0.055, corner, segs=7, matrix=m)
    return finish(bm)


def cabin_door_frames():
    """Seal/lip outline: hollow dark rim with depth + rounded corners."""
    bm = bmesh.new()
    for y, z, w, h, corner in _door_specs():
        for side in (1, -1):
            m = Matrix.Translation((side * 2.075, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_frame(
                bm, w + 0.08, h + 0.08, 0.022, corner + 0.03,
                border=0.050, segs=7, matrix=m,
            )
    return finish(bm)
'''

if old_doors not in text:
    raise SystemExit("DOORS_NOT_FOUND")
text = text.replace(old_doors, new_doors, 1)

# --- 7. Panel lines: distinct radome parting ring ---
old_panel = '''    rings = [
        (15.02, 0.014, 0.011),  # radome / forward-fuselage break
        (8.6, 0.018, 0.010),
        (3.8, 0.016, 0.010),
        (-4.2, 0.016, 0.010),
        (-9.4, 0.016, 0.010),
    ]
'''

new_panel = '''    rings = [
        (18.55, 0.022, 0.018),  # DISTINCT radome parting line (ahead of WS)
        (15.02, 0.014, 0.011),  # forward cabin / cockpit break
        (8.6, 0.018, 0.010),
        (3.8, 0.016, 0.010),
        (-4.2, 0.016, 0.010),
        (-9.4, 0.016, 0.010),
    ]
'''

if old_panel not in text:
    raise SystemExit("PANEL_NOT_FOUND")
text = text.replace(old_panel, new_panel, 1)

# Fix panel ring generation to use elliptical section for nose rings
old_ring_gen = '''    for y, half_w, r_extra in rings:
        r = _radius_at_y(y) + r_extra
        ring_f, ring_a = [], []
        for i in range(segs):
            a = math.tau * i / segs
            xf, zf = math.cos(a) * r, math.sin(a) * r
            ring_f.append(bm.verts.new((xf, y + half_w, zf)))
            ring_a.append(bm.verts.new((xf, y - half_w, zf)))
'''

new_ring_gen = '''    for y, half_w, r_extra in rings:
        rx, rz = _section_at_y(y)
        rx += r_extra
        rz += r_extra
        ring_f, ring_a = [], []
        for i in range(segs):
            a = math.tau * i / segs
            xf, zf = math.cos(a) * rx, math.sin(a) * rz
            ring_f.append(bm.verts.new((xf, y + half_w, zf)))
            ring_a.append(bm.verts.new((xf, y - half_w, zf)))
'''

if old_ring_gen not in text:
    raise SystemExit("RING_GEN_NOT_FOUND")
text = text.replace(old_ring_gen, new_ring_gen, 1)

# --- 8. note string ---
old_note = 'print("C919_NOTE nose3=ellipse-ogive+4pane-curved-ws")'
new_note = 'print("C919_NOTE nose4=blunt-radome+parting+soft-ws+door-window")'
if old_note not in text:
    raise SystemExit("NOTE_NOT_FOUND")
text = text.replace(old_note, new_note, 1)

# Soften pane angular gaps slightly in _cockpit_pane_defs for denser look
# (optional — keep existing pane defs; density bumped in windshield)

if text == orig:
    raise SystemExit("NO_CHANGES")

p.write_text(text, encoding="utf-8")
print("PATCHED", p)
print("BYTES", len(text.encode("utf-8")))
print("TIP_STATION", "(19.95, 0.42, 0.38)  # was (20.08, 0.22, 0.19)")

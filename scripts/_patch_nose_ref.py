# -*- coding: utf-8 -*-
"""Patch build_c919.py for REF-matched nose silhouette (parametric only)."""
from pathlib import Path
import re

PATH = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = PATH.read_text(encoding="utf-8")

# --- 1. Replace nose_with_cap to support optional z_off (4th tuple elem) ---
old_nose_cap = '''def nose_with_cap(profile, segments=None):
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
    # Dome-like tip: keep scale high, very short throw (blunt commercial radome).
    tip_spec = [
        (0.022, 0.97),
        (0.042, 0.92),
        (0.058, 0.84),
        (0.070, 0.72),
        (0.078, 0.55),
    ]
    prev = rings[0]
    for dy, s in tip_spec:
        ring = ring_at(y0 + dy, rx0 * s, rz0 * s)
        for i in range(segs):
            j = (i + and 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    # Pole almost flush with last ring — rounded dome end.
    pole = bm.verts.new((0.0, y0 + 0.078 + min(rx0, rz0) * 0.55 * 0.55, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)
'''

# Fix typo in my draft - use exact file content. Read exact nose_with_cap from file.
print("Finding nose_with_cap...")
m = re.search(r"def nose_with_cap\(profile, segments=None\):.*?return finish\(bm\)\n", text, re.S)
assert m, "nose_with_cap not found"
print("found nose_with_cap len", len(m.group(0)))

new_nose_cap = '''def nose_with_cap(profile, segments=None):
    """Elliptical-station nose + blunt parabolic radome tip (commercial jet).

    Each station is (y, rx, rz) or (y, rx, rz, z_off). z_off drops the
    section center for mild C919 radome droop (REF ~0.5 m tip vs cabin).
    Tip cap is short commercial dome — not a missile cone.
    """
    segs = segments or SEGMENTS
    bm = bmesh.new()

    def _unpack(st):
        y, rx, rz = st[0], st[1], st[2]
        z0 = st[3] if len(st) > 3 else 0.0
        return y, rx, rz, z0

    def ring_at(y, rx, rz, z0=0.0):
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rx, y, math.sin(ang) * rz + z0))
            )
        return ring

    rings = [ring_at(*_unpack(st)) for st in profile]
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    # Blunt parabolic tip: short axial throw, follows first-station droop.
    y0, rx0, rz0, z00 = _unpack(profile[0])
    tip_spec = [
        (0.018, 0.96),
        (0.034, 0.90),
        (0.048, 0.80),
        (0.058, 0.66),
        (0.066, 0.48),
    ]
    prev = rings[0]
    for dy, s in tip_spec:
        ring = ring_at(y0 + dy, rx0 * s, rz0 * s, z00)
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    # Pole almost flush with last ring — rounded dome end.
    pole = bm.verts.new(
        (0.0, y0 + 0.066 + min(rx0, rz0) * 0.48 * 0.50, z00)
    )
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)
'''

text = text[: m.start()] + new_nose_cap + text[m.end() :]

# --- 2. Replace NOSE_PROFILE ---
m2 = re.search(
    r"NOSE_PROFILE = \[\n.*?\n\]\n\n# fuse1:",
    text,
    re.S,
)
assert m2, "NOSE_PROFILE not found"
print("found NOSE_PROFILE")

new_profile = '''NOSE_PROFILE = [
    # nose-ref: REF_C919 meters taper + mild droop (4th = z_off). Tip kept
    # commercial-blunt (not REF 0.28 missile, not old 0.55 fat ball).
    # Join at y=14.85 still (2.06, 2.06, 0).
    (19.88, 0.40, 0.36, -0.42),
    (19.72, 0.54, 0.50, -0.40),
    (19.55, 0.68, 0.60, -0.37),
    (19.35, 0.82, 0.74, -0.34),
    (19.12, 0.96, 0.88, -0.30),
    (18.88, 1.10, 1.04, -0.27),
    (18.60, 1.24, 1.18, -0.23),
    (18.35, 1.34, 1.30, -0.20),
    (18.10, 1.44, 1.40, -0.17),
    (17.85, 1.52, 1.48, -0.14),  # windshield forward belt
    (17.60, 1.58, 1.55, -0.12),
    (17.35, 1.64, 1.62, -0.10),
    (17.05, 1.70, 1.70, -0.08),
    (16.75, 1.76, 1.78, -0.06),
    (16.45, 1.82, 1.84, -0.05),
    (16.15, 1.87, 1.90, -0.04),  # brow / aft glass
    (15.85, 1.92, 1.94, -0.03),
    (15.55, 1.96, 1.98, -0.02),
    (15.25, 2.00, 2.01, -0.01),
    (15.00, 2.03, 2.04, -0.005),
    (14.85, 2.06, 2.06, 0.0),
]

# fuse1:'''

text = text[: m2.start()] + new_profile + text[m2.end() :]

# --- 3. Update _section_at_y to return z_off as well via helper ---
old_section = '''def _section_at_y(y):
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

# Find exact
m3 = re.search(
    r"def _section_at_y\(y\):.*?def _radius_at_y\(y\):.*?return 0\.5 \* \(rx \+ rz\)\n",
    text,
    re.S,
)
assert m3, "_section_at_y block not found"
print("found _section_at_y")

new_section = '''def _section_at_y(y):
    """(rx, rz) at station y. Nose stations are elliptical; fuselage is circular."""
    rx, rz, _z0 = _section_full_at_y(y)
    return (rx, rz)


def _section_full_at_y(y):
    """(rx, rz, z_off) — z_off is nose droop (0 on fuselage)."""
    stations = RADIUS_STATIONS

    def unpack(s):
        rx = s[1]
        rz = s[2] if len(s) > 2 else s[1]
        z0 = s[3] if len(s) > 3 else 0.0
        return rx, rz, z0

    if y >= stations[0][0]:
        return unpack(stations[0])
    if y <= stations[-1][0]:
        return unpack(stations[-1])
    for s0, s1 in zip(stations, stations[1:]):
        y0, y1 = s0[0], s1[0]
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1 + 1e-9)
            rx0, rz0, z00 = unpack(s0)
            rx1, rz1, z01 = unpack(s1)
            return (
                rx0 + (rx1 - rx0) * t,
                rz0 + (rz1 - rz0) * t,
                z00 + (z01 - z00) * t,
            )
    return (2.08, 2.08, 0.0)


def _radius_at_y(y):
    """Mean radius (legacy callers: panel rings, antennas, gear doors)."""
    rx, rz = _section_at_y(y)
    return 0.5 * (rx + rz)
'''

text = text[: m3.start()] + new_section + text[m3.end() :]

# --- 4. Update _canopy_point to honor droop ---
m4 = re.search(
    r"def _canopy_point\(a, y, r_off\):.*?return \(sx \* rx \+ nx \* r_off, y, sz \* rz \+ nz \* r_off\)\n",
    text,
    re.S,
)
assert m4, "_canopy_point not found"
print("found _canopy_point")

new_canopy = '''def _canopy_point(a, y, r_off):
    """Point on the elliptical nose section. a=0 is crown (+Z).

    Offset is along the section normal so glass/frames hug the skin
    instead of inflating into a larger circle. Honors nose droop z_off.
    """
    rx, rz, z0 = _section_full_at_y(y)
    # Unit ellipse param (a measured from +Z): x = rx*sin(a), z = rz*cos(a)
    sx, sz = math.sin(a), math.cos(a)
    # Outward normal of ellipse x^2/rx^2 + z^2/rz^2 = 1
    nx, nz = sx / max(rx, 1e-6), sz / max(rz, 1e-6)
    nlen = math.hypot(nx, nz) or 1.0
    nx, nz = nx / nlen, nz / nlen
    return (sx * rx + nx * r_off, y, sz * rz + nz * r_off + z0)
'''

text = text[: m4.start()] + new_canopy + text[m4.end() :]

# --- 5. Update windshield pane Y to match REF belt (forward ~17.85, aft brow ~15.9) ---
m5 = re.search(
    r"def _cockpit_pane_defs\(expand=0\.0\):.*?return \[\n.*?\]\n\n\n\ndef _add_canopy_pane",
    text,
    re.S,
)
assert m5, "_cockpit_pane_defs not found"
print("found pane defs, len", len(m5.group(0)))

new_panes = '''def _cockpit_pane_defs(expand=0.0):
    """nose-ref: 4 panes on REF windshield belt (narrow Z, front+side).

    Layout: WS_L/WS_R forward, SW_L/SW_R aft cheeks. Soft Y from REF loops /
    dark-belt blend: forward ~17.85, brow ~15.9. Actual openings still via
    knife_project (ws4); these shells are flush Transmission placeholders.
    Angle 0 = crown (+Z). expand ignored.
    """
    _ = expand

    def _sm(t):
        t = min(1.0, max(0.0, t))
        return t * t * (3.0 - 2.0 * t)

    def fwd_y_fwd(a):
        # center slightly ahead of corners (smooth top silhouette)
        t = abs(a) / math.radians(42)
        return _lerp(17.85, 17.68, _sm(t))

    def fwd_y_aft(a):
        t = abs(a) / math.radians(42)
        return _lerp(16.95, 16.72, _sm(t))

    def side_y_fwd(a):
        t = (abs(a) - math.radians(55)) / (math.radians(100) - math.radians(55))
        return _lerp(16.90, 16.45, _sm(t))

    def side_y_aft(a):
        t = (abs(a) - math.radians(55)) / (math.radians(100) - math.radians(55))
        return _lerp(16.15, 15.70, _sm(t))

    gap = math.radians(1.2)
    return [
        {
            "name": "SW_L",
            "a0": -math.radians(100),
            "a1": -math.radians(52),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 16,
            "segs_y": 10,
        },
        {
            "name": "WS_L",
            "a0": -math.radians(46),
            "a1": -gap,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 14,
            "segs_y": 10,
        },
        {
            "name": "WS_R",
            "a0": gap,
            "a1": math.radians(46),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 14,
            "segs_y": 10,
        },
        {
            "name": "SW_R",
            "a0": math.radians(52),
            "a1": math.radians(100),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 16,
            "segs_y": 10,
        },
    ]



def _add_canopy_pane'''

text = text[: m5.start()] + new_panes + text[m5.end() :]

# --- 6. Update cockpit_frames sill/brow to match new pane Y ---
# Replace sill_y / brow_y functions inside cockpit_frames
old_sill = '''    def sill_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(17.62, 17.50, t * t * (3 - 2 * t))
        t = (aa - math.radians(49)) / (math.radians(105) - math.radians(49) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(17.48, 16.92, t * t * (3 - 2 * t))

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(16.18, 16.32, t * t * (3 - 2 * t))
        t = (aa - math.radians(49)) / (math.radians(105) - math.radians(49) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(15.58, 16.05, t * t * (3 - 2 * t))
'''

new_sill = '''    def sill_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(17.88, 17.70, t * t * (3 - 2 * t))
        t = (aa - math.radians(50)) / (math.radians(100) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.95, 16.50, t * t * (3 - 2 * t))

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(16.92, 16.70, t * t * (3 - 2 * t))
        t = (aa - math.radians(50)) / (math.radians(100) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.10, 15.75, t * t * (3 - 2 * t))
'''

assert old_sill in text, "sill_y block not found"
text = text.replace(old_sill, new_sill, 1)

# Update pillar Y samples roughly
text = text.replace(
    """    _add_shell_sector(
        bm,
        [17.58, 17.20, 16.80, 16.45, 16.18],
        -math.radians(0.55),
        math.radians(0.55),
        r_off,
        segs_a=2,
    )""",
    """    _add_shell_sector(
        bm,
        [17.90, 17.45, 17.00, 16.55, 16.20],
        -math.radians(0.55),
        math.radians(0.55),
        r_off,
        segs_a=2,
    )""",
    1,
)

text = text.replace(
    """        _add_shell_sector(
            bm,
            [17.48, 17.05, 16.60, 16.20],
            lo,
            hi,
            r_off,
            segs_a=2,
        )""",
    """        _add_shell_sector(
            bm,
            [17.75, 17.20, 16.70, 16.25],
            lo,
            hi,
            r_off,
            segs_a=2,
        )""",
    1,
)

text = text.replace(
    """        _add_shell_sector(
            bm,
            [16.90, 16.40, 15.95, 15.60],
            lo,
            hi,
            r_off,
            segs_a=2,
        )""",
    """        _add_shell_sector(
            bm,
            [16.85, 16.35, 15.95, 15.65],
            lo,
            hi,
            r_off,
            segs_a=2,
        )""",
    1,
)

# Update seal spans side_out to 100 to match panes
text = text.replace(
    """    spans = [
        (-math.radians(105), -math.radians(49)),
        (-math.radians(47.5), -math.radians(1.2)),
        (math.radians(1.2), math.radians(47.5)),
        (math.radians(49), math.radians(105)),
    ]""",
    """    spans = [
        (-math.radians(100), -math.radians(50)),
        (-math.radians(47.5), -math.radians(1.2)),
        (math.radians(1.2), math.radians(47.5)),
        (math.radians(50), math.radians(100)),
    ]""",
    1,
)

# Update cabin shell ys slightly forward
text = text.replace(
    "    ys = [17.70, 17.20, 16.70, 16.20, 15.70, 15.20]",
    "    ys = [17.95, 17.40, 16.85, 16.30, 15.80, 15.30]",
    1,
)

PATH.write_text(text, encoding="utf-8")
print("PATCHED OK", PATH, "bytes", PATH.stat().st_size)

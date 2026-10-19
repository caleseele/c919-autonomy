# Wing1b replacement: pose_wing through wing_le_strip

def pose_wing(bm, side):
    bmesh.ops.rotate(
        bm,
        verts=list(bm.verts),
        cent=(0, 0, 0),
        matrix=Matrix.Rotation(side * math.radians(5), 4, "Y"),
    )
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0, 0.2, -0.35))


def _wing_airfoil_yz(yle, yte, thick, n_half=12):
    """Closed supercritical-ish airfoil as (y, z) points.

    Order: LE upper → TE upper → TE lower → near-LE lower.
    Fuller rounded nose, flatter upper aft, mild rear loading.
    """
    chord = max(yle - yte, 0.08)
    pts = []

    def thick_at(t):
        peak = 0.30
        if t <= 1e-6:
            return 0.0
        if t < 0.05:
            # Rounded LE bulb
            return thick * math.sin(0.5 * math.pi * (t / 0.05)) * 0.62
        if t <= peak:
            u = (t - 0.05) / (peak - 0.05)
            return thick * (0.62 + 0.38 * math.sin(0.5 * math.pi * u))
        u = (t - peak) / (1.0 - peak)
        # Flatter upper aft (supercritical), thin TE
        return thick * ((1.0 - u) ** 1.15) * (0.92 + 0.08 * (1.0 - u))

    def camber_at(t):
        return 0.020 * chord * math.sin(math.pi * (t ** 0.88))

    for i in range(n_half):
        t = i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        z_scale = 0.58 if t < 0.42 else 0.46
        y = yle - t * chord
        z = cam + yt * z_scale
        pts.append((y, z))

    for i in range(1, n_half - 1):
        t = 1.0 - i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        z_scale = 0.50 if t < 0.50 else 0.60
        y = yle - t * chord
        z = cam - yt * z_scale
        pts.append((y, z))
    return pts


def wing(side):
    """Swept supercritical loft: broad root, gradual taper, mild TE kink."""
    # More stations = smoother LE/TE (less triangular)
    stations = [
        (1.30, 3.58, -2.82, 0.68),
        (2.20, 3.32, -3.05, 0.60),
        (3.40, 2.95, -3.25, 0.52),
        (5.00, 2.42, -3.45, 0.44),   # TE kink (deepest)
        (6.60, 1.88, -3.28, 0.38),
        (8.40, 1.35, -3.02, 0.32),
        (10.4, 0.78, -2.62, 0.25),
        (12.4, 0.22, -2.22, 0.19),
        (14.2, -0.28, -1.92, 0.14),
        (15.5, -0.58, -1.74, 0.11),
        (16.05, -0.72, -1.66, 0.090),
    ]
    n_half = 13
    bm = bmesh.new()
    rings = []
    for sx, yle, yte, th in stations:
        ring = []
        for y, z in _wing_airfoil_yz(yle, yte, th, n_half):
            ring.append(bm.verts.new((side * sx, y, z)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass

    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass

    # Subtle upper TE hinge crease
    for ri, (sx, yle, yte, th) in enumerate(stations[:-1]):
        chord = yle - yte
        y_hinge = yte + chord * 0.20
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.035 and v.co.z > 0.01:
                v.co.z -= 0.010

    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def winglet(side):
    """Blended winglet: continuous arc from tip, upward + slightly outboard."""
    bm = bmesh.new()
    # Match wing tip station chord/thickness, then curl up
    tip_x0 = 16.00
    # (dx, y_le, y_te, z_mid, thick) — first row ≈ wing tip airfoil
    path = [
        (0.00, -0.72, -1.66, 0.00, 0.088),
        (0.10, -0.78, -1.62, 0.08, 0.080),
        (0.22, -0.88, -1.58, 0.28, 0.068),
        (0.34, -0.98, -1.55, 0.58, 0.055),
        (0.44, -1.08, -1.54, 0.95, 0.042),
        (0.52, -1.16, -1.55, 1.30, 0.032),
        (0.58, -1.24, -1.58, 1.62, 0.024),
        (0.60, -1.30, -1.62, 1.88, 0.016),
    ]
    n_half = 9
    rings = []
    for dx, yle, yte, z_mid, th in path:
        local = _wing_airfoil_yz(yle, yte, th, n_half)
        ring = []
        for y, z in local:
            ring.append(bm.verts.new((side * (tip_x0 + dx), y, z + z_mid)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass
    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass

    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def _add_canoe_fairing(bm, cx, cy, cz, length, width, height):
    """Long slender flap-track canoe aligned with airflow (Y)."""
    n_len = 11
    n_rad = 10
    rings = []
    for i in range(n_len):
        t = i / (n_len - 1)
        # Sharp pointed ends, elongated mid
        s = math.sin(math.pi * t)
        s = max(s, 0.04) ** 0.70
        ww = width * 0.5 * s
        hh = height * 0.5 * s
        yy = cy - length * 0.58 + length * t
        ring = []
        for k in range(n_rad):
            a = math.tau * k / n_rad
            xz_x = math.cos(a) * ww
            xz_z = math.sin(a) * hh
            # Flatten top to hug wing underside
            if xz_z > 0:
                xz_z *= 0.40
            ring.append(bm.verts.new((cx + xz_x, yy, cz + xz_z)))
        rings.append(ring)

    for a, b in zip(rings, rings[1:]):
        for i in range(n_rad):
            j = (i + 1) % n_rad
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    try:
        aft = bm.verts.new((cx, cy - length * 0.58 - 0.04, cz - 0.01))
        fwd = bm.verts.new((cx, cy - length * 0.58 + length + 0.04, cz - 0.01))
        for i in range(n_rad):
            j = (i + 1) % n_rad
            bm.faces.new((aft, rings[0][j], rings[0][i]))
            bm.faces.new((fwd, rings[-1][i], rings[-1][j]))
    except ValueError:
        pass


def wing_flap_fairings(side):
    """Four slender canoe flap-track fairings under trailing edge per wing."""
    bm = bmesh.new()
    # Longer, slimmer canoes; pressed up under TE (cz closer to 0)
    fairings = [
        (4.10, -3.35, 1.75, 0.20, 0.24),
        (7.00, -3.18, 1.55, 0.17, 0.21),
        (10.00, -2.72, 1.35, 0.15, 0.18),
        (13.00, -2.20, 1.15, 0.12, 0.15),
    ]
    for sx, sy, length, width, height in fairings:
        _add_canoe_fairing(
            bm,
            side * sx,
            sy + 0.15,
            -0.16,
            length,
            width,
            height,
        )
    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def wing_le_strip(side):
    """Subtle rounded leading-edge bead along the sweep."""
    bm = bmesh.new()
    beads = [
        (2.00, 3.35, 1.20),
        (4.20, 2.60, 1.30),
        (6.80, 1.80, 1.25),
        (9.80, 0.90, 1.20),
        (12.8, 0.05, 1.10),
        (14.8, -0.40, 0.85),
    ]
    for sx, sy, length in beads:
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.048, length * 0.45, 0.036))
        bmesh.ops.translate(bm, verts=created, vec=(side * sx, sy, 0.14))
    pose_wing(bm, side)
    return finish(bm)

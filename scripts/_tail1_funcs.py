# Tail1: airfoil-loft vertical fin + horizontal stabs + subtle hinge lines + dark tail cone
# Replaces stab() through rudder(); also provides tail_cone_cap()

def _tail_airfoil_2d(yle, yte, thick, n_half=11):
    """Closed airfoil in chord(Y) / thickness(T) plane. LE fuller, thinner TE."""
    chord = max(yle - yte, 0.06)
    pts = []

    def thick_at(t):
        peak = 0.28
        if t <= 1e-6:
            return 0.0
        if t < 0.06:
            return thick * math.sin(0.5 * math.pi * (t / 0.06)) * 0.70
        if t <= peak:
            u = (t - 0.06) / (peak - 0.06)
            return thick * (0.70 + 0.30 * math.sin(0.5 * math.pi * u))
        u = (t - peak) / (1.0 - peak)
        return thick * ((1.0 - u) ** 1.20) * 0.95

    def camber_at(t):
        return 0.012 * chord * math.sin(math.pi * (t ** 0.9))

    for i in range(n_half):
        t = i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        y = yle - t * chord
        # +T side
        pts.append((y, cam + yt * 0.55))
    for i in range(1, n_half - 1):
        t = 1.0 - i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        y = yle - t * chord
        pts.append((y, cam - yt * 0.55))
    return pts


def stab(side):
    """Conventional low-mounted HT: swept airfoil loft, mild dihedral, elevator crease.

    NOT a T-tail. Root plants into aft fuselage; tip is clean squared-off with
    slightly rounded edges. Soft span/chord check vs C919 class (~12 m span).
    """
    # Local stations before placement: (x_span, y_le, y_te, thick)
    # Root chord ~2.7 m, tip ~0.85 m, half-span ~6.1 m → span ~12.2 m
    stations = [
        (0.88, 1.40, -1.30, 0.36),
        (1.80, 1.12, -1.20, 0.30),
        (2.90, 0.82, -1.10, 0.25),
        (4.00, 0.52, -0.98, 0.20),
        (4.95, 0.28, -0.86, 0.155),
        (5.65, 0.12, -0.74, 0.115),
        (6.10, 0.02, -0.62, 0.085),
    ]
    n_half = 11
    bm = bmesh.new()
    rings = []
    for sx, yle, yte, th in stations:
        ring = []
        for y, t in _tail_airfoil_2d(yle, yte, th, n_half):
            # thickness along Z for horizontal stab
            ring.append(bm.verts.new((side * sx, y, t)))
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

    # Subtle elevator hinge crease (~22% chord from TE), both surfaces
    for ri, (sx, yle, yte, th) in enumerate(stations[:-1]):
        chord = yle - yte
        y_hinge = yte + chord * 0.22
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.04:
                # push slightly toward midplane of airfoil (shallow seam)
                v.co.z *= 0.82

    # Mild dihedral (~6°) about local root, then place on aft fuselage
    bmesh.ops.rotate(
        bm,
        verts=list(bm.verts),
        cent=(0, 0, 0),
        matrix=Matrix.Rotation(side * math.radians(6.0), 4, "Y"),
    )
    # Mid/upper rear fuselage — flush with skin
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0.0, -16.35, 0.90))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def fuselage_radius_at(y):
    """Mean radius from NOSE/FUSELAGE elliptical stations (keeps fin root on skin)."""
    return _radius_at_y(y)


def vertical_tail():
    """Normal-tail vertical stabilizer: airfoil loft root→tip, rounded tip, soft LE.

    Conventional single fin (NOT T-tail). Tip height stays in ~12 m overall class.
    Root bottom hugs tapering crown so aft heel does not hover over the cone.
    """
    # Stations along height: (z, y_le, y_te, thick_x)
    # LE sweep ~35°, tip rounded (short chord + thin), root thick.
    r_fwd = fuselage_radius_at(-14.7)
    r_aft = fuselage_radius_at(-18.55)
    stations = [
        # plant below crown
        (0.42 * r_fwd, -14.55, -17.85, 0.46),
        (0.55 * r_fwd + 0.15, -14.70, -18.05, 0.42),
        (1.8, -15.05, -18.25, 0.36),
        (3.2, -15.45, -18.35, 0.30),
        (4.6, -15.90, -18.40, 0.24),
        (5.9, -16.35, -18.38, 0.19),
        (7.1, -16.80, -18.28, 0.145),
        (8.15, -17.20, -18.12, 0.105),
        # rounded tip: LE/TE converge, soft dome
        (8.55, -17.45, -17.95, 0.070),
        (8.72, -17.58, -17.82, 0.040),
    ]
    n_half = 11
    bm = bmesh.new()
    rings = []
    for z, yle, yte, th in stations:
        ring = []
        for y, t in _tail_airfoil_2d(yle, yte, th, n_half):
            # thickness along X for vertical fin
            ring.append(bm.verts.new((t, y, z)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    try:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    except ValueError:
        pass

    # Subtle rudder hinge crease near TE (shallow, not a deep groove)
    for ri, (z, yle, yte, th) in enumerate(stations[:-2]):
        chord = yle - yte
        y_hinge = yte + chord * 0.18
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.035:
                v.co.x *= 0.78

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def rudder():
    """Red rudder livery strip along fin TE — thin, follows lofted TE, not a rod."""
    bm = bmesh.new()
    # Follows vertical_tail TE with a slim chord strip on +X face
    shape = [
        (-18.20, 1.6),
        (-18.05, 1.6),
        (-17.88, 7.6),
        (-18.05, 7.6),
    ]
    verts = [bm.verts.new((0.095, y, z)) for y, z in shape]
    face = bm.faces.new(verts)
    extruded = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in extruded["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0.045, 0, 0))
    return finish(bm)


def tail_cone_cap():
    """Dark metallic aft cone tip + circular APU exhaust (matches real C919 photo)."""
    bm = bmesh.new()
    # Cover last ~1.0 m of fuselage with slightly oversized dark shell
    stations = [
        (-18.55, 0.66, 0.68),
        (-18.80, 0.48, 0.50),
        (-19.05, 0.30, 0.32),
        (-19.25, 0.16, 0.175),
        (-19.42, 0.07, 0.08),
        (-19.52, 0.028, 0.032),
    ]
    segs = 48
    rings = []
    for y, rx, rz in stations:
        # slight oversize so it sits outside white skin
        rx *= 1.03
        rz *= 1.03
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rx, y, math.sin(ang) * rz))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            try:
                bm.faces.new((a[i], b[i], b[j], a[j]))
            except ValueError:
                pass
    # Open APU exhaust: leave a hole at tip via small aft ring + inner tube
    tip_y = -19.58
    r_ex = 0.055
    outer = []
    inner = []
    for i in range(segs):
        ang = math.tau * i / segs
        outer.append(
            bm.verts.new((math.cos(ang) * r_ex * 1.35, tip_y, math.sin(ang) * r_ex * 1.35))
        )
        inner.append(
            bm.verts.new((math.cos(ang) * r_ex * 0.55, tip_y - 0.08, math.sin(ang) * r_ex * 0.55))
        )
    # connect last shell ring to outer exhaust lip
    last = rings[-1]
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new((last[i], outer[i], outer[j], last[j]))
            bm.faces.new((outer[i], inner[i], inner[j], outer[j]))
        except ValueError:
            pass
    # close inner disk slightly inset (exhaust face)
    pole = bm.verts.new((0.0, tip_y - 0.10, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new((pole, inner[j], inner[i]))
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)

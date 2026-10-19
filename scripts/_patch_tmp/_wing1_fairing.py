def wing_body_fairing(side):
    """Smooth belly / wing-root fairing loft (C919-style bulge)."""
    bm = bmesh.new()
    # Tighter to fuselage, longer fore-aft blend, softer silhouette
    secs = [
        (2.50, side * 1.15, -1.72, 0.42, 0.38),
        (1.70, side * 1.45, -1.58, 0.65, 0.52),
        (0.95, side * 1.80, -1.42, 0.88, 0.64),
        (0.20, side * 2.05, -1.30, 1.00, 0.70),
        (-0.55, side * 2.12, -1.26, 0.95, 0.60),
        (-1.30, side * 1.90, -1.28, 0.72, 0.46),
        (-2.00, side * 1.55, -1.38, 0.48, 0.32),
        (-2.60, side * 1.20, -1.48, 0.28, 0.20),
    ]
    n_rad = 20
    rings = []
    for y, cx, cz, rx, rz in secs:
        ring = []
        for i in range(n_rad):
            a = math.tau * i / n_rad
            ring.append(
                bm.verts.new(
                    (cx + math.cos(a) * rx, y, cz + math.sin(a) * rz)
                )
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(n_rad):
            j = (i + 1) % n_rad
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
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)

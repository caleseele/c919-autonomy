# -*- coding: utf-8 -*-
"""Patch build_c919.py for cockpit3 pass."""
from pathlib import Path

path = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = path.read_text(encoding="utf-8")

# --- replacements keyed by unique start/end markers ---

NEW_FRAMES = '''def cockpit_frames():
    """Soft thin mullions + brow/sill following the four curved panes.

    cockpit3: slightly wider posts + thicker brow/sill so openings read
    as framed apertures; still soft (no thick bars).
    """
    bm = bmesh.new()
    r_off = 0.020  # proud of glass (+0.010)

    # Narrow-but-readable posts (~1.8 deg)
    mullions = [
        (-math.radians(111.0), -math.radians(109.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.0), math.radians(111.0), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (-math.radians(49.9), -math.radians(48.1), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.1), math.radians(49.9), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (-math.radians(1.6), math.radians(1.6), [17.52, 17.12, 16.72, 16.36, 16.12]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=4)
        # slight radial thickness so posts catch light
        _add_raised_strip(bm, ys, a0, a1, r_in=0.008, r_out=r_off, segs_a=3)

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
        a_list = [_lerp(a0, a1, i / 40.0) for i in range(41)]
        for y_fn, half in ((sill_y, 0.016), (brow_y, 0.016)):
            _add_curve_ribbon(bm, a_list, y_fn, half, r_in=0.006, r_out=r_off)

    # Soft cheek blend outside side panes
    for sign in (-1.0, 1.0):
        ys = [16.85, 16.40, 15.95, 15.50]
        _add_shell_sector(
            bm, ys,
            sign * math.radians(100),
            sign * math.radians(114),
            0.008,
            segs_a=5,
        )

    return finish(bm)
'''

NEW_PUNCH = '''def punch_windshield_openings(nose_obj):
    """Delete nose skin under panes so glass sees interior.

    cockpit3: expand punch slightly under mullions/brow/sill so ragged
    face-delete edges hide behind frames; then drop orphan verts and
    recalc normals for cleaner one-sided openings.
    """
    if nose_obj is None or nose_obj.type != "MESH":
        return
    mesh = nose_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    panes = _cockpit_pane_defs()
    # Angular margin ~1.2 deg so hole tucks under posts; Y margin under brow/sill
    a_pad = math.radians(1.2)
    y_pad = 0.07
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        y = c.y
        if y < 15.28 or y > 17.92:
            continue
        a = math.atan2(c.x, c.z)
        for pane in panes:
            a0, a1 = pane["a0"], pane["a1"]
            lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
            if not (lo - a_pad <= a <= hi + a_pad):
                continue
            y_fwd = pane["y_fwd"](a)
            y_aft = pane["y_aft"](a)
            y_lo, y_hi = (y_aft, y_fwd) if y_aft <= y_fwd else (y_fwd, y_aft)
            if y_lo - y_pad <= y <= y_hi + y_pad:
                rx, rz = _section_at_y(y)
                r_skin = math.hypot(c.x / max(rx, 1e-6), c.z / max(rz, 1e-6))
                # Slightly lower threshold so brim under frames also goes
                if r_skin > 0.78:
                    kill.append(f)
                break
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        # Drop verts that no longer touch any face (cleaner hole rim)
        orphans = [v for v in bm.verts if not v.link_faces]
        if orphans:
            bmesh.ops.delete(bm, geom=orphans, context="VERTS")
        # Dissolve very short boundary edges to reduce jagged stair-steps
        bm.edges.ensure_lookup_table()
        short = []
        for e in bm.edges:
            if e.is_boundary and e.calc_length() < 0.045:
                short.append(e)
        if short:
            try:
                bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
            except Exception:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        mesh.update()
    bm.free()
    print("C919_NOTE punched_ws_faces", len(kill))
'''

NEW_WIPERS = '''def windshield_wipers():
    """Two parked dark wiper arms: solid hub + arm + blade (L/R).

    cockpit3: thicker hub/arm/blade, rubber strip, small park mount and
    washer nozzles near center pillar at windshield base.
    """
    bm = bmesh.new()

    def _add_box(bm, size_xyz, center, track_dir, up=Vector((0, 0, 1))):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=size_xyz)
        d = track_dir.normalized() if track_dir.length > 1e-8 else Vector((0, 1, 0))
        # Prefer Y-aligned for long arms, X for blades
        axis = "Y" if size_xyz[1] >= size_xyz[0] else "X"
        quat = d.to_track_quat(axis, "Z")
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4(),
        )
        return created

    for side in (-1.0, 1.0):
        # Park near center pillar, base of forward panes
        a0 = side * math.radians(6.5)
        p_base = Vector(_canopy_point(a0, 17.48, 0.034))
        p_mid = Vector(_canopy_point(a0 + side * math.radians(2.0), 16.95, 0.034))
        p_tip = Vector(_canopy_point(a0 + side * math.radians(4.0), 16.40, 0.034))
        arm_dir = p_tip - p_base
        arm_len = max(arm_dir.length, 1e-4)

        # Mount pad (flat plate on sill)
        mount_c = p_base + Vector((0, 0.01, -0.01))
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.055, 0.040, 0.014))
        bmesh.ops.translate(bm, verts=created, vec=mount_c)

        # Hub (solid sphere)
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=8, radius=0.038)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=p_base)

        # Arm (tapered as two segments: thicker near hub)
        mid1 = p_base.lerp(p_mid, 0.55)
        mid2 = p_mid.lerp(p_tip, 0.45)
        _add_box(bm, (0.028, arm_len * 0.28, 0.020), mid1, p_mid - p_base)
        _add_box(bm, (0.022, arm_len * 0.30, 0.016), mid2, p_tip - p_mid)

        # Blade body (metal channel) across glass near tip
        a_lo = a0 + side * math.radians(-3.0)
        a_hi = a0 + side * math.radians(16.0)
        p_lo = Vector(_canopy_point(a_lo, 16.44, 0.036))
        p_hi = Vector(_canopy_point(a_hi, 16.36, 0.036))
        blade_mid = (p_lo + p_hi) * 0.5
        blade_dir = p_hi - p_lo
        blade_len = max(blade_dir.length, 1e-4)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(blade_len * 0.5, 0.016, 0.012))
        quat_b = blade_dir.normalized().to_track_quat("X", "Z")
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(blade_mid) @ quat_b.to_matrix().to_4x4(),
        )
        # Rubber lip (slightly thinner, proud toward glass)
        rubber_mid = blade_mid + Vector((0, 0, -0.006))
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(blade_len * 0.48, 0.008, 0.006))
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(rubber_mid) @ quat_b.to_matrix().to_4x4(),
        )

        # Washer nozzle (tiny) outboard of hub
        nozzle = Vector(_canopy_point(a0 + side * math.radians(10.0), 17.52, 0.030))
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.012)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=nozzle)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)
'''

NEW_GLARE = '''def cockpit_glare_shield():
    """Dark glare shelf + crude instrument panel under windshield.

    cockpit3: tapered brow, side cheeks, center pedestal hint, and a few
    dark display rectangles (not full PFD fidelity).
    """
    bm = bmesh.new()

    # Main glare shelf (wide, thin, pitched)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.62, 0.42, 0.055))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 17.02, 0.96))
    bmesh.ops.rotate(
        bm,
        verts=created,
        cent=(0.0, 17.02, 0.96),
        matrix=Matrix.Rotation(math.radians(-16.0), 4, "X"),
    )
    # Front lip drop (anti-glare brow)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.55, 0.08, 0.09))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 17.28, 0.90))

    # Soft side cheeks
    for sx in (-1.05, 1.05):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.20, 0.38, 0.14))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.88, 0.74))

    # Instrument panel shelf (aft of lip, lower)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.35, 0.22, 0.10))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.78, 0.72))
    bmesh.ops.rotate(
        bm,
        verts=created,
        cent=(0.0, 16.78, 0.72),
        matrix=Matrix.Rotation(math.radians(-8.0), 4, "X"),
    )

    # Display rectangles (dark glass look) — 4 across
    for i, sx in enumerate((-0.78, -0.28, 0.28, 0.78)):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        w = 0.34 if i in (1, 2) else 0.28
        bmesh.ops.scale(bm, verts=created, vec=(w, 0.04, 0.18))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.88, 0.82))

    # Center pedestal stub between seats
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(0.22, 0.55, 0.12))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.35, 0.28))

    return finish(bm)
'''

NEW_SEATS = '''def cockpit_pilot_seats():
    """Dual airline-style pilot seats (red) with rails / pedestals.

    cockpit3: cushion + reclined back + headrest silhouette; less boxy;
    simple seat rails so they read as chairs not crates.
    """
    bm = bmesh.new()
    for sx in (-0.50, 0.50):
        # Pedestal / base
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.22, 0.28, 0.10))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.38, 0.05))

        # Seat rails (fore-aft)
        for rx in (-0.12, 0.12):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.035, 0.42, 0.025))
            bmesh.ops.translate(bm, verts=created, vec=(sx + rx, 16.40, -0.02))

        # Cushion (slightly trapezoid via two slabs)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.40, 0.40, 0.10))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.45, 0.20))
        # Front cushion lip (thicker lip = less box)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.38, 0.10, 0.08))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.62, 0.22))

        # Backrest (reclined ~12 deg)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.38, 0.10, 0.58))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.20, 0.58))
        bmesh.ops.rotate(
            bm,
            verts=created,
            cent=(sx, 16.20, 0.30),
            matrix=Matrix.Rotation(math.radians(-12.0), 4, "X"),
        )
        # Lumbar bulge
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.34, 0.06, 0.16))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.28, 0.42))

        # Headrest (narrower, above glare line)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.26, 0.09, 0.14))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.12, 1.16))
        # Side wings of headrest
        for hx in (-0.14, 0.14):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.05, 0.07, 0.12))
            bmesh.ops.translate(bm, verts=created, vec=(sx + hx, 16.12, 1.14))

        # Armrests (slightly sculpted length)
        for ax in (-0.26, 0.26):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.06, 0.32, 0.05))
            bmesh.ops.translate(bm, verts=created, vec=(sx + ax, 16.42, 0.38))

    return finish(bm)
'''


def replace_func(src: str, func_name: str, new_body: str) -> str:
    start = src.find(f"def {func_name}(")
    if start < 0:
        raise SystemExit(f"missing {func_name}")
    # find next top-level def after this one
    nxt = src.find("\ndef ", start + 4)
    if nxt < 0:
        raise SystemExit(f"no next def after {func_name}")
    # keep trailing newline before next def
    return src[:start] + new_body.rstrip() + "\n\n\n" + src[nxt + 1 :]


for name, body in (
    ("cockpit_frames", NEW_FRAMES),
    ("punch_windshield_openings", NEW_PUNCH),
    ("windshield_wipers", NEW_WIPERS),
    ("cockpit_glare_shield", NEW_GLARE),
    ("cockpit_pilot_seats", NEW_SEATS),
):
    text = replace_func(text, name, body)
    print("replaced", name)

# Clearer glass for seats visibility
old_glass = '''    # vis1: clearer cockpit glass so seats/wipers read through panes
    cockpit_glass = glass_material("CockpitGlass")
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.82),
            ("Transmission", 0.82),
            ("Alpha", 0.32),
            ("Roughness", 0.04),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val'''

new_glass = '''    # cockpit3: clearer glass so seats/wipers/dash read through panes
    cockpit_glass = glass_material("CockpitGlass")
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.88),
            ("Transmission", 0.88),
            ("Alpha", 0.26),
            ("Roughness", 0.035),
            ("IOR", 1.45),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.10, 0.14, 0.20, 1.0)'''

if old_glass not in text:
    raise SystemExit("glass block not found")
text = text.replace(old_glass, new_glass)
print("replaced glass block")

# Display material for instrument rectangles — keep same mesh material for now
# (dark glare mat); optionally split later.

# Smooth seats slightly for less faceted look — change use_smooth on seats
old_smooth = '''    for ob in (gs_obj, seat_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = False'''
new_smooth = '''    # Soft-shade seats/glare so cushion silhouette reads less like crates
    for ob in (gs_obj, seat_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = True'''
if old_smooth not in text:
    raise SystemExit("smooth block not found")
text = text.replace(old_smooth, new_smooth)
print("replaced smooth block")

old_note = 'print("C919_NOTE vis1=overwing-raised+wipers+cockpit-seats+glare+clearer-WS")'
new_note = 'print("C919_NOTE cockpit3=thick-wipers+airline-seats+glare-dash+clean-WS-punch")'
if old_note not in text:
    raise SystemExit("note not found")
text = text.replace(old_note, new_note)
print("replaced note")

path.write_text(text, encoding="utf-8")
print("OK wrote", path, "bytes", path.stat().st_size)

# -*- coding: utf-8 -*-
"""vis1 patch: overwing door raise + wipers + cockpit interior."""
from pathlib import Path

path = Path("scripts/build_c919.py")
text = path.read_text(encoding="utf-8")

old_door = '''def _door_specs():
    # y, z, w, h, corner, kind
    return [
        (13.05, 0.05, 0.84, 1.78, 0.12, "passenger"),
        (14.42, 0.12, 0.58, 1.38, 0.10, "service"),
        (1.40, 0.22, 0.62, 1.28, 0.10, "overwing"),
        (-11.45, 0.05, 0.84, 1.78, 0.12, "passenger"),
    ]'''

new_door = '''def _door_specs():
    # y, z, w, h, corner, kind
    # overwing: sill ABOVE wing upper (~z0.15 after pose) + fairing —
    # raised to window-belt so exit is clearly visible in 3/4 views.
    return [
        (13.05, 0.05, 0.84, 1.78, 0.12, "passenger"),
        (14.42, 0.12, 0.58, 1.38, 0.10, "service"),
        (1.65, 0.78, 0.58, 0.95, 0.10, "overwing"),
        (-11.45, 0.05, 0.84, 1.78, 0.12, "passenger"),
    ]'''

if old_door not in text:
    raise SystemExit("door_specs block not found")
text = text.replace(old_door, new_door, 1)

# window door gaps
old_gaps = '''    door_gaps = [
        (12.40, 13.75),   # L1 passenger (clear of pane half-width)
        (13.95, 14.90),   # forward service
        (0.85, 1.95),     # overwing exit
        (-12.10, -10.85), # aft passenger
    ]'''
new_gaps = '''    door_gaps = [
        (12.40, 13.75),   # L1 passenger (clear of pane half-width)
        (13.95, 14.90),   # forward service
        (1.10, 2.20),     # overwing exit (raised / slightly forward)
        (-12.10, -10.85), # aft passenger
    ]'''
if old_gaps not in text:
    raise SystemExit("window door_gaps not found")
text = text.replace(old_gaps, new_gaps, 1)

old_stripe = '''    door_y_gaps = [
        (12.55, 13.55),   # L1
        (14.05, 14.80),   # forward service
        (1.00, 1.80),     # overwing
        (-11.95, -10.95), # aft
    ]'''
new_stripe = '''    door_y_gaps = [
        (12.55, 13.55),   # L1
        (14.05, 14.80),   # forward service
        (1.20, 2.10),     # overwing
        (-11.95, -10.95), # aft
    ]'''
if old_stripe not in text:
    raise SystemExit("stripe door_y_gaps not found")
text = text.replace(old_stripe, new_stripe, 1)

# Insert wipers + cockpit interior before _orient_faces_outward
marker = "\ndef _orient_faces_outward(bm):\n"
insert = r'''
def windshield_wipers():
    """Two parked dark wiper arms + blades at windshield base (L/R)."""
    bm = bmesh.new()
    for side in (-1.0, 1.0):
        a0 = side * math.radians(7.5)
        p_base = Vector(_canopy_point(a0, 17.50, 0.028))
        p_tip = Vector(_canopy_point(a0 + side * math.radians(3.0), 16.38, 0.028))
        mid = (p_base + p_tip) * 0.5
        direction = p_tip - p_base
        length = max(direction.length, 1e-4)

        # Hub
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.024)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=p_base)

        # Arm (thin box aligned to glass)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.014, length * 0.5, 0.011))
        quat = direction.normalized().to_track_quat("Y", "Z")
        bmesh.ops.transform(
            bm, verts=created, matrix=Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
        )

        # Blade (wide thin strip across glass near tip)
        a_lo = a0 + side * math.radians(-2.0)
        a_hi = a0 + side * math.radians(14.0)
        p_lo = Vector(_canopy_point(a_lo, 16.42, 0.030))
        p_hi = Vector(_canopy_point(a_hi, 16.36, 0.030))
        blade_mid = (p_lo + p_hi) * 0.5
        blade_dir = p_hi - p_lo
        blade_len = max(blade_dir.length, 1e-4)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(blade_len * 0.5, 0.009, 0.007))
        quat_b = blade_dir.normalized().to_track_quat("X", "Z")
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(blade_mid) @ quat_b.to_matrix().to_4x4(),
        )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def cockpit_glare_shield():
    """Dark instrument brow / glare shelf under windshield."""
    bm = bmesh.new()
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.55, 0.48, 0.07))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.92, 0.95))
    bmesh.ops.rotate(
        bm,
        verts=created,
        cent=(0.0, 16.92, 0.95),
        matrix=Matrix.Rotation(math.radians(-14.0), 4, "X"),
    )
    # Soft side cheeks of glare shield
    for sx in (-0.95, 0.95):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.22, 0.35, 0.12))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.85, 0.78))
    return finish(bm)


def cockpit_pilot_seats():
    """Dual blocky pilot seats (red) — readable through clear windshield."""
    bm = bmesh.new()
    for sx in (-0.50, 0.50):
        # Cushion
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.36, 0.40, 0.11))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.58, 0.18))
        # Backrest
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.34, 0.11, 0.52))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.35, 0.50))
        # Headrest
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.26, 0.09, 0.13))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.33, 0.88))
        # Armrests
        for ax in (-0.22, 0.22):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.06, 0.28, 0.05))
            bmesh.ops.translate(bm, verts=created, vec=(sx + ax, 16.55, 0.32))
    return finish(bm)


'''

if marker not in text:
    raise SystemExit("_orient_faces_outward marker not found")
if "def windshield_wipers():" not in text:
    text = text.replace(marker, insert + marker, 1)

# Wire into build(): after pitot link
old_pitot = '''    pitot_mat = material("Pitot", (0.12, 0.13, 0.15), 0.35, 0.55)
    link("PitotProbes", pitot_probes(), "avionics", pitot_mat, "navy")

    # --- Fine detail pass (panel lines / fairings / gear doors / antennas) ---'''

new_pitot = '''    pitot_mat = material("Pitot", (0.12, 0.13, 0.15), 0.35, 0.55)
    link("PitotProbes", pitot_probes(), "avionics", pitot_mat, "navy")

    # vis1: clearer cockpit glass so seats/wipers read through panes
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
                bsdf.inputs[key].default_value = val
    # Re-assign windshield to clearer glass (object already linked above)
    ws = bpy.data.objects.get("Windshield")
    if ws is not None and ws.data.materials:
        ws.data.materials[0] = cockpit_glass

    wiper_mat = material("Wiper", (0.05, 0.05, 0.06), 0.45, 0.15)
    wp_obj = link("WindshieldWipers", windshield_wipers(), "avionics", wiper_mat, "navy")
    for poly in wp_obj.data.polygons:
        poly.use_smooth = True

    glare_mat = material("GlareShield", (0.06, 0.07, 0.08), 0.55, 0.05)
    seat_mat = material("PilotSeat", (0.72, 0.10, 0.10), 0.55, 0.02)
    gs_obj = link("GlareShield", cockpit_glare_shield(), "avionics", glare_mat, "navy")
    seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "stripe")
    for ob in (gs_obj, seat_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = False

    # --- Fine detail pass (panel lines / fairings / gear doors / antennas) ---'''

if old_pitot not in text:
    raise SystemExit("pitot block not found")
text = text.replace(old_pitot, new_pitot, 1)

# skip subdiv for new thin/interior meshes
old_skip = '''        "WingBodyFairing",
        # Thin extruded surfaces: subdiv opens gaps / shards the fin
        "Wing",'''
new_skip = '''        "WingBodyFairing",
        "WindshieldWipers",
        "GlareShield",
        "PilotSeats",
        # Thin extruded surfaces: subdiv opens gaps / shards the fin
        "Wing",'''
if old_skip not in text:
    raise SystemExit("skip_prefix block not found")
text = text.replace(old_skip, new_skip, 1)

old_note = 'print("C919_NOTE door1=skin-projected-doors+seal-ribbon+no-navy-frames+stripe-gaps")'
new_note = 'print("C919_NOTE vis1=overwing-raised+wipers+cockpit-seats+glare+clearer-WS")'
if old_note not in text:
    raise SystemExit("note print not found")
text = text.replace(old_note, new_note, 1)

path.write_text(text, encoding="utf-8")
print("PATCH_OK", path, "bytes", path.stat().st_size)

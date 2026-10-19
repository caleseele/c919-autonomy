# -*- coding: utf-8 -*-
"""WS1 patch: flush thin windshield frames, thin vertical wipers, no cavity punch."""
from pathlib import Path

SRC = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = SRC.read_text(encoding="utf-8")

# --- Replace cockpit_windshield through windshield_wipers (inclusive) ---
start = text.index("def cockpit_windshield():")
end = text.index("def cockpit_glare_shield():")

NEW = r'''def cockpit_windshield():
    """Four double-curved C919 panes, slightly recessed under thin frames.

    ws1: modest recess (r_off~0.004) so glass sits behind flush metallic
    ribbons; dense sampling for continuous double curvature.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.004)
    return finish(bm)


def cockpit_frames():
    """Flush thin metallic frame ribbons + restrained dark seal lip.

    ws1 (real C919 refs): NO tubular pipe stacks, NO parallel thick arcs.
    Narrow center post (~1.2 deg), thin corner posts, hairline brow/sill.
    Single-layer shell only (no shell+raised_strip double stack).
    """
    bm = bmesh.new()
    # Barely proud of glass (glass at +0.004)
    r_metal = 0.011
    r_seal = 0.007

    # Narrow posts: angular half-widths ~0.55–0.70 deg (was ~1.6–1.8)
    # Center post especially thin so it is a divider, not a beam.
    mullions = [
        # aft cheek terminations (very thin)
        (-math.radians(110.55), -math.radians(109.45), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.45), math.radians(110.55), [16.88, 16.48, 16.10, 15.72, 15.48]),
        # fwd/side junctions
        (-math.radians(49.55), -math.radians(48.45), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.45), math.radians(49.55), [17.62, 17.20, 16.80, 16.45, 16.28]),
        # CENTER post — narrow (~1.2 deg total)
        (-math.radians(0.60), math.radians(0.60), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
    for a0, a1, ys in mullions:
        # outer metallic face
        _add_shell_sector(bm, ys, a0, a1, r_metal, segs_a=2)
        # dark seal lip (slightly inset radially, same angular span tightened)
        mid = 0.5 * (a0 + a1)
        half = 0.55 * abs(a1 - a0)
        _add_shell_sector(bm, ys, mid - half, mid + half, r_seal, segs_a=2)

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

    # Per-pane brow/sill (not one continuous heavy tube across all panes)
    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), -math.radians(2.8)),
        (math.radians(2.8), math.radians(48)),
        (math.radians(50), math.radians(110)),
    ]
    for a0, a1 in spans:
        a_list = [_lerp(a0, a1, i / 36.0) for i in range(37)]
        # hairline half-width (was 0.016 — tubular)
        for y_fn, half in ((sill_y, 0.0055), (brow_y, 0.0055)):
            _add_curve_ribbon(bm, a_list, y_fn, half, r_in=r_seal, r_out=r_metal)

    # Soft cheek fairing: very flat (r_off tiny) — blends side pane into nose
    # without reading as a raised tube or rectangular cut.
    for sign in (-1.0, 1.0):
        ys = [16.80, 16.35, 15.90, 15.50]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(108),
            sign * math.radians(118),
            0.003,
            segs_a=4,
        )

    return finish(bm)


def punch_windshield_openings(nose_obj):
    """ws1: SKIP punch for exterior white-model priority.

    Prior VIS1/cockpit3 face-delete left ragged cavity rims and overlapping
    edges that read as openings/cross-sections. Exterior pass keeps Nose
    skin continuous under dark-tinted glass (approach a). Seats remain in
    the file but stay dim behind opaque skin+glass until a cleaner Boolean
    punch is reintroduced.
    """
    if nose_obj is None:
        return
    print("C919_NOTE punched_ws_faces", 0, "(ws1 skipped — exterior solid shell)")


def pitot_probes_PLACEHOLDER_DO_NOT_USE():
    pass


def windshield_wipers():
    """Thin flat arms parked vertically along center post (real C919).

    ws1: low-profile disc hubs (not ball spheres), slim elbow near base,
    blade tucked against center mullion. No fat cylinders / end-cap blobs.
    """
    bm = bmesh.new()

    for side in (-1.0, 1.0):
        # Hub just below sill glass, close to center post
        a_hub = side * math.radians(4.2)
        p_hub = Vector(_canopy_point(a_hub, 17.52, 0.018))

        # Low-profile disc hub (flat cylinder), NOT a UV sphere ball
        before = set(bm.verts)
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=12,
            radius1=0.016,
            radius2=0.016,
            depth=0.010,
        )
        created = [v for v in bm.verts if v not in before]
        # Orient disc roughly along surface normal (local Z out)
        # Default cone axis is Z; lay flat on skin: rotate X 90 then place
        bmesh.ops.rotate(
            bm,
            verts=created,
            cent=(0, 0, 0),
            matrix=Matrix.Rotation(math.radians(90), 3, "X"),
        )
        bmesh.ops.translate(bm, verts=created, vec=p_hub)

        # Thin arm: hub → up along center post (toward brow / smaller Y)
        a_tip = side * math.radians(3.0)
        p_elbow = Vector(_canopy_point(a_hub + side * math.radians(1.5), 17.28, 0.020))
        p_tip = Vector(_canopy_point(a_tip, 16.40, 0.020))

        def _flat_bar(p0, p1, width, thick):
            nonlocal bm
            d = p1 - p0
            length = max(d.length, 1e-4)
            mid = (p0 + p1) * 0.5
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(width, length * 0.5, thick))
            quat = d.normalized().to_track_quat("Y", "Z")
            bmesh.ops.transform(
                bm,
                verts=created,
                matrix=Matrix.Translation(mid) @ quat.to_matrix().to_4x4(),
            )

        # Lower arm segment (hub → elbow)
        _flat_bar(p_hub, p_elbow, 0.010, 0.006)
        # Upper arm (elbow → tip along pillar)
        _flat_bar(p_elbow, p_tip, 0.009, 0.005)

        # Slim blade along arm (slightly longer, flatter)
        blade_lo = Vector(_canopy_point(a_hub + side * math.radians(0.5), 17.20, 0.021))
        blade_hi = Vector(_canopy_point(a_tip + side * math.radians(0.8), 16.48, 0.021))
        _flat_bar(blade_lo, blade_hi, 0.014, 0.004)

        # Tiny washer nozzle (optional, very small — not a blob)
        nozzle = Vector(_canopy_point(a_hub + side * math.radians(10.0), 17.55, 0.014))
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.006)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=nozzle)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


'''

# The NEW block accidentally includes a placeholder that would break pitot_probes.
# Fix: end NEW before pitot — we only replace windshield..wipers, and pitot must stay.
# Our NEW currently ends with windshield_wipers and then has a bad placeholder.
# Rebuild NEW without the placeholder.

NEW = r'''def cockpit_windshield():
    """Four double-curved C919 panes, slightly recessed under thin frames.

    ws1: modest recess (r_off~0.004) so glass sits behind flush metallic
    ribbons; dense sampling for continuous double curvature.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.004)
    return finish(bm)


def cockpit_frames():
    """Flush thin metallic frame ribbons + restrained dark seal lip.

    ws1 (real C919 refs): NO tubular pipe stacks, NO parallel thick arcs.
    Narrow center post (~1.2 deg), thin corner posts, hairline brow/sill.
    Single-layer shell only (no shell+raised_strip double stack).
    """
    bm = bmesh.new()
    # Barely proud of glass (glass at +0.004)
    r_metal = 0.011
    r_seal = 0.007

    # Narrow posts: angular half-widths ~0.55–0.70 deg (was ~1.6–1.8)
    # Center post especially thin so it is a divider, not a beam.
    mullions = [
        # aft cheek terminations (very thin)
        (-math.radians(110.55), -math.radians(109.45), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.45), math.radians(110.55), [16.88, 16.48, 16.10, 15.72, 15.48]),
        # fwd/side junctions
        (-math.radians(49.55), -math.radians(48.45), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.45), math.radians(49.55), [17.62, 17.20, 16.80, 16.45, 16.28]),
        # CENTER post — narrow (~1.2 deg total)
        (-math.radians(0.60), math.radians(0.60), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
    for a0, a1, ys in mullions:
        # outer metallic face
        _add_shell_sector(bm, ys, a0, a1, r_metal, segs_a=2)
        # dark seal lip (slightly inset radially, same angular span tightened)
        mid = 0.5 * (a0 + a1)
        half = 0.55 * abs(a1 - a0)
        _add_shell_sector(bm, ys, mid - half, mid + half, r_seal, segs_a=2)

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

    # Per-pane brow/sill (not one continuous heavy tube across all panes)
    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), -math.radians(2.8)),
        (math.radians(2.8), math.radians(48)),
        (math.radians(50), math.radians(110)),
    ]
    for a0, a1 in spans:
        a_list = [_lerp(a0, a1, i / 36.0) for i in range(37)]
        # hairline half-width (was 0.016 — tubular)
        for y_fn, half in ((sill_y, 0.0055), (brow_y, 0.0055)):
            _add_curve_ribbon(bm, a_list, y_fn, half, r_in=r_seal, r_out=r_metal)

    # Soft cheek fairing: very flat (r_off tiny) — blends side pane into nose
    # without reading as a raised tube or rectangular cut.
    for sign in (-1.0, 1.0):
        ys = [16.80, 16.35, 15.90, 15.50]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(108),
            sign * math.radians(118),
            0.003,
            segs_a=4,
        )

    return finish(bm)


def punch_windshield_openings(nose_obj):
    """ws1: SKIP punch for exterior white-model priority.

    Prior VIS1/cockpit3 face-delete left ragged cavity rims and overlapping
    edges that read as openings/cross-sections. Exterior pass keeps Nose
    skin continuous under dark-tinted glass (approach a). Seats remain in
    the file but stay dim behind opaque skin+glass until a cleaner Boolean
    punch is reintroduced.
    """
    if nose_obj is None:
        return
    print("C919_NOTE punched_ws_faces", 0, "(ws1 skipped — exterior solid shell)")


def windshield_wipers():
    """Thin flat arms parked vertically along center post (real C919).

    ws1: low-profile disc hubs (not ball spheres), slim elbow near base,
    blade tucked against center mullion. No fat cylinders / end-cap blobs.
    """
    bm = bmesh.new()

    for side in (-1.0, 1.0):
        # Hub just below sill glass, close to center post
        a_hub = side * math.radians(4.2)
        p_hub = Vector(_canopy_point(a_hub, 17.52, 0.018))

        # Low-profile disc hub (flat cylinder), NOT a UV sphere ball
        before = set(bm.verts)
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=12,
            radius1=0.016,
            radius2=0.016,
            depth=0.010,
        )
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.rotate(
            bm,
            verts=created,
            cent=(0, 0, 0),
            matrix=Matrix.Rotation(math.radians(90), 3, "X"),
        )
        bmesh.ops.translate(bm, verts=created, vec=p_hub)

        # Thin arm: hub → up along center post (toward brow / smaller Y)
        a_tip = side * math.radians(3.0)
        p_elbow = Vector(_canopy_point(a_hub + side * math.radians(1.5), 17.28, 0.020))
        p_tip = Vector(_canopy_point(a_tip, 16.40, 0.020))

        def _flat_bar(p0, p1, width, thick):
            d = p1 - p0
            length = max(d.length, 1e-4)
            mid = (p0 + p1) * 0.5
            before_local = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created_local = [v for v in bm.verts if v not in before_local]
            bmesh.ops.scale(
                bm, verts=created_local, vec=(width, length * 0.5, thick)
            )
            quat = d.normalized().to_track_quat("Y", "Z")
            bmesh.ops.transform(
                bm,
                verts=created_local,
                matrix=Matrix.Translation(mid) @ quat.to_matrix().to_4x4(),
            )

        # Lower arm segment (hub → elbow)
        _flat_bar(p_hub, p_elbow, 0.010, 0.006)
        # Upper arm (elbow → tip along pillar)
        _flat_bar(p_elbow, p_tip, 0.009, 0.005)

        # Slim blade along arm (slightly longer, flatter)
        blade_lo = Vector(
            _canopy_point(a_hub + side * math.radians(0.5), 17.20, 0.021)
        )
        blade_hi = Vector(
            _canopy_point(a_tip + side * math.radians(0.8), 16.48, 0.021)
        )
        _flat_bar(blade_lo, blade_hi, 0.014, 0.004)

        # Tiny washer nozzle (optional, very small — not a blob)
        nozzle = Vector(
            _canopy_point(a_hub + side * math.radians(10.0), 17.55, 0.014)
        )
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.006)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=nozzle)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


'''

# Find true end: after windshield_wipers function, next is cockpit_glare_shield
# But punch sits BETWEEN cockpit_frames and pitot_probes, and wipers after pitot.
# Structure in file:
#   cockpit_windshield
#   cockpit_frames
#   punch_windshield_openings
#   pitot_probes
#   windshield_wipers
#   cockpit_glare_shield

# So we cannot replace one contiguous block from windshield to wipers without
# eating pitot_probes. Do three separate replacements.

def replace_func(src, name, new_body_with_def):
    """Replace from 'def name' through just before the next top-level def."""
    marker = f"def {name}("
    i = src.index(marker)
    # find next def at beginning of line after i+1
    j = i + len(marker)
    while True:
        k = src.find("\ndef ", j)
        if k < 0:
            raise SystemExit(f"no next def after {name}")
        # ensure it's top-level (def at col 0 after newline)
        # skip nested? we only have top-level defs
        nxt = src[k + 1 : src.find("(", k)]
        # skip if it's somehow wrong
        break
    # include trailing blank lines before next def
    return src[:i] + new_body_with_def.rstrip() + "\n\n\n" + src[k + 1 :]

# Split NEW into three function strings
import re

parts = {}
for fname in ("cockpit_windshield", "cockpit_frames", "punch_windshield_openings", "windshield_wipers"):
    m = re.search(
        rf"(def {fname}\(.*?)(?=\ndef )",
        NEW + "\ndef _END():\n    pass\n",
        re.S,
    )
    if not m:
        raise SystemExit(f"parse fail {fname}")
    parts[fname] = m.group(1)

text2 = text
for fname in ("cockpit_windshield", "cockpit_frames", "punch_windshield_openings", "windshield_wipers"):
    text2 = replace_func(text2, fname, parts[fname])
    print("replaced", fname)

# Material: silver metal for CockpitFrames
old_cf = 'cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", frame_mat, "navy")'
new_cf = '''cockpit_metal = material("CockpitMetal", (0.72, 0.74, 0.76), 0.28, 0.85)
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", cockpit_metal, "navy")'''
if old_cf not in text2:
    raise SystemExit("cf_obj link not found")
text2 = text2.replace(old_cf, new_cf, 1)

# Darker exterior glass (reads as glazing on white skin without punch)
old_g = '''    # cockpit3: clearer glass so seats/wipers/dash read through panes
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

new_g = '''    # ws1: darker exterior glazing (no punch — panes read on white skin)
    cockpit_glass = glass_material("CockpitGlass")
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.55),
            ("Transmission", 0.55),
            ("Alpha", 0.42),
            ("Roughness", 0.045),
            ("IOR", 1.45),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.05, 0.07, 0.10, 1.0)'''

if old_g not in text2:
    raise SystemExit("glass block not found")
text2 = text2.replace(old_g, new_g, 1)

# Update end note
text2 = text2.replace(
    'print("C919_NOTE cockpit3=thick-wipers+airline-seats+glare-dash+clean-WS-punch")',
    'print("C919_NOTE ws1=flush-thin-frames+vertical-wipers+no-punch-exterior")',
)

SRC.write_text(text2, encoding="utf-8")
print("WS1 patch written", SRC, "bytes", SRC.stat().st_size)
# Sanity: pitot still present, no placeholder
assert "def pitot_probes():" in text2
assert "PLACEHOLDER" not in text2
assert "def cockpit_windshield():" in text2
assert "ws1 skipped" in text2
print("sanity ok")

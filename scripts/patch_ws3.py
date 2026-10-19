# -*- coding: utf-8 -*-
"""ws3: transparent 4-pane windshield aligned to REF; kill CockpitMask; punch openings."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
# When run from project scripts/, parent is project root.
if (ROOT / "build_c919.py").exists() and not (ROOT / "scripts").exists():
    # running from /workspace/c919-work copy
    BUILD = ROOT / "build_c919.py"
    BAK = ROOT / "build_c919.py.bak-ws3"
else:
    BUILD = ROOT / "scripts" / "build_c919.py"
    BAK = ROOT / "scripts" / "build_c919.py.bak-ws3"

t = BUILD.read_text(encoding="utf-8")
shutil.copy2(BUILD, BAK)
print("BACKUP", BAK)

# ---------------------------------------------------------------------------
# 1) Transparent cockpit glass (#DDEEEB, Transmission=1.0)
# ---------------------------------------------------------------------------
new_glass_fn = '''def cockpit_glass_material(name="CockpitGlass"):
    """ws3: clear tinted windshield — Transmission 1.0, faint blue-green #DDEEEB."""
    # #DDEEEB → linear-ish approx
    col = (0.867, 0.933, 0.922)
    mat = material(name, col, 0.02, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (col[0], col[1], col[2], 1.0)
        for key, val in (
            ("Transmission Weight", 1.0),
            ("Transmission", 1.0),
            ("Alpha", 0.18),
            ("IOR", 1.5),
            ("Roughness", 0.02),
            ("Metallic", 0.0),
            ("Specular IOR Level", 0.5),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    try:
        mat.blend_method = "HASHED"  # EEVEE: not Opaque; better than BLEND for glass
    except Exception:
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    try:
        mat.shadow_method = "NONE"
    except Exception:
        pass
    # Blender 5 / EEVEE raytrace hints when present
    for attr, val in (
        ("use_screen_refraction", True),
        ("use_raytrace_refraction", True),
        ("refraction_depth", 0.02),
    ):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat

'''

pat = re.compile(
    r"def cockpit_glass_material\(name=\"CockpitGlass\"\):.*?(?=\ndef _paint_star|\ndef material|\ndef glass_material|\ndef _lerp)",
    re.S,
)
# Function sits early — find exact block until next def at column 0 after it
m = re.search(
    r"def cockpit_glass_material\(name=\"CockpitGlass\"\):.*?(?=\n\ndef |\n\ndef)",
    t,
    re.S,
)
if not m:
    # try without double newline
    m = re.search(
        r"def cockpit_glass_material\(name=\"CockpitGlass\"\):.*?(?=\ndef )",
        t,
        re.S,
    )
if not m:
    raise SystemExit("cockpit_glass_material not found")
t = t[: m.start()] + new_glass_fn + t[m.end() :]
print("OK glass_fn")

# ---------------------------------------------------------------------------
# 2) Pane defs from REF (side a~50–105) + Soft radome/WS belt; NO expand/mask
# ---------------------------------------------------------------------------
new_panes = '''def _cockpit_pane_defs(expand=0.0):
    """ws3: C919 four panes aligned to REF silhouette (measure-only).

    REF (scale 0.01, nose −Y→mapped to Soft +Y tip 19.88):
      side opening azimuth ~50–104° from crown; front |a|<~48°.
    Soft belt: sill just aft of radome (~17.55), brow ~16.15 — NOT onto crown.
    expand ignored (kept for call-site compat); no CockpitMask oversize.
    Angle 0 = crown (+Z). L/R mirrors.
    """
    _ = expand  # noqa: F841 — ws3: no mask expand

    def fwd_y_fwd(a):
        t = min(1.0, abs(a) / math.radians(47))
        s = t * t * (3.0 - 2.0 * t)
        # nearly level sill; slightly aft toward corner
        return _lerp(17.62, 17.50, s)

    def fwd_y_aft(a):
        t = min(1.0, abs(a) / math.radians(47))
        s = t * t * (3.0 - 2.0 * t)
        # brow dips less at center (no roof wrap); corners a bit higher/aft
        return _lerp(16.18, 16.32, s)

    def side_y_fwd(a):
        t = (abs(a) - math.radians(49)) / (math.radians(105) - math.radians(49) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.48, 16.92, s)

    def side_y_aft(a):
        # aft edge leans back: crown-ward more aft (smaller Y), outer sill less aft
        t = (abs(a) - math.radians(49)) / (math.radians(105) - math.radians(49) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(15.58, 16.05, s)

    gap = math.radians(1.2)
    corner = math.radians(47.5)
    side_out = math.radians(105)
    return [
        {
            "name": "SW_L",
            "a0": -side_out,
            "a1": -corner - gap * 0.5,
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 22,
            "segs_y": 16,
        },
        {
            "name": "WS_L",
            "a0": -corner + gap * 0.5,
            "a1": -gap,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 18,
            "segs_y": 14,
        },
        {
            "name": "WS_R",
            "a0": gap,
            "a1": corner - gap * 0.5,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 18,
            "segs_y": 14,
        },
        {
            "name": "SW_R",
            "a0": corner + gap * 0.5,
            "a1": side_out,
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 22,
            "segs_y": 16,
        },
    ]


'''

m = re.search(
    r"def _cockpit_pane_defs\(expand=0\.0\):.*?(?=\ndef _add_canopy_pane)",
    t,
    re.S,
)
if not m:
    raise SystemExit("pane_defs not found")
t = t[: m.start()] + new_panes + t[m.end() :]
print("OK panes")

# ---------------------------------------------------------------------------
# 3) Replace windshield / mask / frames with ws3 versions
# ---------------------------------------------------------------------------
new_ws_block = '''def _add_canopy_pane_solid(bm, pane, r_out, r_in):
    """Double shell (~1–2 cm) so glass has thickness for glTF/EEVEE."""
    a0, a1 = pane["a0"], pane["a1"]
    segs_a, segs_y = pane["segs_a"], pane["segs_y"]
    outer, inner = [], []
    for j in range(segs_y + 1):
        ty = j / segs_y
        ro, ri = [], []
        for i in range(segs_a + 1):
            ta = i / segs_a
            a = _lerp(a0, a1, ta)
            y = _lerp(pane["y_fwd"](a), pane["y_aft"](a), ty)
            ro.append(bm.verts.new(_canopy_point(a, y, r_out)))
            ri.append(bm.verts.new(_canopy_point(a, y, r_in)))
        outer.append(ro)
        inner.append(ri)
    for j in range(segs_y):
        for i in range(segs_a):
            bm.faces.new(
                (outer[j][i], outer[j + 1][i], outer[j + 1][i + 1], outer[j][i + 1])
            )
            # inward face (reverse winding)
            bm.faces.new(
                (inner[j][i + 1], inner[j + 1][i + 1], inner[j + 1][i], inner[j][i])
            )
    # rim between outer/inner
    for j in range(segs_y + 1):
        for i, border in (
            (0, True),
            (segs_a, True),
        ):
            pass
    for i in range(segs_a):
        # fwd rim j=0, aft rim j=segs_y
        for j in (0, segs_y):
            o0, o1 = outer[j][i], outer[j][i + 1]
            i0, i1 = inner[j][i], inner[j][i + 1]
            if j == 0:
                bm.faces.new((o0, i0, i1, o1))
            else:
                bm.faces.new((o1, i1, i0, o0))
    for j in range(segs_y):
        for i in (0, segs_a):
            o0, o1 = outer[j][i], outer[j + 1][i]
            i0, i1 = inner[j][i], inner[j + 1][i]
            if i == 0:
                bm.faces.new((o0, o1, i1, i0))
            else:
                bm.faces.new((o1, o0, i0, i1))


def cockpit_pane_mesh(pane_name):
    """One named pane mesh (WS_L / WS_R / SW_L / SW_R)."""
    bm = bmesh.new()
    pane = None
    for p in _cockpit_pane_defs():
        if p["name"] == pane_name:
            pane = dict(p)
            break
    if pane is None:
        raise ValueError(pane_name)
    pane["segs_a"] = max(pane["segs_a"], 24)
    pane["segs_y"] = max(pane["segs_y"], 16)
    # flush: outer ~6 mm proud, inner ~10 mm inset → ~1.6 cm thick
    _add_canopy_pane_solid(bm, pane, r_out=0.006, r_in=-0.010)
    return finish(bm)


def cockpit_windshield():
    """ws3: combined four panes (legacy single object; prefer cockpit_pane_mesh)."""
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 24)
        pane["segs_y"] = max(pane["segs_y"], 16)
        _add_canopy_pane_solid(bm, pane, r_out=0.006, r_in=-0.010)
    return finish(bm)


def cockpit_mask():
    """ws3: removed — return empty mesh so any stale call is harmless."""
    bm = bmesh.new()
    return finish(bm)


def cockpit_frames():
    """ws3: narrow black seals 3–6 cm + thin center/corner pillars (no faceplate)."""
    bm = bmesh.new()
    r_off = 0.011  # just outside glass outer

    # Center pillar ~4 cm arc ≈ 1.1°
    _add_shell_sector(
        bm,
        [17.58, 17.20, 16.80, 16.45, 16.18],
        -math.radians(0.55),
        math.radians(0.55),
        r_off,
        segs_a=2,
    )
    # Corner posts front/side
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(46.9)
        a1 = sign * math.radians(48.3)
        lo, hi = (a0, a1) if a0 < a1 else (a1, a0)
        _add_shell_sector(
            bm,
            [17.48, 17.05, 16.60, 16.20],
            lo,
            hi,
            r_off,
            segs_a=2,
        )
    # Side aft posts
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(104.2)
        a1 = sign * math.radians(105.8)
        lo, hi = (a0, a1) if a0 < a1 else (a1, a0)
        _add_shell_sector(
            bm,
            [16.90, 16.40, 15.95, 15.60],
            lo,
            hi,
            r_off,
            segs_a=2,
        )

    def sill_y(a):
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

    def _seal_strip(a0, a1, y_fn, half_y=0.022, n=28):
        """~4.4 cm seal half-width along Y on canopy."""
        a_list = [_lerp(a0, a1, i / float(n)) for i in range(n + 1)]
        ou, ol = [], []
        for a in a_list:
            y = y_fn(a)
            ou.append(bm.verts.new(_canopy_point(a, y + half_y, r_off)))
            ol.append(bm.verts.new(_canopy_point(a, y - half_y, r_off)))
        for i in range(n):
            bm.faces.new((ou[i], ou[i + 1], ol[i + 1], ol[i]))

    spans = [
        (-math.radians(105), -math.radians(49)),
        (-math.radians(47.5), -math.radians(1.2)),
        (math.radians(1.2), math.radians(47.5)),
        (math.radians(49), math.radians(105)),
    ]
    for a0, a1 in spans:
        _seal_strip(a0, a1, sill_y, 0.022)
        _seal_strip(a0, a1, brow_y, 0.022)

    return finish(bm)


def cockpit_cabin_shell():
    """ws3: simple dark cabin tube + dash silhouette visible through glass."""
    bm = bmesh.new()
    # Inner tube under windshield belt
    ys = [17.70, 17.20, 16.70, 16.20, 15.70, 15.20]
    segs = 28
    scale = 0.82
    rings = []
    for y in ys:
        rx, rz = _section_at_y(y)
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            # a_canopy uses 0=crown from +Z; here full circle from +X
            x = math.cos(a) * rx * scale
            z = math.sin(a) * rz * scale
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    # Dash shelf under sill (dark board)
    dash_y = 17.35
    dash_z = 0.55
    dash_x = 0.95
    dash_depth = 0.55
    corners = [
        (-dash_x, dash_y, dash_z),
        (dash_x, dash_y, dash_z),
        (dash_x, dash_y - dash_depth, dash_z),
        (-dash_x, dash_y - dash_depth, dash_z),
        (-dash_x, dash_y, dash_z - 0.08),
        (dash_x, dash_y, dash_z - 0.08),
        (dash_x, dash_y - dash_depth, dash_z - 0.08),
        (-dash_x, dash_y - dash_depth, dash_z - 0.08),
    ]
    vs = [bm.verts.new(c) for c in corners]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 3, 7, 4),
        (1, 5, 6, 2),
        (0, 4, 5, 1),
        (3, 2, 6, 7),
    ]
    for f in faces:
        bm.faces.new(tuple(vs[i] for i in f))
    return finish(bm)


'''

# Replace from _add_canopy_pane through end of cockpit_frames (keep punch)
# Keep existing _add_canopy_pane / _add_shell_sector helpers — insert solid after them
# Strategy: replace cockpit_windshield through cockpit_frames inclusive

m = re.search(
    r"def cockpit_windshield\(\):.*?return finish\(bm\)\n\n\ndef cockpit_mask\(\):.*?return finish\(bm\)\n\n\ndef cockpit_frames\(\):.*?return finish\(bm\)\n\n\n",
    t,
    re.S,
)
if not m:
    # try single newlines
    m = re.search(
        r"def cockpit_windshield\(\):.*?def cockpit_mask\(\):.*?def cockpit_frames\(\):.*?return finish\(bm\)\n\n",
        t,
        re.S,
    )
if not m:
    raise SystemExit("windshield/mask/frames block not found")

# Prepend solid helper before cockpit_windshield — inject after _add_curve_ribbon block
# Actually new_ws_block includes helpers starting with _add_canopy_pane_solid
t = t[: m.start()] + new_ws_block + t[m.end() :]
print("OK ws/mask/frames")

# ---------------------------------------------------------------------------
# 4) Re-enable punch; widen Y gate for new panes (~15.4–17.75)
# ---------------------------------------------------------------------------
t = t.replace(
    "    # ws2: NO punch — continuous nose skin under flush sunglass mask/glass\n"
    "    # punch_windshield_openings(bpy.data.objects.get(\"Nose\"))  # disabled\n",
    "    # ws3: clean punched openings so transparent glass shows cabin\n"
    "    punch_windshield_openings(bpy.data.objects.get(\"Nose\"))\n",
)
if "punch_windshield_openings(bpy.data.objects.get(\"Nose\"))" not in t:
    raise SystemExit("punch re-enable failed")
print("OK punch enabled")

# Update punch Y window
t = t.replace(
    "        if y < 15.40 or y > 17.80:\n",
    "        if y < 15.35 or y > 17.85:\n",
)

# punch calls _cockpit_pane_defs() — OK with default expand=0

# ---------------------------------------------------------------------------
# 5) build(): link 4 panes, seals, cabin; remove CockpitMask; fix glass dup
# ---------------------------------------------------------------------------
old_ws_link = '''    cockpit_glass = cockpit_glass_material("CockpitGlass")
    ws_obj = link("Windshield", cockpit_windshield(), "avionics", cockpit_glass, "glass")
    mask_mat = material("CockpitMask", (0.025, 0.028, 0.032), 0.85, 0.0)
    mask_obj = link("CockpitMask", cockpit_mask(), "avionics", mask_mat, "navy")
    cockpit_metal = material("CockpitMetal", (0.22, 0.23, 0.25), 0.42, 0.55)
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", cockpit_metal, "navy")
    # Cabin panes/frames + cockpit frames: flat. Windshield stays smooth (curved canopy).
    for ob in (win_obj, wf_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = False
    # Windshield + mask + thin frames: smooth sunglass curvature
    for ob in (ws_obj, mask_obj, cf_obj):
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''

new_ws_link = '''    cockpit_glass = cockpit_glass_material("CockpitGlass")
    seal_mat = material("CockpitSeal", (0.02, 0.02, 0.025), 0.55, 0.0)
    pane_objs = []
    for pname in ("WS_L", "WS_R", "SW_L", "SW_R"):
        ob = link(pname, cockpit_pane_mesh(pname), "avionics", cockpit_glass, "glass")
        pane_objs.append(ob)
    # Legacy aggregate name kept for older viewers / MISSING checks
    ws_obj = link("Windshield", cockpit_windshield(), "avionics", cockpit_glass, "glass")
    ws_obj.hide_render = True
    ws_obj.hide_viewport = True
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", seal_mat, "navy")
    cabin_mat = material("CockpitCabin", (0.04, 0.045, 0.05), 0.75, 0.0)
    cabin_obj = link("CockpitCabin", cockpit_cabin_shell(), "avionics", cabin_mat, "navy")
    for ob in (win_obj, wf_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = False
    for ob in pane_objs + [cf_obj, cabin_obj]:
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''

if old_ws_link not in t:
    raise SystemExit("ws link block not found exact")
t = t.replace(old_ws_link, new_ws_link, 1)
print("OK build link")

# Remove duplicate inside1 glass reassignment + unhide glare; dark seats
old_inside = '''    # inside1: transparent cockpit glass so seats show through openings
    cockpit_glass = material("CockpitGlass", (0.06, 0.09, 0.12), 0.06, 0.0)
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.86),
            ("Transmission", 0.86),
            ("Alpha", 0.28),
            ("Roughness", 0.05),
            ("IOR", 1.45),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.06, 0.09, 0.12, 1.0)
    try:
        cockpit_glass.blend_method = "BLEND"
    except Exception:
        pass
    try:
        cockpit_glass.use_backface_culling = False
    except Exception:
        pass
    try:
        cockpit_glass.shadow_method = "NONE"
    except Exception:
        pass

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
    # ws2: hide glare — exterior uses dark glass + mask only
    if gs_obj:
        gs_obj.hide_render = True
        gs_obj.hide_viewport = True
    seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "stripe")
    # ws2: seats not for exterior — hide (continuous nose; no punch cave)
    if seat_obj:
        seat_obj.hide_render = True
        seat_obj.hide_viewport = True
    # Soft-shade seats/glare so cushion silhouette reads less like crates
    for ob in (gs_obj, seat_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''

new_inside = '''    # ws3: glass already assigned; show dark glare + dark seat silhouettes through openings
    wiper_mat = material("Wiper", (0.05, 0.05, 0.06), 0.45, 0.15)
    wp_obj = link("WindshieldWipers", windshield_wipers(), "avionics", wiper_mat, "navy")
    for poly in wp_obj.data.polygons:
        poly.use_smooth = True

    glare_mat = material("GlareShield", (0.05, 0.055, 0.06), 0.60, 0.05)
    seat_mat = material("PilotSeat", (0.08, 0.08, 0.09), 0.70, 0.02)  # dark, not red
    gs_obj = link("GlareShield", cockpit_glare_shield(), "avionics", glare_mat, "navy")
    seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "navy")
    for ob in (gs_obj, seat_obj):
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''

if old_inside not in t:
    raise SystemExit("inside1 block not found")
t = t.replace(old_inside, new_inside, 1)
print("OK interior")

# export_glb: keep glare/seats (visible dark); stop deleting them
t = t.replace(
    '''    # ws2c: do not ship hidden interior seats/glare into GLB
    for name in ("PilotSeats", "GlareShield"):
        ob = bpy.data.objects.get(name)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
''',
    '''    # ws3: keep dark glare/seats for see-through; hide duplicate Windshield aggregate
    wsdup = bpy.data.objects.get("Windshield")
    if wsdup is not None and wsdup.hide_viewport:
        bpy.data.objects.remove(wsdup, do_unlink=True)
''',
)
print("OK export")

# Required names / subdiv skip
t = t.replace('"CockpitMask",\n', '"WS_L",\n        "WS_R",\n        "SW_L",\n        "SW_R",\n        "CockpitCabin",\n')
# subdiv skip: CockpitMask → new names
t = t.replace(
    '        "CockpitMask",\n',
    '        "WS_L",\n        "WS_R",\n        "SW_L",\n        "SW_R",\n        "CockpitCabin",\n',
)

# Fix MISSING list if separate from subdiv - check
if "CockpitMask" in t:
    print("WARN CockpitMask still present at:", [i for i,l in enumerate(t.splitlines()) if "CockpitMask" in l][:10])

BUILD.write_text(t, encoding="utf-8")
print("WROTE", BUILD, "bytes", BUILD.stat().st_size)

# sanity
assert "def cockpit_pane_mesh" in t
assert "punch_windshield_openings(bpy.data.objects.get" in t
assert "CockpitMask" not in t or t.count("CockpitMask") <= 2  # maybe in comments
assert "Transmission Weight\", 1.0)" in t or 'Transmission Weight", 1.0)' in t
print("WS3_PATCH_OK")

# -*- coding: utf-8 -*-
"""ws2: no punch cave; flush 4-pane sunglass mask + dark glass; keep door2."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

# --- 1) Dark cockpit glass (exterior: seats not readable) ---
old_glass = '''def glass_material(name="Glass"):
    """Tinted cabin/cockpit glass with real transparency (glTF transmission + alpha)."""
    mat = material(name, (0.08, 0.12, 0.18), 0.05, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.08, 0.12, 0.18, 1.0)
        for key, val in (
            ("Transmission Weight", 0.55),
            ("Transmission", 0.55),
            ("Alpha", 0.55),
            ("IOR", 1.45),
            ("Roughness", 0.06),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
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
    return mat
'''

new_glass = '''def glass_material(name="Glass"):
    """Cabin window glass (lighter). Cockpit uses cockpit_glass_material()."""
    mat = material(name, (0.08, 0.12, 0.18), 0.05, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.08, 0.12, 0.18, 1.0)
        for key, val in (
            ("Transmission Weight", 0.55),
            ("Transmission", 0.55),
            ("Alpha", 0.55),
            ("IOR", 1.45),
            ("Roughness", 0.06),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
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
    return mat


def cockpit_glass_material(name="CockpitGlass"):
    """ws2: dark reflective windshield — Transmission high but tint/alpha hide seats."""
    mat = material(name, (0.02, 0.04, 0.06), 0.02, 0.05)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.02, 0.05, 0.07, 1.0)
        for key, val in (
            ("Transmission Weight", 0.82),
            ("Transmission", 0.82),
            ("Alpha", 0.38),
            ("IOR", 1.52),
            ("Roughness", 0.02),
            ("Metallic", 0.08),
            ("Specular IOR Level", 0.65),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
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
    return mat
'''

if "def cockpit_glass_material" in t:
    print("GLASS_FN already")
elif old_glass in t:
    t = t.replace(old_glass, new_glass, 1)
    print("GLASS_FN exact")
else:
    raise SystemExit("glass_material block not found")

# --- 2) Sunglass pane defs (4 panes, side rake aft-up) ---
new_panes = '''def _cockpit_pane_defs(expand=0.0):
    """C919 four-pane sunglass mask (ws2).

    expand>0 grows the footprint for CockpitMask (dark face larger than glass).
    Side panes rake aft-up; front brow tucks into crown (side-view arc, not box).
    Angle 0 = crown (+Z). L/R mirrors.
    """
    ex = expand

    def fwd_y_fwd(a):
        t = min(1.0, abs(a) / math.radians(48))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.58 + ex * 0.4, 17.48 + ex * 0.3, s)

    def fwd_y_aft(a):
        # Brow deeper into crown at center → continuous downward arc in side view
        t = min(1.0, abs(a) / math.radians(48))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(15.98 - ex * 0.35, 16.22 - ex * 0.2, s)

    def side_y_fwd(a):
        t = (abs(a) - math.radians(48)) / (math.radians(112) - math.radians(48) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.46 + ex * 0.25, 16.70 + ex * 0.2, s)

    def side_y_aft(a):
        # Aft-up rake (sunglasses): aft edge climbs toward crown as |a| grows mid-cheek
        t = (abs(a) - math.radians(48)) / (math.radians(112) - math.radians(48) + 1e-9)
        t = min(1.0, max(0.0, t))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(16.18 - ex * 0.25, 15.35 - ex * 0.35, s)

    # Angular extents: narrow center gap; cheeks wrap further aft
    gap = math.radians(1.1)
    corner = math.radians(47.5)
    side_out = math.radians(112)
    return [
        {
            "name": "side_L",
            "a0": -side_out - math.radians(ex * 8),
            "a1": -corner - gap * 0.5,
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 24,
            "segs_y": 16,
        },
        {
            "name": "fwd_L",
            "a0": -corner + gap * 0.5,
            "a1": -gap,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 20,
            "segs_y": 16,
        },
        {
            "name": "fwd_R",
            "a0": gap,
            "a1": corner - gap * 0.5,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 20,
            "segs_y": 16,
        },
        {
            "name": "side_R",
            "a0": corner + gap * 0.5,
            "a1": side_out + math.radians(ex * 8),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 24,
            "segs_y": 16,
        },
    ]

'''

pat_panes = re.compile(
    r"def _cockpit_pane_defs\([^\)]*\):.*?return \[\n(?:.*?\n)*?    \]\n\n\n",
    re.S,
)
# More robust: from def to before def _add_canopy_pane
pat_panes = re.compile(
    r"def _cockpit_pane_defs\(.*?\n(?=def _add_canopy_pane)",
    re.S,
)
if not pat_panes.search(t):
    raise SystemExit("_cockpit_pane_defs not found")
t = pat_panes.sub(new_panes, t, count=1)
print("PANES_OK")

# --- 3) Replace windshield / frames / add mask ---
new_ws_block = '''def cockpit_windshield():
    """ws2: four flush sunglass panes on continuous skin (NO punch).

    Glass sits a few mm proud of dark CockpitMask; continuous Nose underneath.
    """
    bm = bmesh.new()
    for pane in _cockpit_pane_defs(expand=0.0):
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.0035)
    return finish(bm)


def cockpit_mask():
    """ws2: dark matte face-mask — larger than glass; visual key of C919 cockpit."""
    bm = bmesh.new()
    for pane in _cockpit_pane_defs(expand=0.55):
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 22)
        pane["segs_y"] = max(pane["segs_y"], 14)
        # Slightly under glass, on skin
        _add_canopy_pane(bm, pane, r_off=0.0010)
    # Fill narrow center gap so mask reads as one sunglass band
    def yf(a):
        t = min(1.0, abs(a) / math.radians(48))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(17.58, 17.48, s)

    def ya(a):
        t = min(1.0, abs(a) / math.radians(48))
        s = t * t * (3.0 - 2.0 * t)
        return _lerp(15.98, 16.22, s)

    gap_pane = {
        "a0": -math.radians(1.4),
        "a1": math.radians(1.4),
        "y_fwd": yf,
        "y_aft": ya,
        "segs_a": 4,
        "segs_y": 14,
    }
    _add_canopy_pane(bm, gap_pane, r_off=0.0010)
    return finish(bm)


def cockpit_frames():
    """ws2: hairline center pillar + corner posts only — no thick car-door lips."""
    bm = bmesh.new()
    r_off = 0.0055  # barely proud of glass

    # Narrow center pillar only (~0.9 deg)
    _add_shell_sector(
        bm,
        [17.50, 17.10, 16.70, 16.30, 15.95],
        -math.radians(0.45),
        math.radians(0.45),
        r_off,
        segs_a=2,
    )
    # Thin corner posts (front/side meet)
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(47.0)
        a1 = sign * math.radians(48.2)
        lo, hi = (a0, a1) if a0 < a1 else (a1, a0)
        _add_shell_sector(
            bm,
            [17.45, 17.00, 16.55, 16.15],
            lo,
            hi,
            r_off,
            segs_a=2,
        )
    return finish(bm)


'''

pat_ws = re.compile(
    r"def cockpit_windshield\(\):.*?return finish\(bm\)\n\n\ndef cockpit_frames\(\):.*?return finish\(bm\)\n\n\n(?=def punch_windshield)",
    re.S,
)
m = pat_ws.search(t)
if not m:
    # try without requiring punch next
    pat_ws = re.compile(
        r"def cockpit_windshield\(\):.*?return finish\(bm\)\n\n\ndef cockpit_frames\(\):.*?return finish\(bm\)\n",
        re.S,
    )
    m = pat_ws.search(t)
    if not m:
        raise SystemExit("windshield/frames block not found")
    t = pat_ws.sub(new_ws_block, t, count=1)
else:
    t = pat_ws.sub(new_ws_block + "\n", t, count=1)
print("WS_FRAMES_MASK_OK")

# --- 4) Skip punch call ---
old_punch_call = "    punch_windshield_openings(bpy.data.objects.get(\"Nose\"))\n"
new_punch_call = (
    "    # ws2: NO punch — continuous nose skin under flush sunglass mask/glass\n"
    "    # punch_windshield_openings(bpy.data.objects.get(\"Nose\"))  # disabled\n"
)
if "ws2: NO punch" in t:
    print("PUNCH_CALL already")
elif old_punch_call in t:
    t = t.replace(old_punch_call, new_punch_call, 1)
    print("PUNCH_CALL disabled")
else:
    raise SystemExit("punch call not found")

# --- 5) Main: link mask, dark glass, skip seats visibility ---
# Replace windshield linking block
old_link = '''    ws_obj = link("Windshield", cockpit_windshield(), "avionics", glass, "glass")
    cockpit_metal = material("CockpitMetal", (0.28, 0.29, 0.31), 0.38, 0.70)
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", cockpit_metal, "navy")
'''

new_link = '''    cockpit_glass = cockpit_glass_material("CockpitGlass")
    ws_obj = link("Windshield", cockpit_windshield(), "avionics", cockpit_glass, "glass")
    mask_mat = material("CockpitMask", (0.04, 0.045, 0.05), 0.78, 0.02)
    mask_obj = link("CockpitMask", cockpit_mask(), "avionics", mask_mat, "navy")
    cockpit_metal = material("CockpitMetal", (0.22, 0.23, 0.25), 0.42, 0.55)
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", cockpit_metal, "navy")
'''

if "CockpitMask" in t and "cockpit_glass_material" in t[t.find("ws_obj = link"):t.find("ws_obj = link")+800]:
    print("LINK already?")
if old_link in t:
    t = t.replace(old_link, new_link, 1)
    print("LINK exact")
else:
    # softer
    pat = re.compile(
        r"    ws_obj = link\(\"Windshield\".*?\n    cockpit_metal = material\(\"CockpitMetal\".*?\n    cf_obj = link\(\"CockpitFrames\".*?\n",
        re.S,
    )
    if not pat.search(t):
        raise SystemExit("ws/cf link block not found")
    t = pat.sub(new_link, t, count=1)
    print("LINK regex")

# Smooth mask too
old_smooth = '''    # Windshield + cockpit frames: smooth so canopy/mullions read as curves
    for ob in (ws_obj, cf_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''
new_smooth = '''    # Windshield + mask + thin frames: smooth sunglass curvature
    for ob in (ws_obj, mask_obj, cf_obj):
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True
'''
if "mask_obj, cf_obj" in t or "ws_obj, mask_obj, cf_obj" in t:
    print("SMOOTH already")
elif old_smooth in t:
    t = t.replace(old_smooth, new_smooth, 1)
    print("SMOOTH exact")
else:
    pat = re.compile(
        r"    # Windshield \+ cockpit frames:.*?poly\.use_smooth = True\n",
        re.S,
    )
    if pat.search(t):
        t = pat.sub(new_smooth, t, count=1)
        print("SMOOTH regex")
    else:
        print("WARN smooth block")

# Hide pilot seats from exterior export presence: still create but hide + black
# Replace seat link to hide_render
if 'seat_obj = link("PilotSeats"' in t:
    # After seat link, add hide
    t = t.replace(
        'seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "stripe")\n',
        'seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "stripe")\n'
        '    # ws2: seats not for exterior — hide (continuous nose; no punch cave)\n'
        '    if seat_obj:\n'
        '        seat_obj.hide_render = True\n'
        '        seat_obj.hide_viewport = True\n',
        1,
    )
    print("SEATS_HIDDEN")
else:
    print("WARN seats link")

# Also hide glare (optional interior)
if 'gs_obj = link("GlareShield"' in t and "ws2: hide glare" not in t:
    t = t.replace(
        'gs_obj = link("GlareShield", cockpit_glare_shield(), "avionics", glare_mat, "navy")\n',
        'gs_obj = link("GlareShield", cockpit_glare_shield(), "avionics", glare_mat, "navy")\n'
        '    # ws2: hide glare — exterior uses dark glass + mask only\n'
        '    if gs_obj:\n'
        '        gs_obj.hide_render = True\n'
        '        gs_obj.hide_viewport = True\n',
        1,
    )
    print("GLARE_HIDDEN")

# Ensure CockpitMask in required-name checks if any
if '"CockpitFrames"' in t and '"CockpitMask"' not in t[t.find("required"):t.find("required")+500] if "required" in t else True:
    # Add to the tuple of expected names near end if present
    t2 = t.replace(
        '        "CockpitFrames",\n',
        '        "CockpitFrames",\n        "CockpitMask",\n',
        1,
    )
    if t2 != t:
        t = t2
        print("KEYS_ADDED")

# door2 guard
start, end = t.find("def cabin_door_frames"), t.find("def cabin_door_windows")
assert not re.search(r"(?m)^\s*add_rounded_frame\(", t[start:end])

# Must not call punch (active)
assert "punch_windshield_openings(bpy.data.objects.get" not in t.replace(
    "# punch_windshield_openings(bpy.data.objects.get", ""
)

p.write_text(t, encoding="utf-8")
tt = p.read_text(encoding="utf-8")
assert "def cockpit_mask" in tt
assert "ws2: NO punch" in tt
assert "cockpit_glass_material" in tt
assert "door2e:" in tt or "never planar add_rounded_frame" in tt
print("WS2_PATCH_OK", p.stat().st_size)

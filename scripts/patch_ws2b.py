# -*- coding: utf-8 -*-
"""ws2b: separate mask/glass radii; darker glass; kill z-fight speckles."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

# Darker, less see-through cockpit glass
old = '''def cockpit_glass_material(name="CockpitGlass"):
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
'''

new = '''def cockpit_glass_material(name="CockpitGlass"):
    """ws2b: dark sunglass — shiny but mostly opaque from outside (no seat read)."""
    mat = material(name, (0.01, 0.025, 0.035), 0.02, 0.12)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.01, 0.03, 0.045, 1.0)
        for key, val in (
            ("Transmission Weight", 0.55),
            ("Transmission", 0.55),
            ("Alpha", 0.72),
            ("IOR", 1.52),
            ("Roughness", 0.025),
            ("Metallic", 0.15),
            ("Specular IOR Level", 0.75),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
'''

if "ws2b: dark sunglass" in t:
    print("GLASS already")
elif old in t:
    t = t.replace(old, new, 1)
    print("GLASS exact")
else:
    raise SystemExit("cockpit_glass_material body not found")

# Radial offsets: mask clear of skin, glass clear of mask
t = t.replace(
    "        _add_canopy_pane(bm, pane, r_off=0.0035)\n    return finish(bm)\n\n\ndef cockpit_mask():",
    "        _add_canopy_pane(bm, pane, r_off=0.012)\n    return finish(bm)\n\n\ndef cockpit_mask():",
    1,
)
# mask panes at 0.0010 -> 0.005
t = t.replace(
    "        # Slightly under glass, on skin\n        _add_canopy_pane(bm, pane, r_off=0.0010)\n",
    "        # Under glass, clear of white skin (avoid z-fight speckles)\n"
    "        _add_canopy_pane(bm, pane, r_off=0.005)\n",
    1,
)
t = t.replace(
    "    _add_canopy_pane(bm, gap_pane, r_off=0.0010)\n",
    "    _add_canopy_pane(bm, gap_pane, r_off=0.005)\n",
    1,
)
# frames above glass
t = t.replace(
    "    r_off = 0.0055  # barely proud of glass\n",
    "    r_off = 0.015  # ws2b: thin post clear of glass\n",
    1,
)
# Darker mask
t = t.replace(
    'mask_mat = material("CockpitMask", (0.04, 0.045, 0.05), 0.78, 0.02)',
    'mask_mat = material("CockpitMask", (0.025, 0.028, 0.032), 0.85, 0.0)',
    1,
)

# Larger mask expand
t = t.replace(
    "    for pane in _cockpit_pane_defs(expand=0.55):",
    "    for pane in _cockpit_pane_defs(expand=0.85):",
    1,
)

assert "ws2: NO punch" in t
start, end = t.find("def cabin_door_frames"), t.find("def cabin_door_windows")
assert not re.search(r"(?m)^\s*add_rounded_frame\(", t[start:end])

p.write_text(t, encoding="utf-8")
print("WS2B_OK", p.stat().st_size)

# -*- coding: utf-8 -*-
"""WS1c: single-sided flush frames (no tube ribbons), medium-dark glass."""
from pathlib import Path
import re

p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
t = p.read_text(encoding="utf-8")

# Replace cockpit_frames function entirely
new_frames = r'''def cockpit_frames():
    """Flush thin metallic frame ribbons — single-sided, no pipe tubes.

    ws1c: kill parallel-arc / tubular look from raised strips & curve ribbons.
    Posts and brow/sill are single-layer shells barely proud of glass.
    Center post ~1.2 deg; corner posts ~1.1 deg; hairline brow/sill.
    """
    bm = bmesh.new()
    r_off = 0.009  # glass at +0.004

    mullions = [
        (-math.radians(110.55), -math.radians(109.45), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (math.radians(109.45), math.radians(110.55), [16.88, 16.48, 16.10, 15.72, 15.48]),
        (-math.radians(49.55), -math.radians(48.45), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (math.radians(48.45), math.radians(49.55), [17.62, 17.20, 16.80, 16.45, 16.28]),
        (-math.radians(0.60), math.radians(0.60), [17.50, 17.10, 16.70, 16.35, 16.12]),
    ]
    for a0, a1, ys in mullions:
        _add_shell_sector(bm, ys, a0, a1, r_off, segs_a=2)

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

    def _flat_curve_strip(a0, a1, y_fn, half_y, n=36):
        """Single-sided strip on canopy (outer face only — no radial tube)."""
        a_list = [_lerp(a0, a1, i / float(n)) for i in range(n + 1)]
        ou, ol = [], []
        for a in a_list:
            y = y_fn(a)
            ou.append(bm.verts.new(_canopy_point(a, y + half_y, r_off)))
            ol.append(bm.verts.new(_canopy_point(a, y - half_y, r_off)))
        for i in range(n):
            bm.faces.new((ou[i], ou[i + 1], ol[i + 1], ol[i]))

    spans = [
        (-math.radians(110), -math.radians(50)),
        (-math.radians(48), -math.radians(2.8)),
        (math.radians(2.8), math.radians(48)),
        (math.radians(50), math.radians(110)),
    ]
    for a0, a1 in spans:
        _flat_curve_strip(a0, a1, sill_y, 0.0045)
        _flat_curve_strip(a0, a1, brow_y, 0.0045)

    # Very flat cheek blend (skin-like, not a raised tube)
    for sign in (-1.0, 1.0):
        ys = [16.80, 16.35, 15.90, 15.50]
        _add_shell_sector(
            bm,
            ys,
            sign * math.radians(108),
            sign * math.radians(118),
            0.002,
            segs_a=4,
        )

    return finish(bm)


'''

def replace_func(src, name, new_body):
    marker = f"def {name}("
    i = src.index(marker)
    k = src.find("\ndef ", i + len(marker))
    if k < 0:
        raise SystemExit("no next def")
    return src[:i] + new_body.rstrip() + "\n\n\n" + src[k + 1 :]

t = replace_func(t, "cockpit_frames", new_frames)

# Medium-dark glass (not near-black void)
start = t.index("    # ws1b: dark exterior glazing")
end = t.index("    # Re-assign windshield to clearer glass")
new_g = '''    # ws1c: medium-dark exterior panes (read as glass panels, not voids)
    cockpit_glass = material("CockpitGlass", (0.16, 0.18, 0.22), 0.18, 0.25)
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.12),
            ("Transmission", 0.12),
            ("Alpha", 1.0),
            ("Roughness", 0.10),
            ("IOR", 1.45),
            ("Metallic", 0.25),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.16, 0.18, 0.22, 1.0)
    try:
        cockpit_glass.blend_method = "OPAQUE"
    except Exception:
        pass
'''
t = t[:start] + new_g + "\n" + t[end:]

t = t.replace(
    'print("C919_NOTE ws1b=flush-thin-frames+dark-glass+vertical-wipers+no-punch")',
    'print("C919_NOTE ws1c=single-sided-frames+mid-dark-glass+vertical-wipers+no-punch")',
    1,
)

# Slimmer wiper hubs further
t2 = t
# reduce hub radius 0.016 -> 0.011, depth 0.010 -> 0.007
t2 = t2.replace("radius1=0.016,\n            radius2=0.016,\n            depth=0.010,",
                "radius1=0.011,\n            radius2=0.011,\n            depth=0.007,")
t2 = t2.replace("_flat_bar(p_hub, p_elbow, 0.010, 0.006)", "_flat_bar(p_hub, p_elbow, 0.007, 0.004)")
t2 = t2.replace("_flat_bar(p_elbow, p_tip, 0.009, 0.005)", "_flat_bar(p_elbow, p_tip, 0.006, 0.0035)")
t2 = t2.replace("_flat_bar(blade_lo, blade_hi, 0.014, 0.004)", "_flat_bar(blade_lo, blade_hi, 0.010, 0.003)")
t2 = t2.replace("radius=0.006)", "radius=0.0045)", 1)  # nozzle

p.write_text(t2, encoding="utf-8")
assert "def pitot_probes():" in t2
assert "_flat_curve_strip" in t2
assert "ws1c" in t2
print("ws1c patch ok")

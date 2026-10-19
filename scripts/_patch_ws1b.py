# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
t = p.read_text(encoding="utf-8")
start = t.index("    # ws1: darker exterior glazing")
end = t.index("    # Re-assign windshield to clearer glass")
new = '''    # ws1b: dark exterior glazing readable in Workbench/glTF (no punch)
    # Nearly opaque dark panes so 4-pane layout reads on white skin.
    cockpit_glass = material("CockpitGlass", (0.06, 0.08, 0.11), 0.12, 0.35)
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.18),
            ("Transmission", 0.18),
            ("Alpha", 0.92),
            ("Roughness", 0.08),
            ("IOR", 1.45),
            ("Metallic", 0.35),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.06, 0.08, 0.11, 1.0)
    try:
        cockpit_glass.blend_method = "OPAQUE"
    except Exception:
        pass
'''
t = t[:start] + new + "\n" + t[end:]
t = t.replace(
    'cockpit_metal = material("CockpitMetal", (0.72, 0.74, 0.76), 0.28, 0.85)',
    'cockpit_metal = material("CockpitMetal", (0.55, 0.57, 0.60), 0.30, 0.90)',
    1,
)
t = t.replace(
    'print("C919_NOTE ws1=flush-thin-frames+vertical-wipers+no-punch-exterior")',
    'print("C919_NOTE ws1b=flush-thin-frames+dark-glass+vertical-wipers+no-punch")',
    1,
)
p.write_text(t, encoding="utf-8")
print("patched", start, end)

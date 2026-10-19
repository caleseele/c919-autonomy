# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'cockpit_glass = material("CockpitGlass", (0.16, 0.18, 0.22), 0.18, 0.25)',
    'cockpit_glass = material("CockpitGlass", (0.07, 0.08, 0.10), 0.22, 0.15)',
    1,
)
t = t.replace(
    'bsdf.inputs["Base Color"].default_value = (0.16, 0.18, 0.22, 1.0)',
    'bsdf.inputs["Base Color"].default_value = (0.07, 0.08, 0.10, 1.0)',
    1,
)
t = t.replace(
    'cockpit_metal = material("CockpitMetal", (0.55, 0.57, 0.60), 0.30, 0.90)',
    'cockpit_metal = material("CockpitMetal", (0.28, 0.29, 0.31), 0.38, 0.70)',
    1,
)
t = t.replace(
    'print("C919_NOTE ws1c=single-sided-frames+mid-dark-glass+vertical-wipers+no-punch")',
    'print("C919_NOTE ws1d=single-sided-frames+dark-pane-contrast+vertical-wipers+no-punch")',
    1,
)
p.write_text(t, encoding="utf-8")
print("ws1d contrast ok")

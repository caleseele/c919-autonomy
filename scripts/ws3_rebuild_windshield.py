# -*- coding: utf-8 -*-
"""ws3 windshield rebuild — documentation + optional import helpers.

Production geometry lives in scripts/build_c919.py after patch_ws3.py.
This file records the REF→Soft mapping and pane names for re-runs.

REF measure (refs/sample_ref_windshield.py):
  scale 0.01, clear -30° Z, nose at Y=0, up +Z
  Soft: tip Y=19.88, soft_y = 19.88 - ref_y * (39.46/38.84)
  Side opening azimuth ~50–104° from crown

Pane objects: WS_L, WS_R, SW_L, SW_R
Seals: CockpitFrames (black, 3–6 cm)
Cabin: CockpitCabin
Removed: CockpitMask
"""
PANE_NAMES = ("WS_L", "WS_R", "SW_L", "SW_R")
SOFT_TIP_Y = 19.88
REF_LEN_M = 38.84
SOFT_LEN_M = 39.46

def soft_y_from_ref_nose_distance(d_m: float) -> float:
    return SOFT_TIP_Y - d_m * (SOFT_LEN_M / REF_LEN_M)

if __name__ == "__main__":
    print("ws3 helper only — run: blender -b -P scripts/build_c919.py")
    for d in (1.85, 2.1, 3.55, 4.5):
        print(f"  tip+{d:.2f}m -> soft_y {soft_y_from_ref_nose_distance(d):.2f}")

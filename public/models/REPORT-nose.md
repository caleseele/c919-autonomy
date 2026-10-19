# C919 nose reshape report (2026-10-16)

## Goal
Match real C919 front photo `refs/cockpit/ref-nose-front.png` (+ physical/anatomy refs):
soft blunt ogive radome (not needle, not soccer-ball), 4-pane windshield with aft-raked side panes.

## NOSE_PROFILE stations used (Y toward nose, R = circular radius)
```
(19.68, 0.40),
(19.48, 0.62),
(19.22, 0.86),
(18.90, 1.10),
(18.52, 1.32),
(18.08, 1.52),
(17.55, 1.68),
(16.95, 1.82),
(16.30, 1.93),
(15.60, 2.01),
(15.10, 2.04),
(14.85, 2.06),
```
Tip closure (`nose_with_cap`): shallow dome rings at
`y0+0.08 / 0.82·R`, `y0+0.15 / 0.62·R`, `y0+0.20 / max(0.16,0.42·R)`,
then tiny dome pole at `y0+0.20+0.35·R_last` (finite tip width — no needle pole).

## Windshield (kept attached after profile change)
- Forward panes: Y 18.05 → 16.30, azimuth ±7°…±48°
- Side panes: leading rake 17.98→17.25, trailing sweep 16.40→15.30, azimuth ±54°…±118°
- Flush mullions + continuous brow/sill; optional pitot probes on flanks

## Unchanged (no regression intended)
Cabin rounded windows/doors, flag GB-15×10, metal fans, white winglets, empennage.

## Deliverables
- `scripts/build_c919.py`
- `public/models/c919.glb` (~957 KB); backup `c919.glb.bak-nose-reshape`
- Audits: `c919-detail-nose-side.png` (true side, up=+Z), `c919-detail-windshield.png` (¾ front)
- Pixel tip check (side): white height grows ~1→32→61→91→116→138 px over 25 px from tip — blunt, not needle

## Blender
Portable 5.2.2 at `C:\Blender\blender-5.2.2-windows-x64\blender.exe`

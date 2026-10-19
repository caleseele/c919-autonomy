# C919 cockpit rebuild report (2026-10-16)

## Goal
Match real C919 / physical-model refs: **rounded radome** + **4-pane panoramic windshield** (787-family), not needle tip / jagged holes / floating shards.

## Refs used
- `refs/cockpit/ref-anatomy.png` — labeled C919, 4 large double-curved panes fused with radome
- `refs/cockpit/ref-physical.png` — physical model, smooth canopy silhouette
- `refs/cockpit/current-bad-nose.png` — prior bad: needle tip + jagged glass
- Web: ningbocat / CCTV notes on C919 四块双曲面整体风挡

## Code changes (`scripts/build_c919.py`)
| Item | Before | After |
|------|--------|-------|
| Nose tip | `(19.85, 0.02)` needle | Dense **ogive** `NOSE_PROFILE` (tip R=0.12 → R=0.82 in 0.20 units) |
| Radius helpers | Duplicated needle stations | Shared `NOSE_PROFILE` / `FUSELAGE_PROFILE` / `_radius_at_y` |
| Windshield | Uniform Y shell, small panes | `_cockpit_pane_defs`: 2 forward + 2 large side (trapezoid Y), dense grid |
| Frames | Raised pipe strips / bead belts / hatch plate | Flush thin shell mullions + continuous brow/sill ribbons |
| Subdiv | Nose subdivided (pinched tip) | **Nose skipped** in `apply_subdivision` |
| Glass mat | Lighter blue | Darker `(0.02,0.05,0.10)` metallic so panes read on white |

Unchanged: rounded cabin windows, doors, flag, fans, white winglets, empennage.

## Deliverables
- `scripts/build_c919.py` (+ box copy `/workspace/c919-work/build_c919.py`)
- `public/models/c919.glb` (~960 KB) with `c919.glb.bak` / `c919.glb.bak-nose`
- Audits: `c919-detail-windshield.png` (3/4 front), `c919-detail-nose-side.png` (side)
- Pixel check (side audit): tip white height 15→81 px over 20 px forward — **rounded**, not needle

## Compare to refs
- **Radome:** now ogive with rapid near-tip flare (same family as physical model dome), not the old needle.
- **Glass:** four canopy sectors (side L / fwd L / fwd R / side R) on the nose surface with thin center + side mullions and continuous brow/sill — silhouette closer to anatomy 4-pane wrap.
- **Leftover vs OEM photos:** glass is still an overlay (no boolean holes in skin); canopy cross-section is still circular lathe, not a custom 787-style flattened forehead. Further polish would be true skin cutouts + non-circular canopy loft.

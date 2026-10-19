# C919 nose-fix notes

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; original Nose hidden; visible body Nose_开窗

## Step1
- Body: Nose (plus Fuselage); tip +Y ~20.03
- WindowOutline: 0 in blend (floating lines were CockpitFrames / old pane edges)
- REF: Obj3d66-19714258-2-287; 15 materials Transmission=0; 011/013/017 dark but not windshield islands

## Step2 outline source
- fallback_existing_WS_SW_panes_ref_derived
- (a) REF material islands failed for 4 windshield panes; (b) WindowOutline missing
- Used existing WS_L/WS_R/SW_L/SW_R (REF soft_y derived)

## Step3
- Nose is open shell -> solidify then Exact boolean with per-pane OBB cutters (+/- 0.35m along normal)
- Complex glass prisms did not intersect; OBB boxes did
- Hole check (corrected): WS_L/R SW_L/R all OPEN; tip/cheek SOLID
- Nose_开窗 ~706 faces, boundary ~205

## Step4-6
- Glass C919_玻璃: Transmission 1, Rough 0.02, IOR 1.5, #DDEEEB, Alpha 0.3, Blended
- Seals: FAILED (0 faces) — gap
- Cabin: CockpitCabin dark grey
- Radome: soft spherical push; tip still slightly blunt
- Hidden: CockpitFrames, WindshieldWipers, PanelLines, REF
- GLB: 1778764 bytes (~1.70 MB); backup c919.glb.bak-nose-fix

## Previews
- PC: public/models/nose-fix/step{1..6}_*.png
- Box: /workspace/c919-work/previews/nose-fix/
- Logs: scripts/_nose_fix_logs/ and /workspace/c919-work/logs/

## MISSING_COUNT = 4
1. Jagged hole edges
2. Radome not perfect arc
3. Window seals not generated
4. Workbench != web glass look

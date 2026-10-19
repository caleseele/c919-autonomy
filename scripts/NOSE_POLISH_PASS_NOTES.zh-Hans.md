# C919 nose polish pass

- Time: 2026-10-17 Asia/Shanghai
- blender -b; no knife_project; body `Nose_开窗`

## Done
1. Hole-edge polish: dissolve <8mm boundary, limited dissolve 8°, loop Laplacian
2. Seals: **328 faces** from WS/SW outer-face boundaries (closed thin solids had 0 island boundary)
   - ~4 cm, inset 2 mm, BVH snap onto skin, black Roughness 0.5, flush/inward
3. Glass: single-sided outer, Transmission #DDEEEB Alpha 0.3, inset 4 mm
4. Radome: centerline sphere-map (cx=cz=0) + poke tip on +Y axis — continuous arc, not flat disk
5. Helpers hidden; GLB use_visible=True; no REF mesh merged

## Checks
- windows OPEN: 4/4
- tip_axis: SOLID; tip_y=20.448; r_min=0.0; r_mean=0.10128583928395037
- near_axis: [(0.0, 20.448, 0.0), (0.0252, 20.4463, 0.0288), (0.048, 20.4453, 0.0066), (-0.048, 20.4453, 0.0066)]
- sil: [{'y': 19.6, 'r_mean': 0.961, 'r_min': 0.789, 'n': 34}, {'y': 19.8, 'r_mean': 0.925, 'r_min': 0.812, 'n': 35}, {'y': 20.0, 'r_mean': 0.531, 'r_min': 0.434, 'n': 145}, {'y': 20.2, 'r_mean': 0.451, 'r_min': 0.382, 'n': 22}, {'y': 20.4, 'r_mean': 0.192, 'r_min': 0.142, 'n': 45}]
- boundary_edges: 205
- seal_faces=328 glass_faces=1632
- GLB: 1634604 bytes (1.56 MB)
- backup: c919.glb.bak-nose-polish / c919.blend.bak-nose-polish

## Previews
- PC: public/models/nose-fix/polish_*.png
- Box: /workspace/c919-work/previews/nose-fix/

## MISSING (0)
- none critical

## Honesty
- Window rims still have some OBB-boolean faceting (not CAD fillets).
- Seals follow pane outlines; may not hug every jagged hole edge perfectly.
- Radome is sphere-mapped from the old flat tip (better arc than a plate, not REF-perfect CAD).

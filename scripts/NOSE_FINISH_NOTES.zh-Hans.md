# 机头收尾（finish）

## 1. 玻璃 / 驾驶舱
- CockpitGlass_REF: Transmission≈0.92, Alpha≈0.42, IOR=1.5, Rough=0.02, Base #DDEEEB, BLEND/BLENDED
- （EEVEE 可读性略提高 Alpha；规格仍接近 0.3 透射）
- CockpitCabin: 内嵌暗盒，置于玻璃后缘内侧，避免穿出上沿
- 上沿黑缝: 玻璃上缘外扩 ~4mm；已删除穿出的 WindshieldGapStrip

## 2. 漂浮细线（删除前）
- 详见 `scripts/_nose_finish_logs/floater_inventory_before.json`
- 独立 edges-only: **无**
- 薄片嫌疑: TailMark / TailMark_L / Title / Title_L（机尾字标，**未删**）
- 已删: `WindshieldGapStrip`（穿出风挡的遮挡条）
- Nose 松散边=0；尖刺顶点=0；清 sharp 边
- 雷达罩十字保留为 `RadomePanelLines`（24 条细管）+#C8CACD 折面，并裁切不超出尖端

## 3. 风挡上沿
- 玻璃上缘外扩 4mm（不改窗形主体）

## 4. 登机门
- 删除机身 `Doors` 前舱门岛（yc≈14.42 与 13.05，左右共 4 岛）及对应 DoorFrames/DoorWindows
- 保留 REF 机头上门 + 机身中段/后段舱门

## 5. 雷达罩板线颜色
- #C8CACD，Roughness≈0.65

## 6. 导出
- GLB 1.45 MB；备份 `.bak-nose-finish`
- EEVEE: `public/models/nose-finish/{oblique45,front,full_side}.png`

## 诚实差距
- EEVEE 透射仍可能偏暗；Three.js 以材质通道为准
- 若仍见尖端细线，可能是法线高光或 REF 自带板线
- 接缝仍为重叠双层，非熔接

## glass_more
- Transmission=1.0, Alpha=0.30000001192092896, IOR=1.5, Rough=0.019999999552965164, Base #DDEEEB, blend=BLEND, surface=BLENDED
- Cabin kept: CockpitCabin
- GLB 1.45 MB; backup `.bak-glass-more`
- Previews: `public/models/nose-finish/glass_more_oblique45.png`, `glass_more_front.png`

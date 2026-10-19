# C919 机头重塑说明（nose3 / CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-nose3`、`public/models/c919.glb.bak-nose3`
- **范围**：仅改 `Nose` / `Windshield` / `CockpitFrames`（及机头侧空速管位置）；机身、机翼、发动机、起落架、涂装 partId 未动。

## 机头几何

- `NOSE_PROFILE` 改为椭圆站位 `(y, rx, rz)`，不再用纯圆截面。
- 尖端柔和圆钝（非针尖、非半球）；中段减弱球形鼓包，整体拉长为客机 ogive。
- 站位（最终）：
  - tip `(20.08, 0.22, 0.19)` → 逐步加宽
  - 风挡前约 `(18.00, 1.32, 1.26)`
  - 与机身接合 `(14.85, 2.06, 2.06)`（恢复圆形）
- `nose_with_cap`：尖端短帽环保持同一椭圆比；pole 浅圆钝，避免半球赤道尖点。
- `_section_at_y` / `_canopy_point`：风挡与框条沿椭圆法向浮起，贴合蒙皮。

## 驾驶舱风挡

- 仍为 C919 四块承力风挡（2 前窗 + 2 侧窗），非 A320/737 六块。
- 玻璃沿椭圆机身采样（`r_off=0.012`），分区缝约 2°，避免白蒙皮露出成“粗框”。
- 竖框 / 上眉 / 下台沿 `y(a)` 贴边；颊部薄整流。
- partId：`Windshield` / `CockpitFrames` → avionics；livery 钩子未改。

## 输出

- GLB 约 **1.09–1.15 MB**（远低于 2.5 MB）
- 预览：`c919-detail-nose-side.png`、`c919-detail-nose-front.png`、`c919-detail-windshield.png`、`c919-preview-nose-reshape.png`
- Box 副本：`/workspace/c919-work/c919-preview-nose-reshape.png`

## 已知不足

- 极尖端 lathe pole 在强光下仍可能有轻微 shading 聚点。
- 风挡为四块曲面壳，高俯视时仍略偏“贴片感”（未做 boolean 挖洞）。
- 本机 EEVEE GPU 曾崩溃，细节预览改用 Cycles CPU。

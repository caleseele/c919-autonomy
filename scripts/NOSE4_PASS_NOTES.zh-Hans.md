# C919 机头细化说明（nose4 / CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-nose4`、`public/models/c919.glb.bak-nose4`
- **范围**：仅改机头雷达罩 / 风挡框 / 前机身门窗与探针；机翼、发动机、起落架、涂装 partId 未动。

## 1. 雷达罩尖端（相对 nose3）

| | nose3 | nose4（最终） |
|---|---|---|
| 第一站 tip `(y, rx, rz)` | `(20.08, 0.22, 0.19)` | `(19.88, 0.55, 0.50)` |
| tip 相对 nose3 | — | rx/rz 约 **2.5×** |
| tip 轴向帽 | 长锥式 scale→0.24 | 短钝穹顶 scale→0.55，pole 贴近 |
| 观感 | 偏尖，像导弹锥 | 钝圆民航抛物线/椭球雷达罩 |

- 整体仍保持拉长椭圆截面（非旧版圆球鼓包）。
- 接合站仍为 `(14.85, 2.06, 2.06)`。

## 2. 雷达罩分缝

- 在 `y≈18.48` 增加一圈 **清晰的环向分缝**（`half_w=0.028`，`r_extra=0.024`），深蓝灰 `PanelLines`。
- 原 `y=15.02` 前机身分缝保留。
- 机头段环线按椭圆截面 `_section_at_y` 生成，贴合蒙皮。

## 3. 风挡（四块双曲面）

- 四块面板采样加密（`segs_a≥24`, `segs_y≥16`），玻璃 `r_off=0.010`。
- 竖框角宽收窄约 1.2°；眉条/窗台改连续 `_add_curve_ribbon`（径向厚度），减弱阶梯感。
- partId：`Windshield` / `CockpitFrames` 未改。

## 4. L1 门 / 舷窗 / 探针

- 舱门更深凹入（`x≈2.018`，厚 `0.055`），圆角加大；框条加深作密封唇示意。
- 舷窗改为有厚度的凹入玻璃 + 更深窗框 bezel（非纯贴片黑洞）。
- `PitotProbes`：空速管按椭圆蒙皮重定位；颊部增加静态口小圆盘。

## 输出

- GLB 约 **1.35–1.45 MB**（远低于 2.5 MB）
- 预览：`c919-preview-nose4.png`、`c919-detail-nose-side.png`、`c919-detail-nose-front.png`、`c919-detail-windshield.png`、`c919-detail-door-window.png`
- Box 副本：`/workspace/c919-work/c919-preview-nose4.png` 等

## 已知不足

- 静态口为示意圆盘，非真实静压孔阵列精度。
- 风挡仍为曲面壳叠加，未做 boolean 挖洞。

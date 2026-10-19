# door2 舱门修复说明

## 问题（用户截图）
翼上应急门呈厚深灰空心矩形线框、双影/倾斜、脱离机身蒙皮；附近客窗尚可。机头风挡衔接另单列（本趟未做 nose2）。

## 根因（回归，已复核）
1. **`_patch_door_bold.py` 回归**：在 door1 皮肤投影缝之后，又给 overwing 加了平面 `add_rounded_frame`（轴对齐、放在 `x=±rx`），正是飘线框/双影的来源。
2. **一度尝试凹入面板**（door2d `r_off=-0.006`）：面板埋进机身实体壳，外视只剩缝框——与 door1 笔记「凹入不可见」相同，已撤销。
3. **双圈 seal loft**（door2 初版）会被读成「双线框」，已改为单圈细缝。

## 修复（door2e，最终）
- **删除** overwing 的平面 `add_rounded_frame`；所有舱门缝仅 `_add_skin_seal_loft`（椭圆蒙皮投影）。
- 门板：`_add_skin_shell_grid`，**略凸** `r_off=+0.005`（必须在蒙皮外，否则被 Fuselage 遮挡）。
- 门缝：单圈细边 `border≈0.026–0.028`，`r_off=+0.009`，与门板尺寸对齐（填满喉口、少角隙）。
- `DoorSkin` 略加深 `(0.58,0.60,0.62)`，相对机身白可读。
- `DoorFrames` 仍为 `panel` 槽（非 navy）。
- 未改机翼/发动机/起落架/tail1；未下载 Sketchfab 网格。

## 校验
| 项 | 值 |
|---|---|
| MISSING_COUNT | **0** |
| GLB | **~1.52 MB**（1595432）≪ 2.5 MB |
| overwing FRAME_RADIAL span | **~0.0055 m**（贴皮，非平面厚框） |
| overwing DOOR_RADIAL span | **~0.0051 m** |
| 翼上净高 | sill z≈0.54 vs wing upper≈0.03 → **clearance ~0.5 m** |
| 调试色 | 绿门板 + 红门缝连续可见（`c919-debug-doors-door2.png`） |

## 预览（PC）
- `public/models/c919-preview-door2.png`
- `public/models/c919-detail-door-overwing.png`（侧视）
- `public/models/c919-detail-door-overwing-34.png`
- `public/models/c919-detail-door-l1.png`
- `public/models/c919-debug-doors-door2.png`

## 备份
- `scripts/build_c919.py.bak-door2`
- `public/models/c919.glb.bak-door2`

## 诚实缺口 / 未做
- **nose2 未做**：机头风挡台阶/俯视衔接仍待下一趟。
- 客舱窗仍为轴对齐圆角板（自带轻微「浮」影），本趟未改 Windows。
- 门缝在强侧光近景下仍可能显「框」，但是皮肤投影细 rim，不再是倾斜双线框立方体。
- 舵面/长整流等与门无关项未动。
- Sketchfab 仅作视觉参考，未装插件、未导入第三方网格。

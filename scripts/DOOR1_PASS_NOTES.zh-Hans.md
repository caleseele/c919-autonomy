# door1 舱门修复说明

## 问题
翼上应急门等呈飘在机身外的深蓝/黑线框，未贴合蒙皮，也不像塞式舱门。

## 根因（已确认）
1. **平面板**：旧 `cabin_doors` / `cabin_door_frames` 用轴对齐圆角板放在 `x=±rx`，只在赤道贴皮；门上下因圆柱曲率离开蒙皮 → 飘线框。
2. **navy 槽**：`DoorFrames` 使用 `liverySlot="navy"`，前端涂装覆成深蓝。
3. **凹入不可见**：一度把面板放在 `r_off=-0.026`（蒙皮内侧），外视只剩缝线。
4. **轮廓缺直边采样**：圆角轮廓最初只生成四角圆弧，竖边只有端点 → 竖缝退化成极细长面，再加法线朝内被剔除，看起来只剩顶边 U 形。

## 修复
- `_side_skin_point`：椭圆截面法向投影到 ±X 蒙皮（与风挡同思路）。
- 门面板：圆角足迹曲面网格，略凸出（`r_off≈0.005`），材质略深于机身白。
- 门缝：同心圆角矩形 loft（直边加密采样 + 多圈），深灰连续闭环。
- `_orient_faces_outward`：法线朝外，避免左右缝被剔除。
- 客舱门保留小舷窗；服务门/翼上应急门无窗。
- `DoorFrames` 槽位改为 `panel`。
- 彩条在门位 Y 段断开。
- `Door*` 关闭背面剔除并光滑着色。

## 未改
机翼、发动机、机头 tip（nose4）、全尾翼。未下载/拷贝 Sketchfab/CGTrader 几何。

## 校验
- `MISSING_COUNT=0`
- GLB ≈ 1.55 MB（< 2.5 MB）
- 发射材质调试：绿门缝左右连续度 ≈ 0.9+，红门板满高度
- 预览：`c919-preview-door1.png`、`c919-detail-door-overwing.png`、`c919-detail-door-l1.png`、`c919-detail-doors-side.png`

## 备份
- `scripts/build_c919.py.bak-door1`
- `public/models/c919.glb.bak-door1`

# C919 机头 + 发动机细化说明（CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-nose-engine`、`public/models/c919.glb.bak-nose-engine`
- **机头**
  - 雷达罩 ogive：`NOSE_PROFILE` 加密近尖端站点；`nose_with_cap` tip 环 3→5，尖端更圆滑
  - Nose lathe 段数：112 → **120**
  - 雷达罩分缝：在 `panel_join_lines` 增加 y≈15.02 环向板线
  - 风挡框：竖框方位角收窄；眉线/窗台略收；新增颊部整流壳带，减轻「贴片感」
  - 四块风挡布局与 partId（`Windshield`/`CockpitFrames` → avionics）未改
- **发动机（左右对称）**
  - 进气道唇口：`engine_lip_ring` 改为圆环截面圆角唇（8 段管截面），非扁圆柱切口
  - 短舱：分段 lathe（风扇机匣 / 后体分界）+ 低面数锯齿喷口提示 + 内涵道喷口 + 尖锥 spinner
  - 风扇：14 → **18** 宽弦扭转叶片，尖端半径 ≈0.96 m（直径贴近 LEAP-1C ~77 in）
  - 挂架：多截面菱形 loft + 翼根/短舱软整流鼓包，替代单盒
  - partId / 名称保留：`Engine_*` / `EngineLip_*` / `Fan_*` / `Pylon_*` → engine；liverySlot 不变
- **体积**：重建后 GLB ≈ **1.10 MB**（远低于 2.5 MB）
- **预览**：`c919-preview.png`、`c919-detail-windshield.png`、`c919-detail-fan.png`、`c919-detail-nose-side.png`、`c919-detail-engine-side.png`、`c919-detail-engine-front.png`
- **未用**：Blender MCP / Hard Ops / BoxCutter / Lux3D；退出时 Boxcutter AttributeError 可忽略

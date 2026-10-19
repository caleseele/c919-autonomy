# 驾驶舱内饰（cockpit-int）

## 废料清单（删除前）
见 `scripts/_cockpit_int_logs/scrap_inventory_before.json`（座舱区域相交物体）。

主要条目：
- `CockpitCabin`（旧暗盒）faces=6
- `CockpitGlass_REF` / `Nose` / `Fuselage` / `RadomePanelLines`（保留）
- `PilotSeats`（隐藏残留，已删）

## 已删除
- `CockpitCabin`
- `PilotSeats`

## 新增物体
- `CockpitInterior`（Nose 窗后蒙皮内翻内缩壳，#1A1C1F Rough 0.8）
- `CockpitGlareShield` / `CockpitGlareWing_L` / `CockpitGlareWing_R`
- `CockpitInstrumentPanel`
- `CockpitSeat_L_Base` / `CockpitSeat_L_Back` / `CockpitSeat_R_Base` / `CockpitSeat_R_Back`
- `CockpitSeals`（黑密封条 #0E0E0E，沿玻璃外侧面边界，约 312 面）
- `CockpitPillar_Center` / `CockpitPillar_L` / `CockpitPillar_R`（金属灰 #9A9DA1 Metal 0.6）
- `Wiper_L_Arm` / `Wiper_L_Blade` / `Wiper_R_Arm` / `Wiper_R_Blade`

## 玻璃
- Base #2E3A3E, Roughness 0.03, IOR 1.5, Transmission 1.0, Alpha 0.45, BLENDED

## 导出
- GLB ≈ 1.51 MB；备份 `.bak-cockpit-int`
- EEVEE：`public/models/cockpit-int/{front,oblique45,side}.png`
- Web：`localhost:5173` 有运行；Chrome headless 截到 `web_oblique45.png` / `web_view.png`（预设角度有限，建议用户硬刷新后点「正面/侧面」）

## 诚实差距
- 内壳/座椅/遮光罩为低模，透过玻璃可见方盒感
- 密封条基于双面玻璃外侧面边界，曲率处可能略不齐
- 雨刷为停泊姿态近似，非精确铰链运动学
- Web headless 截图不一定切到 front/side 相机预设

# C919 机身细化说明（fuse1 / CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-fuse1`、`public/models/c919.glb.bak-fuse1`
- **范围**：仅改机身几何 + 外表面细节（窗/门/分段线/侧条）；**未动** wing1 机翼/小翼/滑轨罩/翼身整流、双发+吊挂、起落架、尾翼、nose4 雷达罩尖端造型、涂装 partId / liverySlot

## 相对改前

| 项目 | 改前 | fuse1 |
|---|---|---|
| 机身截面 | 等半径圆管 lathe，中段几乎无曲率变化 | 椭圆站位 loft（微冠高 rz≥rx），中段近圆柱，前/后自然过渡 |
| 后机身 | 站位少、收径偏陡，末端偏钝 | 加密尾锥站位 + 软尖端（非平切） |
| 分段线 | 多圈粗环 + 纵向暗槽（像拼装管） | 仅保留雷达罩分缝；去掉纵向暗槽与多余舱段环 |
| 舷窗 | 不透明深色贴片 + 偏粗框 | 圆角矩形 + 薄框；`glass_material`（Transmission/Alpha）半透明玻璃 |
| 舱门 | 偏厚凸起矩形 | L1/服务/翼上应急/后客舱门；凹入门板 + 细密封唇 |
| 侧条 | `box` 凸出金属杆感 | 贴皮薄壳 `fuselage_paint_stripe`（表面涂装） |

## 保留未动（校验）

- `Wing_R` 面数 **242**（与 wing1 一致）；`Winglet_*` / `WingFairing_*` / `WingBodyFairing_*` 仍在
- `Engine_R/L` 面数 **624**；吊挂 `Pylon_*` 保留
- `Nose` tip 仍为 nose4b 钝圆站位（未改尖端）
- `Stab_*` / `VerticalTail` / `Gear_*` 未改网格生成逻辑（`fuselage_radius_at` 改为跟新蒙皮半径，避免尾根悬空）
- partId / 名称：`Fuselage` `Windows` `WindowFrames` `Doors` `DoorFrames` `DoorWindows` `Stripe_*` `PanelLines` `Flag_*` 等保留

## 输出

- GLB ≈ **1.50 MB**（`1502828` bytes，≪ 2.5 MB）
- 预览：`c919-preview-fuse1.png`、`c919-detail-fuse-side.png`、`c919-detail-fuse-top.png`、`c919-detail-windows.png`、`c919-detail-doors.png`
- Box 副本：`/workspace/c919-work/` 同名 png + 本说明
- 备份路径见上

## 校验

- `MISSING_COUNT=0`
- Soft ACAP 长度约 **39.72 m**（官方 38.90 m；未整机重标定，略长但非严重失调）
- Vite `:5173` 未杀

## 已知不足（下轮可继续抠；**未开 tail 轮**）

- 中段仍偏“长管”观感，前后曲率还可再对照三视图微调（尤其机头接合后 1–2 m）
- 舷窗玻璃在 Three.js 里 transmission 支持因浏览器/材质路径而异；若仍偏实心，可再降 Alpha 或加内侧深色舱壁
- 门框/窗框仍是独立 mesh 凹凸示意，非蒙皮 boolean 挖洞；近距离仍能看出凸缘阴影
- 客舱门精确站位未按机场规划手册逐站标定；翼上应急与 L1/服务间距可再核
- 红色 cheatline 为既有涂装色（非金色）；已改为贴皮，但未绕门断开
- 尾翼外形仍属后续 tail 轮范围

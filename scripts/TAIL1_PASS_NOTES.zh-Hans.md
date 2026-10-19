# C919 机尾细化说明（tail1 / CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-tail1`、`public/models/c919.glb.bak-tail1`
- **范围**：仅改垂尾 / 平尾 / 后机身→尾锥过渡 / 舵面浅缝 / 深灰尾锥+APU；**未动** fuse1 机身主体与门窗、nose/ws1/inside1 机头风挡、wing1 机翼、双发+吊挂、起落架、涂装 partId（TailMark/Title 仅微调位置）
- **未下载** Sketchfab / CGTrader 模型；对照商飞三面图尺寸量级 + 真机尾部照片外形

## 相对改前（平板挤出尾翼）

| 项目 | 改前 | tail1 |
|---|---|---|
| 垂尾 | 平面多边形挤出（等厚 ~0.34 m），尖端平切 | 沿高度多站翼型 loft，根厚→尖薄；尖端收成圆顶（pole） |
| 方向舵 | 粗红条偏杆感 | 贴 TE 细红涂装条 + 垂尾 TE 浅铰缝（非深槽） |
| 平尾 | 平面挤出等厚，块状/三角感 | 展向多站翼型 loft；根弦约 2.7 m→尖弦约 0.85 m；约 6° 上反；后缘浅升降舵缝 |
| 尾锥 | 白蒙皮收尖为主 | 略加密后机身站位；新增深灰 `TailCone` 金属帽 + 齐平圆形 APU 排气口 |
| APU | 方盒+锥针 | 机腹流线 scoop；尖端去掉针状突出 |

## Soft ACAP 对照（未整机重标定）

| 量 | 本模 | 官方量级 |
|---|---|---|
| 全长（鼻尖→尾尖） | ≈ **39.75 m** | 38.90 m |
| 平尾展 | ≈ **12.14 m** | 同级客机约 12 m 级 |
| 垂尾尖 Z | ≈ **8.82 m** | 总高约 11.95 m（含起落架；未改整机高度系） |

## 保留未动（校验）

- `Wing_R` 面数 **242**（wing1）；`Engine_R/L` **624**
- `Nose` / `Windshield` / `Doors` / `Fuselage` 生成逻辑未改（仅 FUSELAGE 最后若干尾锥站位略顺）
- partId：`Stab_*` `VerticalTail` `Rudder` 保留；新增 `TailCone`（`partId=tail`）
- 常规单垂尾（**非** T 尾）

## 输出

- GLB ≈ **1.6 MB**（≪ 2.5 MB）
- 预览：`c919-preview-tail1.png`、`c919-detail-tail-side.png`、`c919-detail-tail-rear.png`、`c919-detail-htail-top.png`
- Box：`/workspace/c919-work/` 同名 png + 本说明；脚本侧 `scripts/TAIL1_PASS_NOTES.zh-Hans.md`
- `MISSING_COUNT=0`（VerticalTail / Stab_* / TailCone / Fuselage / Wing / Engine / Nose / Doors 等）

## 已知不足（诚实缺口）

- 垂尾根部仍是“插入蒙皮”示意，**没有**真实长整流 fillet；后斜视交接仍偏硬
- 平尾翼根同样无专用整流罩；与机身交线仍可见
- TailMark「MU」贴花仍是平面 quad，非东航燕子矢量；侧面可能显方块贴花
- 升降舵/方向舵仅为浅几何折缝 + 红舵涂装条，非独立活动面网格
- 尾锥深灰段与白蒙皮分界仍偏“套壳”，非完整面板分缝系统
- Soft 全长仍略长于 ACAP（同 fuse1）；本轮未整机缩放到 38.90 m

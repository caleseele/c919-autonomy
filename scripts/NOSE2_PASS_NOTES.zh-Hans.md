# nose2 机头/风挡衔接说明

## 问题（用户俯视截图）
风挡相对雷达罩呈台阶/陡接；俯视轮廓偏硬；椭圆站位不够连续。要求保留 inside1 透视座舱（细框、开孔、座椅可见），禁止粗管框与整腔掏空。

## 未动
- **door2** 蒙皮舱门/细缝（无平面 `add_rounded_frame`）
- 机翼、发动机、起落架、tail1
- 未导入 Sketchfab 网格；nose4 tip `(19.88, 0.55, 0.50)` 未削尖

## 改动（nose2 → nose2d）

### 1. 站位加密（NOSE_PROFILE）
风挡带 y≈15.3–18.4 加密椭圆站，平滑 rx/rz 过渡到机身接合 `14.85/2.06`。

### 2. 风挡 Y 曲线（俯视轮廓）
- 前缘改为 **中心略前、脸颊略后**（smoothstep），去掉旧「外侧更靠前」造成的俯视台阶感。
- `cockpit_frames` 的 sill/brow 与窗格曲线对齐。
- 脸颊 blend 加长加宽。

### 3. 玻璃/框落座
- 玻璃 `r_off≈0.004`（更贴皮，减少下沉台阶）
- 细金属框 `r_off≈0.008`（仍非 pipe）
- 雷达罩分缝环改为发丝级 `(18.48, 0.008, 0.005)`

### 4. 开孔盖边（nose2d，针对俯视锯齿）
- 删除区（kill）与盖边（cover）分 inset：cover 更靠近窗格外缘，用不透明 rim **盖住** lathe 删面遗留的锯齿边界（透过玻璃可见的楼梯边）。
- 法兰更浅；边界 dissolve 阈值加大。
- 仍为 **周圈法兰**（非实心径向板），座椅可见。

### 5. 冠部 fairing
sill 前 / brow 后各加一条冠部壳带（避开玻璃 Y 带，防 z-fight）。

## 校验
| 项 | 值 |
|---|---|
| MISSING_COUNT | **0** |
| GLB | **~1.61 MB**（1692148）≪ 2.5 MB |
| punched_ws_faces | ~322（perimeter-flange） |
| door2 planar frame | **无** |

## 预览
- `public/models/c919-preview-nose2.png`
- `public/models/c919-detail-nose-top.png`（俯视，对标用户失败模式）
- `public/models/c919-detail-windshield-34.png`
- `public/models/c919-detail-nose-side.png`

## 备份
- `scripts/build_c919.py.bak-nose2`
- `public/models/c919.glb.bak-nose2`

## 诚实缺口
- 程序化「开孔+贴玻璃」仍无法达到 CAD 级无缝整流；近景仍可能看到轻微 rim/色差。
- 风挡本身是分段双曲壳，不是整块吹塑罩——俯视不会像光滑球体。
- 客舱窗仍为轴对齐板（非本趟范围）。
- 座舱内部仍为示意座椅/遮光罩，非航电细节。

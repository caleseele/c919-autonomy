# C919 机翼细化说明（wing1 / CLI 脚本）

- **备份**：`scripts/build_c919.py.bak-wing1`、`public/models/c919.glb.bak-wing1`
- **范围**：仅改主翼 / 翼身整流 / 翼尖小翼 / 襟翼滑轨整流罩 / 前缘细条；机身、机头、驾驶舱、发动机、起落架、尾翼、涂装 partId **未动**。

## 相对改前（扁平挤出翼）

| 项目 | 改前 | wing1 |
|---|---|---|
| 主翼 | 平面多边形挤出（约 0.28 厚），三角形感强 | 沿展向多站 loft 超临界示意翼型，根厚→尖薄 |
| 平面外形 | 少点折线，偏三角 | 11 站：宽翼根、渐收、后缘约 1/3 半展有 kink |
| 翼尖小翼 | 挤出折角片 | 自翼尖连续上翘的 blended loft（白蒙皮） |
| 滑轨整流 | `create_cube` 方柱/短杆 | 每侧 4 个细长独木舟形（尖头尖尾，贴后缘下） |
| 翼身整流 | 多个 UV 球 blob | 椭圆截面沿机身 Y 向 loft 的柔和鼓包 |

## 保留未动

- `Engine_*` / `Pylon_*` 位置与 partId（发动机仍在翼下 x≈±6.2）
- `Wing_*` / `Winglet_*` / `WingFairing_*` / `WingLE_*` / `WingBodyFairing_*` 命名与 `partId=wing`
- `pose_wing` 仍为 5°（绕 Y）+ `(0, 0.2, -0.35)`，与吊挂对齐
- 整机尺度未重标定（翼尖约 x≈16.0，全翼展量级仍贴近 ~35.8 m）

## 输出

- GLB ≈ **1.39 MB**（`1452332` bytes，远低于 2.5 MB）
- 预览：`c919-preview-wing1.png`、`c919-detail-wing-top.png`、`c919-detail-wing-side.png`、`c919-detail-winglet.png`、`c919-detail-flaptrack.png`
- Box 副本：`/workspace/c919-work/` 同名 png + 本说明

## 校验

- `MISSING_COUNT=0`（Wing / Winglet / Fairing / Engine / Fuselage / Nose 等）
- Wing_R 面数约 242（loft）；WingFairing_R 约 480（4×canoe）

## 已知不足（下轮可继续抠）

- 翼身整流仍是示意 loft，未与机身做 boolean 挖合，俯视交接处仍可能略生硬
- 独木舟为简化纺锤体，非真实 C919 分段滑轨罩外形；俯视仍显细线
- 翼尖小翼顶端后缘仍略棱角；高度/外倾可再对照三视图微调
- 仅有轻微后缘铰缝示意，无完整襟翼/副翼分缝面板
- `pose_wing` 继承旧号（右侧翼尖略下压），未改成真实上反角，以免吊挂错位

# C919 机头 REF 对照重做说明（nose-ref）

- **时间**：2026-10-17（Asia/Shanghai）
- **备份**：`scripts/build_c919.py.bak-nose-ref`、`public/models/c919.glb.bak-nose-ref`
- **约束**：未合并 REF 网格进量产 GLB；仅用 REF 比例/轮廓驱动参数化曲线。未恢复 face-delete / boolean 锯齿开洞；未恢复不透明 CockpitMask。玻璃仍为 flush Transmission 贴壳 + 细密封条。

## Goal A — 米制清理 FBX

| 项 | 值 |
|---|---|
| 源 | `refs/REF_C919.fbx`（cm，~4.4 MB） |
| 产出 | `refs/REF_C919_meters.fbx` |
| 桌面副本 | `C:\Users\希儿\Desktop\REF_C919_meters.fbx` |
| 大小 | ~4.93 MB（4931084） |
| 长度 | **38.837 m**（目标 ≈38.8） |
| 翼展 | **35.693 m**（目标 ≈35.7） |
| 高度 | **12.134 m**（目标 ≈12.1） |
| 处理 | 删 helper `…-1-818` + Cube；保留主网格；`scale=0.01` 并 Apply；旋转清零；原点移到包围盒中心 XY、肚皮 Z=0；机头 −Y |

校验 JSON：`refs/REF_C919_meters_verify.json`  
截面采样：`refs/REF_nose_sections.json`（REF tip→cabin droop ≈0.56 m）

## Goal B — 程序化机头贴 REF 剪影

### 改动（`scripts/build_c919.py`）

1. **`NOSE_PROFILE`**：按 REF 米制截面重采样锥度（尖端更瘦、向接合站更顺），站位带第 4 元 **`z_off` 下垂**（尖端 −0.42 m → 接合 0；略轻于 REF 0.56 m，避免过猛）。
2. **`nose_with_cap`**：支持 `(y,rx,rz,z_off)`；钝穹顶 tip_spec 略收，pole 跟 z_off。
3. **`_section_full_at_y` / `_canopy_point` / 座舱内壳**：玻璃、框、内壳跟随下垂，避免浮空。
4. **风挡带**：前缘推到 ≈17.85，前窗 Y 变长；侧窗角域约 52–100°；sill/brow/立柱 Y 同步。仍禁止 punch；开洞仍靠 ws4 knife（GUI）。

### 未改

- door2 / 翼 / 发 / 起落架 / 尾 / 涂装 partId
- 未 import Sketchfab / 未把 REF 面并入 GLB

### 校验

| 项 | 值 |
|---|---|
| MISSING_COUNT | **0** |
| GLB | **~1.61 MB**（1613144）≪ 2.5 MB |
| tip_y / tip_z / droop | 20.03 / −0.42 / **0.42 m** |

### 预览

- `public/models/c919-preview-nose-ref.png`
- `public/models/c919-detail-nose-side.png`
- `public/models/c919-detail-nose-front.png`
- `public/models/c919-detail-nose-top.png`
- `public/models/c919-detail-windshield.png`

## 诚实缺口

1. **前风挡开洞**仍依赖 ws4 knife GUI；本趟只重建蒙皮比例 + flush 玻璃壳，未重跑 knife（`-b` 会崩）。前窗透视仍可能弱于侧窗。
2. 下垂取 0.42 m（REF≈0.56 m）——侧视更像，但未 1:1 复刻；再加大需重校起落架/探针高度。
3. 尖端 rx=0.40（REF≈0.28）——有意偏钝，避免回到「导弹头」。
4. REF 风挡边界环 soft_y≈14.5–15.3 与暗材质带≈18.6 不一致；本趟用折中前缘 ≈17.85。若要更贴边界环，需再后移整带。
5. 风挡仍是分段双曲壳，不是 CAD 级吹塑罩。

## 脚本

- `scripts/_export_ref_meters.py` — Goal A
- `scripts/_patch_nose_ref.py` / `_patch_cabin_z.py` — 补丁
- `scripts/render_nose_ref.py` — 预览

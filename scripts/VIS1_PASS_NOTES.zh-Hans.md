# VIS1 通过笔记（过翼门 / 雨刮 / 驾驶舱内视）

时间：2026-10-16 约 22:10 CST（Asia/Shanghai）

## 本轮目标
A. 过翼应急门抬到机翼上表面之上，侧视/3/4 可见  
B. 风挡两根雨刮（停放位）  
C. 透过透明风挡能隐约看到双座椅 + 遮光罩  
约束：不下载/拷贝 Sketchfab·CGTrader 网格；保留 nose4 / wing1 / 涂装 partId；GLB << 2.5 MB

## 做了什么
1. **过翼门** `_door_specs`：`(1.80, 0.95, 0.56, 0.88, …, "overwing")`  
   - 门底边世界 Z ≈ 0.555，机翼上表近根 Z ≈ 0.025 → **净空 ≈ 0.53 m**  
   - 窗带/彩条门隙同步改为约 `(1.25, 2.35)` / `(1.35, 2.25)`  
   - 过翼门密封加厚 + `add_rounded_frame` 粗边框，便于读出轮廓  
2. **雨刮** `windshield_wipers()`：左右各 1 组 hub + arm + blade，深色材质，停放近中立柱  
3. **驾驶舱内视**  
   - `cockpit_glare_shield()` + `cockpit_pilot_seats()`（红色块状座椅，头枕抬到 Z≈1.18，高出遮光罩）  
   - `punch_windshield_openings()`：从 Nose 删除风挡四扇下蒙皮（约 222 面），否则玻璃贴在实心机头上看不到内部  
   - 风挡改用更透的 `CockpitGlass`（α≈0.32 / transmission≈0.82）  
4. **备份**：`scripts/build_c919.py.bak-vis1`、`public/models/c919.glb.bak-vis1`  
5. **未**安装 Sketchfab For Blender，**未**导入任何第三方机模

## 产物
| 文件 | 说明 |
|------|------|
| `public/models/c919.glb` | ≈ **1.55 MB**（1553184 B） |
| `public/models/c919.blend` | 同源 |
| `c919-preview-vis1.png` 等 | 预览在 `public/models/` 与 box `/workspace/c919-work/` |

## 成功项核对
| 项 | 状态 |
|----|------|
| 过翼门几何高于机翼上表 | **通过**（净空 0.53 m） |
| 两根雨刮可见 | **通过** |
| 座椅透过开洞风挡可见 | **通过**（块状，头枕清晰） |
| 无第三方模型导入 | **通过** |
| GLB < 2.5 MB | **通过**（1.55 MB） |

## 仍缺 / 未做漂亮（诚实）
**MISSING_COUNT = 5**（本轮观感缺口，非整机重做）

1. **过翼门在「机翼挡前景」的 3/4 低机位**仍易被机翼面挡住视线——几何已抬高，但透视遮挡仍在；边框对比在 clay 预览里仍偏弱。  
2. **风挡开洞边缘**略不齐（一侧窗洞偏黑），还需收边/补框。  
3. **雨刮**仍偏细针状，未到「粗臂+宽叶片」量感。  
4. **座椅**仅为红块占位，无安全带/侧操纵台。  
5. **Three.js** 端玻璃 transmission 观感依赖前端材质；Workbench 预览不能代表网页透明度。

## 未动
机头 tip（nose4）、翼平面/发动机/起落架/尾翼（除过翼门相关窗隙）、涂装 partId。未做机尾专项。

## 回退
复制 `.bak-vis1` 覆盖 `build_c919.py` / `c919.glb` 后重跑 Blender 即可。

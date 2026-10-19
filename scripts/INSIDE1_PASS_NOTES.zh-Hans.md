# INSIDE1 通道纪要（透过风挡看驾驶舱 / 无 VIS1 空腔感）

时间：2026-10-16 约 23:05 CST（Asia/Shanghai）

## 本轮目标
恢复透过四块风挡看到 PilotSeats / GlareShield，同时保持 WS1 细贴皮边框与细雨刮，避免 VIS1 那种锯齿大开洞空腔感。
约束：不下载第三方网格；不动机翼/机尾/发动机/nose4 tip；GLB << 2.5 MB。

## 改了什么
1. **punch_windshield_openings()**（inside1b）
   - 重新启用删面开洞，但角向/纵向内缩（A_INSET≈1.05°、Y_INSET≈0.045 m），让 WS1 细边框盖住洞缘
   - 删孤儿顶点、溶解过短边界边
   - **仅周缘内翻边**（深约 0.028 m），不再铺满整窗径向板（inside1 初版误铺满挡住座椅，已修正）
2. **CockpitGlass**：Alpha≈0.28、Transmission Weight≈0.86、blend=BLEND（glTF/Three.js 可透）
3. **玻璃 r_off**：0.004 → 0.006，略外凸盖住翻边外唇
4. **座椅/遮光罩**：整体前移并略抬高头枕，遮光罩略降，便于正视透过风挡看见红色座椅轮廓
5. **保留**：WS1 单层细边框、细雨刮、nose4 tip、机翼/门/发动机/尾

## 备份
- `scripts/build_c919.py.bak-inside1`
- `public/models/c919.glb.bak-inside1`

## 产物
| 文件 | 说明 |
|------|------|
| `public/models/c919.glb` | 约 **1.51 MB**（1580784 B） |
| `public/models/c919.blend` | 同源 |
| `c919-preview-inside1.png` | 总览（EEVEE，带玻璃） |
| `c919-detail-windshield-front.png` | 风挡正面 |
| `c919-detail-windshield-side.png` | 侧面/3/4 |
| `c919-detail-cockpit-interior.png` | 隐藏玻璃俯视，确认座椅可见 |

## 成功核对
| 项 | 状态 |
|----|------|
| Nose / Windshield / CockpitFrames / Wipers / GlareShield / PilotSeats | **MISSING_COUNT = 0** |
| 开洞面数 | **178**（inset） |
| 隐藏玻璃后正视/俯视可见座椅头枕 | **通过** |
| 外边框仍为 WS1 细贴皮（无管状 ribbon） | **通过** |
| 未导入 Sketchfab | **通过** |
| GLB << 2.5 MB | **通过**（≈1.51 MB） |

## 仍缺 / 诚实差距
1. **Workbench 粘土预览里玻璃常显实心灰**；透光度主要依赖 EEVEE / 前端 Three.js 的 transmission+alpha。
2. 周缘翻边与蒙皮同色，极近看 rim 仍偏浅；未单独做深色密封胶条材质。
3. 正视低机位时遮光罩仍占画面中部，座椅多为头枕/靠背上沿，不是完整座舱透视。
4. 开洞仍是程序化删面，边界在无边框遮挡角度可能有轻微折感。
5. 座椅/仪表仍是低模示意，非 Sketchfab 高模。

## 回退
恢复 `.bak-inside1` 的 `build_c919.py` / `c919.glb` 后重跑 Blender。
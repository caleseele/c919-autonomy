# COCKPIT3 通道纪要（驾驶舱细化）

时间：2026-10-16 约 22:26 CST（Asia/Shanghai）

## 本轮目标
加深驾驶舱可视细节（雨刮 / 座椅 / 遮光罩仪表台 / 风挡开洞），对照 Sketchfab 风格截图仅作外形参考，**不下载、不导入** Sketchfab 模型，不装 Sketchfab For Blender 插件。

## 改了什么
1. **雨刮** `windshield_wipers()`  
   - 加粗 hub（R≈0.055）+ 短臂 + 金属槽形刮片 + 橡胶唇 + 端帽  
   - 底座垫板；刮片停在风挡下沿/门槛附近；每侧 1 个洗涤喷嘴  
2. **座椅** `cockpit_pilot_seats()`  
   - 座垫/前唇、后仰靠背、腰托、头枕侧翼、扶手  
   - 底座 + 前后导轨，减少「红箱子」感  
3. **遮光罩/仪表台** `cockpit_glare_shield()`  
   - 倾斜眉板 + 前唇 + 侧颊  
   - 仪表架上 4 块深色显示矩形；中央操纵台占位  
4. **风挡开洞** `punch_windshield_openings()`  
   - 开洞略扩到立框/眉/门槛下，锯齿边藏进边框  
   - 删孤儿顶点、溶解过短边界边；本轮约 **230** 面  
5. **边框** `cockpit_frames()`：立框略加宽并加径向厚度，眉/门槛 ribbon 加厚  
6. **玻璃** `CockpitGlass`：Alpha≈0.26 / Transmission≈0.88，更易透过看座椅  

## 备份
- `scripts/build_c919.py.bak-cockpit3`
- `public/models/c919.glb.bak-cockpit3`

## 产物
| 文件 | 说明 |
|------|------|
| `public/models/c919.glb` | 约 **1.50 MB**（1572152 B） |
| `public/models/c919.blend` | 同源 |
| `c919-preview-cockpit3.png` | 总览 |
| `c919-detail-wipers.png` | 雨刮特写 |
| `c919-detail-cockpit-interior.png` | 座椅/仪表台（渲染时隐藏风挡） |
| `c919-detail-windshield.png` | 风挡/边框 |

## 成功核对
| 项 | 状态 |
|----|------|
| Nose / Windshield / Wipers / CockpitFrames / GlareShield / PilotSeats 均存在 | **MISSING_COUNT = 0** |
| 雨刮更粗、左右成对可读 | **通过** |
| 座椅有垫/背/头枕/导轨轮廓 | **通过**（仍是低模示意） |
| 遮光罩有仪表矩形 | **通过** |
| 开洞边更干净（被边框盖住） | **通过**（Workbench 近似） |
| 未改机尾专改；未下载 Sketchfab | **通过** |
| GLB << 2.5 MB | **通过**（1.50 MB） |

## 仍缺 / 诚实差距
1. 座椅仍是多块方体拼装，非曲面航空座椅；无安全带/五金。  
2. 仪表仅为深色矩形，不是真实 PFD/ND。  
3. 雨刮无铰链动画，停放姿态近似。  
4. 风挡开洞是删面，极近看仍可能有轻微锯齿。  
5. Three.js 端 transmission/alpha 观感取决于前端材质管线；Workbench 预览偏实色。  
6. 未做完整驾驶舱侧壁/顶棚/遮阳板。

## 未动
机头 tip（nose4）、机翼、机身门窗位置、发动机、机尾专改、涂装 partId、过翼门高度（VIS1）。

## 回退
恢复 `.bak-cockpit3` 的 `build_c919.py` / `c919.glb` 后重跑 Blender 生成。


# WS1 通道纪要（风挡外框 / 机鼻衔接 / 雨刮 / 外观白模）

时间：2026-10-16 约 22:50 CST（Asia/Shanghai）

## 本轮目标
按真机座舱特写（忽略人员）改进外观白模：细贴皮边框、连续机鼻-顶盖、清晰四窗格、细雨刮竖直停靠、消除 VIS1 开洞造成的空腔感。
约束：不下载第三方网格；不动机翼/尾/发动机；保留 partId；GLB << 2.5 MB。

## 改了什么
1. **cockpit_frames()**（ws1c）
   - 去掉 shell+raised_strip 双层与 _add_curve_ribbon 空心管状剖面（并行弧边/管子感来源）
   - 改为单层贴皮壳：中立柱约 1.2°、角柱约 1.1°、眉/门槛半宽约 0.0045 m
   - 银色改深灰金属 CockpitMetal，白模对比更清晰
2. **punch_windshield_openings()** — **跳过删面**（方案 a）
   - Nose 蒙皮保持连续；深色玻璃叠在蒙皮上，消除锯齿空腔/断面
   - 座椅仍在文件内，但外观优先下透过实心蒙皮不可见
3. **cockpit_windshield()** — 四窗格略凹入（r_off=0.004）；深色不透明风挡材质便于白模读出分区
4. **windshield_wipers()** — 低矮圆盘 hub（非球体）、扁平细臂沿中立柱竖直停靠、肘关节、去掉粗端帽/大球喷嘴
5. **未改** tip 钝圆（nose4）、机翼、机尾、发动机、涂装 partId

## 备份
- scripts/build_c919.py.bak-ws1
- public/models/c919.glb.bak-ws1

## 产物
| 文件 | 说明 |
|------|------|
| public/models/c919.glb | 约 **1.49 MB** |
| public/models/c919.blend | 同源 |
| c919-preview-ws1.png | 总览 |
| c919-detail-windshield-front.png | 风挡正面 |
| c919-detail-windshield-side.png | 侧面/3/4 |
| c919-detail-wipers.png | 雨刮特写 |

## 成功核对
| 项 | 状态 |
|----|------|
| Nose / Windshield / Wipers / CockpitFrames 存在 | **MISSING_COUNT = 0** |
| 开洞面数 = 0（无空腔删面） | **通过** |
| 边框单层贴皮（无 curve_ribbon 管） | **通过** |
| 四窗格布局保留 | **通过** |
| 雨刮 Y 向沿中柱停靠 | **通过**（审计 Y≈16.6–17.6） |
| tip 钝圆未改尖 | **通过** |
| GLB << 2.5 MB | **通过**（约 1.49 MB） |
| 未导入第三方模型 | **通过** |

## 仍缺 / 诚实差距
1. 无单独「密封胶条」材质层（白模阶段用细边框代替）；真机铆钉未做。
2. 跳过 punch 后，透过风挡看不到座椅/仪表；若要内视需另做干净 Boolean 开洞。
3. Workbench 预览材质对比有限；Three.js 端观感取决于前端材质。
4. 机鼻顶盖与风挡交界仍是程序化站位曲面，极近看可能有轻微环缝/折感。
5. 雨刮无铰链五金精细件；洗涤喷嘴仅为极小点。
6. 风挡深色块在白模上可读，但还不是真机镀膜虹彩玻璃。

## 回退
恢复 .bak-ws1 的 uild_c919.py / c919.glb 后重跑 Blender。

# ws3 风挡（透明四窗）说明

## 用户要求
去掉深灰 CockpitMask；玻璃必须透明；轮廓对齐 REF_C919.fbx；透过玻璃能看到舱内；不要大型面罩。

## REF 采样（只测量，不拷网格）
- 文件：`refs/REF_C919.fbx`；脚本：`refs/sample_ref_windshield.py` → `refs/REF_WS_SILHOUETTE.json`
- 导入：`global_scale=1` 后物体缩放 **0.01**，清除约 −30° Z，机头挪到 Y=0；主网格 `Obj3d66-19714258-2-287`；helper / Cube 忽略
- Soft 映射：`soft_y = 19.88 − ref_y_from_nose × (39.46 / 38.84)`（Soft 尖≈19.88，REF 长≈38.84 m）
- **侧窗开孔**边界环方位角约 **50°–104°**（冠顶 a=0）→ Soft 侧窗 `a∈[49°,105°]`
- 深色 V-Ray 材质带混有机鼻涂装，**不用**其 Y 极值当玻璃；正面 sill/brow 落在雷达罩后 Soft **≈17.55 / 16.2**（不上机顶）

## 本趟做法
1. **删除 CockpitMask**（不再 link；函数留空壳防旧调用）
2. **四独立玻璃**：`WS_L` `WS_R` `SW_L` `SW_R`，双壳厚约 1.6 cm，齐平（外 +6 mm / 内 −10 mm）
3. **材质**：`CockpitGlass` `#DDEEEB`，Transmission Weight=**1.0**，Roughness≈0.02，IOR=1.5，Alpha≈0.18，`blend_method=HASHED`
4. **密封框**：`CockpitFrames` 仅约 4 cm 黑条 + 窄中柱/角柱/侧后柱
5. **开洞**：`punch_windshield_openings` 重新启用（inset 删面 + 翻边，**非 Boolean**）；本趟删面 **340**
6. **舱内**：`CockpitCabin` 深色筒壳 + 简易仪表台；`GlareShield` 可见；座椅改深灰（非红）
7. **door2 / 翼 / 发 / 尾**未改；未导入 Sketchfab / REF 网格进量产

## 校验
| 项 | 值 |
|---|---|
| MISSING_COUNT | **0** |
| CockpitMask | **absent** |
| Transmission | **1.0** |
| GLB | **1 695 444 ≈ 1.62 MB** ≪ 2.5 MB |
| 开洞面 | 340 |
| 备份 | `build_c919.py.bak-ws3` / `c919.glb.bak-ws3` |

## 预览
- `c919-detail-windshield-34.png` — 45° 可透视到深色舱内
- `c919-detail-windshield-side.png`
- `c919-detail-nose-top.png`
- `c919-preview-ws3.png`
- 盒内副本：`/workspace/c919-work/`

## 诚实缺口
1. 部分角度（侧视掠射）Cycles 下近侧窗格可能几乎看不见（薄壳 + HASHED），远侧开洞更醒目——Three.js 端观感取决于 transmission/alpha 实现。
2. 开洞边缘仍是低模 lathe 台阶；有翻边遮挡，但极近看可能仍有轻微锯齿。
3. REF 深色材质未能干净拆出四块玻璃网格；正面 Y 带靠雷达罩比例 + 侧孔方位角约束，非逐厘米贴合高模顶点。
4. 雨刮仍沿旧 sill 站位，未按新窗格重标定。
5. 全机截面仍非严格 3.96×4.166 椭圆重比例。

# ws2 风挡（墨镜罩）说明

## 用户拒收原因
挖洞风挡：锯齿 boolean 边、厚车门框唇、红座椅从空洞清晰可见，不像 C919 四窗格墨镜罩。

## 本趟做法
1. **关闭挖洞**：不再调用 `punch_windshield_openings`；Nose 风挡带冠顶蒙皮连续（审计 `NOSE_CROWN_VERTS_IN_WS_BELT≈219`）。
2. **CockpitMask**：深灰哑光面罩，面积大于玻璃（`expand≈0.85`），贴皮 `r_off≈0.005`。
3. **Windshield**：四窗格（2 前 + 2 侧颊，窄中缝），侧窗后掠；玻璃 `r_off≈0.012`，深色 `CockpitGlass`（高反射、Alpha≈0.72，外视不读座椅）。
4. **CockpitFrames**：仅细中柱 + 角柱（约 20 面），无粗唇。
5. **PilotSeats / GlareShield**：隐藏并从 GLB 导出中删除。
6. **door2 保留**：舱门仍为蒙皮 loft，无平面 `add_rounded_frame`。

## 未改
机翼 / 发动机 / 起落架 / tail1；未导入 Sketchfab。

## 校验
| 项 | 值 |
|---|---|
| MISSING_COUNT | **0**（含 CockpitMask） |
| GLB | **~1.56 MB（1636568）** ≪ 2.5 MB |
| punch | **disabled** |
| 挖洞审计 | 冠顶蒙皮顶点仍在风挡 Y 带 |
| 失败角渲染红像素 | **0**（无红座椅外泄） |

## 预览
- `c919-preview-ws2.png`
- `c919-detail-windshield-34.png`（用户失败角）
- `c919-detail-windshield-side.png`
- `c919-detail-nose-top.png`

## 备份
- `scripts/build_c919.py.bak-ws2`
- `public/models/c919.glb.bak-ws2`
- 指南：`scripts/C919_NOSE_WINDSHIELD_GUIDE.zh-Hans.md`

## 诚实缺口
- 低模分段仍可能在强光下显出玻璃/面罩边缘锯齿感（非挖洞，是网格分辨率）。
- 全机 ACAP 椭圆 3.96×4.166 m 未做整体重比例；仅风挡造型按 brief。
- Three.js 里深色玻璃观感依赖引擎对 transmission/alpha 的支持。

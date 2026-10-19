# ws4 风挡（Knife Project）

## 结论摘要
- **`bpy.ops.mesh.knife_project` 在 GUI 下已跑通**（RIGHT 侧窗 + FRONT 前窗）。
- **`--background` / `-b` 会 ACCESS_VIOLATION**，禁止用于 knife 步。
- 连续蒙皮重建（已禁用 `punch_windshield_openings`）。
- **MISSING_COUNT = 0**；**GLB ≈ 1.46 MB**（1 534 476）≪ 2.5 MB。
- CockpitMask 已去除；door2 / 翼 / 发 / 尾未改；未导入 Sketchfab 网格。

## 硬约束执行情况
| 约束 | 状态 |
|---|---|
| 主切割用 knife_project | ✅ GUI 调用成功 |
| 侧窗 RIGHT 视图 | ✅ |
| 前风挡 FRONT 视图 | ✅ 算子成功；见缺口 |
| 禁止 Boolean | ✅ |
| 禁止以角度带删面作主切割 | ✅ 仅在刀线后删轮廓内面 |

## 流程
1. `blender -b -P scripts/build_c919.py` → 连续 Nose（无 punch）
2. `blender --factory-startup --python scripts/ws4_knife_project_windshield.py`（**无 -b**）
   - 建 `WindowOutline_Side`（YZ）+ `WindowOutline_Front`（XZ），父级空物体名 `窗户轮廓`
   - RIGHT → knife_project(cut_through=True)
   - FRONT → knife_project(cut_through=True)
   - 仅删窄带（Z≈0.58–1.18）轮廓内面
   - 侧窗可从洞边界建玻璃；前窗若无闭环则程序化补 `WS_L/WS_R`
   - 边界内挤 ~4 cm 黑密封条 + 深色 `CockpitCabin`
   - 导出 GLB + 预览

## REF 轮廓
FBX 无独立「REF_玻璃」。侧窗方位/高度带参考审计与 Soft 窄带：同高度、前后排布（非冠顶上下叠）。轮廓在 Soft 坐标生成（测量映射，不拷网格）。

## CLI / 上下文
- Timer 0.5s 后执行（等 VIEW3D）。
- `temp_override(window, area, region, active_object=Nose)`。
- glTF 导出前需恢复 active_object（timer 上下文否则缺属性）。

## 本趟实测日志要点
- `knife ok RIGHT` / `knife ok FRONT`
- `deleted_interior_faces 18`（主要为侧窗）
- `hole_loops 2`（SW_L / SW_R）；前窗闭环未稳定形成 → 程序化补前玻璃
- MISSING_COUNT 0

## 诚实缺口
1. **前窗开洞不稳定**：FRONT knife 算子成功，但弯曲机头上 XZ 投影与删面过滤器未稳定得到前窗闭环（仅 2 个侧洞环）。前玻璃目前多为程序化贴皮，透视效果弱于侧窗。
2. **边缘仍受 lathe 分辨率限制**：刀线后边界比纯角度删面干净，但低模下仍可能有折感。
3. 密封条为边界边挤出条带，非完美圈梁。
4. 需 GUI；无法纯 `-b` 一键。

## 备份 / 文档
- `scripts/build_c919.py.bak-ws4`、`public/models/c919.glb.bak-ws4`
- `scripts/C919_KNIFE_PROJECT_WINDSHIELD.zh-Hans.md`（用户方法）
- `scripts/ws4_knife_project_windshield.py`、`scripts/run_ws4.ps1`

## 预览
`c919-detail-windshield-34.png` / `…-side.png` / `c919-detail-nose-top.png` / `c919-preview-ws4.png`  
盒内：`/workspace/c919-work/`

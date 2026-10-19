# C919 风挡开洞方法：Knife Project（用户指定流程）

> 禁止：在细分曲面上用 Boolean 开窗；禁止以「按角度带选面删除」作为主切割手段。  
> 必须：用「窗户轮廓」物体 + `bpy.ops.mesh.knife_project()`。

## 适用版本
Blender 5.2.x（本工程验证）。**不要**加 `-b/--background` 跑 knife 步——后台会崩或无有效投影；需带 VIEW3D 的 GUI 启动。

## 步骤 0 — 恢复无洞蒙皮
机身/Nose 必须是**开洞前**的连续蒙皮（ws2 连续皮或关闭 `punch_windshield_openings` 后重导）。删掉 `CockpitMask`。

## 步骤 1 — 从 REF 得到「窗户轮廓」
1. 导入 `refs/REF_C919.fbx`，Scale **0.01**，机头 −Y，上 +Z；只用主网格 `Obj3d66-19714258-2-287`。
2. 在机头上半、风挡高度带选出四块玻璃区域（材质/区域），复制。
3. 进入编辑模式 → **Select Boundary Loop** → 删内部面，只留轮廓边/面环。
4. 物体命名 **`窗户轮廓`**（或拆成 `窗户轮廓_前` / `窗户轮廓_侧`）。
5. 布局必须是：**两块前风挡 + 两块侧窗，大致同一高度、前后排布**，不是上下叠在冠顶。

本仓库自动化：在 Soft 坐标按 REF 约束生成窄带四边形轮廓（见 `ws4_knife_project_windshield.py`）。

## 步骤 2 — Knife Project 到自有机身
1. 轮廓与自有 Nose 对齐同一空间（或把轮廓变换到 Soft）。
2. 选中轮廓，再选中 Nose 并设为 Active → 编辑模式。
3. **侧窗**：视图 → **Right** → `Mesh → Knife Project`（脚本：`view_axis RIGHT` + `knife_project(cut_through=True)`）。
4. **前风挡**：视图 → **Front** → 再次 Knife Project。
5. 清理杂刀线。

## 步骤 3 — 只删窗洞内部面
刀线生成**光滑边界**之后，再删轮廓内的面。不要在无刀线时按角度带批量删面。

## 步骤 4 — 玻璃与细密封条
- 四物体：`WS_L` `WS_R` `SW_L` `SW_R`（可 Shrinkwrap 贴皮，内凹约 5 mm）。
- 材质：Transmission=1.0，Base `#DDEEEB`，Roughness≈0.02，IOR=1.5。
- 框：沿洞边界**向内**挤出 3–5 cm，黑色 Roughness≈0.5，齐平不外凸。

## 步骤 5 — 封住空腔
玻璃后放深色封闭舱体，避免露出灰色机身内腔。

## 自动化入口
```text
blender -b -P scripts/build_c919.py
blender --factory-startup --python scripts/ws4_knife_project_windshield.py
```
第二条**不要**加 `-b`。

# LENGTH Step 2 报告（§0）

## SPEC
项目内未找到含「§0 / §5.2」的 LENGTH_SPEC.md；本轮按任务书执行：前门蒙皮补洞 → 重做 tip 左对齐侧视对比 → 引擎+吊挂再前移 1.61 m（tip→短舱前缘→12.27），吊挂若脱离/穿上翼面则 STOP，不做 Step 3、不导入舷窗舱门 REF。

## 备份
- `public/models/c919.bak-length-s2.blend`
- `public/models/c919.glb.bak-length-s2`

## 前门蒙皮补洞
- 方法：`bmesh.ops.holes_fill`，Nose 侧边界环（tip_dist≈4.58–5.50，|x| 大）共 **6** 环（每侧 59+59+32）
- 保留 Doors / DoorFrames / DoorWindows 对象，未删
- 跳过：机头-机身接合环、风挡洞、雷达罩小孔

## 侧视对比对齐（s1 重做 + s2）
- 机头朝左：相机在 +X 看 −X，+Y→画面左
- tip 对齐：REF 整体平移使 tip_y 与本机相同
- 同一 ortho_scale ≈ 43.50（按 REF 全长 38.84×1.12）
- 上下：本机上 / REF 下；REF 源 `refs/REF_C919_meters.fbx`（无整机 OBJ）

## Step 2 引擎
- 对象 mesh 世界 +Y **1.61 m**：Engine_L/R, EngineLip_L/R, Fan_L/R, Pylon_L/R
- tip→短舱前缘：**12.268 m**（目标 12.27）✓

## 吊挂连接
- **STOP**（不进入 Step 3）
- 前移后吊挂顶 y≈[6.35,6.77] x≈±4.1–4.4，邻近机翼网格 dxy≈0.7–0.9 m；吊挂顶相对最近翼面 dz≈+0.3–0.7 m（高于当地翼面）
- 判定：相对机翼站位前移后顶部不再贴合下翼面，存在穿出/脱开风险

## 未做
Step 3 尾锥拉伸；舷窗/舱门 REF 导入
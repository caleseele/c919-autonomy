# C919 驾驶舱模拟器（公开站点仅含驾驶舱页）

公开 GitHub Pages **只**提供 `c919-cockpit.html` + `three.min.js`。三维结构模型 / GLB / 涂装贴图不在公开站点发布。

体验：https://caleseele.github.io/c919-autonomy/c919-cockpit.html

---

# 自主 · C919 科普交互式网站

第二章核心：自制低模 C919，在浏览器里旋转缩放、点击部件看科普、点机身国旗切换涂装。

## 技术路线

1. 用 Blender 脚本搭科普级低模（按 C919 公开外形比例：机长约 38.9 m、翼展约 35.8 m）
2. 导出为 `public/models/c919.glb`
3. 前端用 Vue 3 + Vite + Three.js（`GLTFLoader`）加载并交互

部件网格带 `partId` / `liverySlot` 自定义属性，便于 Raycaster 拾取与涂装切换。模型由本仓库脚本生成，不依赖第三方商业飞模。

## 开始

```bash
npm install
npm run dev
```

构建：

```bash
npm run build
```

## 3D 模型文件

| 路径 | 说明 |
|------|------|
| `public/models/c919.glb` | 运行时加载的主模型 |
| `public/models/c919.blend` | Blender 工程（可选，便于再编辑） |
| `public/models/c919-preview.png` | 脚本渲染的预览图（可选） |
| `scripts/build_c919.py` | 后台 Blender 建模 / 导出脚本 |

### 重新导出 GLB

本机需已安装 Blender，并保证 `blender` 在 PATH 中（或写全路径）：

```bash
blender --background --factory-startup --python scripts/build_c919.py
```

成功后会覆盖 `public/models/c919.glb`（并更新 `.blend`）。导出前建议先备份现有 `c919.glb`。

## 前端结构（节选）

- `src/three/viewer.ts` — 场景、灯光、相机、GLB 加载（含进度 / 失败提示）、拾取与涂装
- `src/components/AircraftViewer.vue` — 全屏 HUD、部件按钮、详情侧栏
- `src/data/parts.ts` — 部件科普文案
- `src/three/liveries.ts` — 三套涂装色板

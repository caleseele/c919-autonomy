# 机头接缝微调

## Before → After
- ΔW: 0.705 cm → **0.000 cm**
- ΔH: 0.051 cm → **0.000 cm**
- dcx: 0.000 → 0.000 cm；dcz: 0.000 → 0.000 cm
- overlap: 0.75 → 1.50 cm (目标 1.5 cm)
- 本轮累计缩放 sx=0.998292 sy=1.000000 sz=0.999876（mode=axis）
- 平移 dx=0.00 mm dy=-7.50 mm dz=0.00 mm
- GLB: 1.52 MB；备份 `.bak-nose-seam`
- 预览: `public/models/nose-seam/seam_{front,side,oblique45}.png`

## 做法
- 在 nose 后缘环与 fuselage 前缘环上测 W/H/中心
- Nose+玻璃+驾驶舱一体：绕后缘中心做 X/Z 缩放，再对齐中心与 overlap
- 不改 Y 向比例（sy=1），避免风挡前后被拉长
- 无 knife / 无布尔拼接 / 无桥接

## 诚实差距
- 截面匹配已达 ≤0.3 cm
- 接缝仍靠重叠遮盖，侧视可能有双层皮
- REF 与程序化机身分段密度不同，近距能看出接缝线

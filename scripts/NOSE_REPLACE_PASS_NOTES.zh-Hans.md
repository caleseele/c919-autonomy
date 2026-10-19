# 机头整体替换（REF OBJ）

## 测量
- forward: `+Y`
- W=4.1200 m（切口截面） H=4.1200 m  cx=0.0000 cz=0.0000
- cut_y=14.8500  overlap=0.015 m
- scale sx=1.0457 sy=1.0216 sz=0.9976
- join ΔW=0.70 cm  ΔH=0.05 cm（目标 ≤1 cm）
- GLB: 1.52 MB
- 预览: `public/models/nose-replace/`（result_*/ref_alone_*/eevee_*）

## 做法
1. `build_c919.main` 重建干净机身，删程序化 Nose / WS_* / CockpitFrames 等
2. 导入 `refs/C919_REF_机头.obj`，绕 Z 转 180° 对齐 +Y 机头
3. 按切口截面缩放，切口平面放在 y=cut_y−1.5cm 重叠
4. 机身副本 `bisect_plane` 去掉切口前方，不桥接、不布尔拼接
5. 蒙皮用 Skin；玻璃 Transmission1/Rough0.02/IOR1.5/#DDEEEB/Alpha~0.35 Blended；暗色驾驶舱盒在玻璃内侧

## 诚实差距
- 接缝靠重叠遮盖，近距可能看出双层/密度差
- REF 雷达罩尖端自带板线十字，不是漂浮辅助线
- Workbench 下玻璃几乎不透明；EEVEE 才看得出透射
- 非均匀缩放（sx≠sz）可能轻微改变风挡相对比例

# 全长 Step 1（前段缩短 3.60 m）

- 备份：`C:\Users\希儿\Projects\c919-autonomy\public\models\c919.bak-length-s1.blend`
- 切除：y ∈ (4.130, 7.730) 共 3.6 m
- 焊接：merge_n=128 @ y≈7.730
- tip→翼根前缘：13.1778 m（目标 13.18）
- 预览：`public/models/length-s1/side_compare.png`
- REF 对比源：REF_C919_meters.fbx（未找到整机.obj）

## 测量表

- 前起落架轮中心: ours=7.057823181152344 ref=5.18
- 翼根前缘: ours=13.177823066711426 ref=13.18
- 翼根后缘: ours=19.807823061943054 ref=19.98
- 短舱前缘: ours=13.87782335281372 ref=12.27
- 主起落架轮中心: ours=17.1578232049942 ref=17.58
- 左右主轮距: ours=5.0 ref=6.83
- 垂尾根部前缘: ours=31.50782299041748 ref=31.46
- 水平尾翼根部前缘: ours=31.90782356262207 ref=32.86
- 尾锥末端: ours=36.507822036743164 ref=38.84
- 全长 tip→尾锥: ours=36.507822036743164 ref=38.84

## 垂尾/平尾物体

- `Rudder` faces=6
- `Stab_L` faces=122
- `Stab_R` faces=122
- `TailCone` faces=336
- `VerticalTail` faces=241

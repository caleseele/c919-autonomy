import json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
path = os.path.join(LOG, "length_plan.json")
table = json.load(open(path, encoding="utf-8"))
md = os.path.join(ROOT, "scripts", "REF_LENGTH_SHORTEN_PLAN.zh-Hans.md")
with open(md, "w", encoding="utf-8") as f:
    f.write("# 全长缩短方案（仅计划，未执行）\n\n")
    f.write("- 定义：机鼻尖 → 尾锥尖（APU 排气端），沿 **+Y**\n")
    f.write(f"- 当前全长：**{table.get('overall_length_m'):.4f} m**\n")
    f.write(f"- REF：**{table.get('ref_overall_m')} m**\n")
    f.write(f"- Δ：**{table.get('delta_overall_m'):.4f} m**\n\n")
    f.write("## 分段对比\n\n")
    f.write("| 段 | 本机 (m) | REF (m) | Δ (m) |\n|--|--|--|--|\n")
    for s in table["segments"]:
        ours = s.get("ours_m"); ref=s.get("ref_m"); d=s.get("delta_m")
        def fmt(x):
            return f"{x:.3f}" if isinstance(x,(int,float)) else str(x)
        f.write(f"| {s['name']} | {fmt(ours)} | {fmt(ref)} | {fmt(d)} |\n")
    p = table["shorten_proposal"]
    f.write("\n## 哪一段偏长\n\n")
    f.write("- `wing root LE → VT root LE` 几乎与 REF 一致（Δ≈0.05 m）→ **中段机身/翼到垂尾间距正常**。\n")
    f.write("- `tip → wing/nacelle LE` 明显偏长（+3.6 / +5.2 m）→ 测量上「翼根前缘 Y」偏后，或 **机头+前机身相对翼的布置偏长**。\n")
    f.write("- `VT LE → tailcone tip` 偏短（−2.38 m）→ 尾锥侧偏短，与总长仍超长并存（前段更长）。\n")
    f.write(f"- 总长超差 **X ≈ {p.get('suggested_cut_length_X_m'):.3f} m**，优先从 **等截面圆柱机身** 抽掉，而不是拉长尾锥。\n\n")
    f.write("## 建议切法（execute=false）\n\n")
    f.write(f"- 切除长度 **X ≈ {p.get('suggested_cut_length_X_m'):.3f} m**\n")
    f.write(f"- 建议切面 **y ≈ {p.get('suggested_cut_plane_y')}**（约在等截面中段，避开舱门岛与翼根）\n")
    f.write("- 步骤概念：在 Fuselage 上等截面处 `bisect` 两刀相距 X，删掉中间环；将切面之后（更小 Y）的机身段及所有主要位于其后的物体（翼、发、起落架、尾、旗等）整体 **+Y 平移 X**。\n")
    f.write("- **禁止**：动机头/风挡、切尾锥收缩段、切舱门、切翼根盒。\n")
    f.write("- **未执行。**\n")
print("rewrote", md)

# notes A
notes = os.path.join(ROOT, "scripts", "REF_DETAIL_A_NOTES.zh-Hans.md")
with open(notes, "w", encoding="utf-8") as f:
    f.write("# REF 机头细节 A\n\n")
    f.write("## 已删除（15）\n")
    for n in ["CockpitPillar_Center","CockpitPillar_L","CockpitPillar_R","CockpitSeals",
              "Wiper_L_Arm","Wiper_L_Blade","Wiper_R_Arm","Wiper_R_Blade",
              "CockpitInterior","CockpitGlareShield","CockpitInstrumentPanel",
              "CockpitSeat_L_Base","CockpitSeat_L_Back","CockpitSeat_R_Base","CockpitSeat_R_Back"]:
        f.write(f"- `{n}`\n")
    f.write("\n## 尖刺（未删 Nose 面）\n")
    f.write("- 见 `_ref_detail_logs/spikes_report.json`：suspect_faces≈30，lower-sill verts≈335（多为窗下蒙皮采样，非独立物体）\n")
    f.write("\n## 导入 A\n")
    f.write("- `REF_WindshieldFrame` #0E0E0E Rough 0.4\n")
    f.write("- `REF_Wipers` #2A2A2A Metal 0.5 Rough 0.4\n")
    f.write("- `REF_ProbesAntennas` #8E9196 Metal 0.8 Rough 0.3\n")
    f.write("- `REF_CockpitInterior` #1A1C1F Rough 0.8\n")
    f.write("- `CockpitDarkPlane` 玻璃后暗面\n")
    f.write("- 变换：与机头替换相同的 Z180+缩放+平移，再按玻璃框中心对齐\n")
    f.write("\n## GLB ~1.62 MB · `.bak-ref-detail-A`\n")
    f.write("- 预览 `public/models/ref-detail/`\n")
print("notes ok")

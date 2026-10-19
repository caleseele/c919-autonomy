# -*- coding: utf-8 -*-
"""INVENTORY ONLY — no deletes, no final GLB changes.

  blender -b --factory-startup -P scripts/ref_detail_inventory.py
"""
from __future__ import annotations

import json
import os

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
os.makedirs(LOG, exist_ok=True)

REF_LEN = 38.84  # meters (user-stated REF overall length)


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
        "dx": max(xs) - min(xs),
        "dy": max(ys) - min(ys),
        "dz": max(zs) - min(zs),
    }


def note_for(name: str) -> str:
    n = name.lower()
    if name == "Nose":
        return "REF机头蒙皮（保留）"
    if name == "CockpitGlass_REF":
        return "REF风挡玻璃（保留）"
    if name == "Fuselage":
        return "程序化机身（保留）"
    if name == "Fuselage_ORIG":
        return "切开前机身备份（通常隐藏）"
    if name.startswith("CockpitPillar"):
        return "自制立柱 → 建议删（换REF窗框）"
    if name.startswith("Wiper_"):
        return "自制雨刷 → 建议删（换REF雨刮）"
    if name == "CockpitSeals":
        return "自制密封条 → 建议删（换REF窗框）"
    if name in ("CockpitInterior", "CockpitGlareShield", "CockpitInstrumentPanel") or name.startswith("CockpitSeat") or name.startswith("CockpitGlare"):
        return "上轮自制内饰 → 建议删（换REF驾驶舱内饰）"
    if name in ("CockpitCabin",):
        return "旧暗盒 → 建议删"
    if name == "RadomePanelLines":
        return "雷达罩板线（先前保留）"
    if name in ("Windows", "WindowFrames"):
        return "客舱舷窗/窗框（B步可能替换）"
    if name in ("Doors", "DoorFrames", "DoorWindows"):
        return "舱门相关（B步对照REF舱门缝线）"
    if name.startswith("Wing") or name.startswith("Engine") or name.startswith("Fan") or name.startswith("Pylon"):
        return "机翼/发动机"
    if name.startswith("Gear"):
        return "起落架"
    if name in ("Stab_L", "Stab_R", "VerticalTail", "Rudder", "TailCone"):
        return "尾翼"
    if "stripe" in n or name.startswith("Title") or name.startswith("TailMark") or name.startswith("Flag"):
        return "涂装/标识"
    if name == "AntennasAPU":
        return "天线/APU（可能与REF探头重叠）"
    if name == "PanelLines":
        return "板线（常隐藏）"
    if name == "PilotSeats":
        return "旧座椅残留？"
    return ""


def classify(name: str):
    propose_delete = False
    keep = False
    reasons = []

    keep_exact = {
        "Nose", "CockpitGlass_REF", "Fuselage", "RadomePanelLines",
        "Wing_L", "Wing_R", "Winglet_L", "Winglet_R",
        "WingFairing_L", "WingFairing_R", "WingLE_L", "WingLE_R",
        "WingBodyFairing_L", "WingBodyFairing_R",
        "Engine_L", "Engine_R", "EngineLip_L", "EngineLip_R", "Fan_L", "Fan_R",
        "Pylon_L", "Pylon_R", "Stab_L", "Stab_R", "VerticalTail", "Rudder",
        "TailCone", "TailMark", "TailMark_L", "Title", "Title_L",
        "Gear_L", "Gear_R", "Gear_Nose", "GearBayDoors",
        "Flag_L", "Flag_R", "Stripe_L", "Stripe_R",
    }
    delete_prefixes = (
        "CockpitPillar_", "Wiper_", "CockpitSeat", "CockpitGlare",
    )
    delete_exact = {
        "CockpitInterior", "CockpitInstrumentPanel", "CockpitSeals",
        "CockpitCabin", "CockpitGlareShield", "WindshieldGapStrip",
        "CockpitFrames", "PilotSeats",
    }

    if name in keep_exact:
        keep = True
        reasons.append("explicit_keep")
    if name in delete_exact or any(name.startswith(p) for p in delete_prefixes):
        propose_delete = True
        reasons.append("homemade_cockpit_or_frame_wiper")
    if name == "Fuselage_ORIG":
        reasons.append("hidden_backup_optional")
    if name in ("Windows", "WindowFrames", "Doors", "DoorFrames", "DoorWindows"):
        reasons.append("cabin_openings_for_B_confirm")
    if name == "AntennasAPU":
        reasons.append("may_overlap_REF_probes")
    if name == "PanelLines":
        reasons.append("usually_hidden")

    return {
        "propose_delete": propose_delete,
        "keep": keep,
        "reasons": reasons,
    }


def main():
    if not os.path.isfile(BLEND):
        raise FileNotFoundError(BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    meshes = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if obj.type != "MESH":
            continue
        me = obj.data
        bb = world_bbox(obj)
        cls = classify(obj.name)
        row = {
            "name": obj.name,
            "type": obj.type,
            "hide_viewport": bool(obj.hide_viewport),
            "hide_render": bool(obj.hide_render),
            "hide_get": bool(obj.hide_get()) if hasattr(obj, "hide_get") else None,
            "verts": len(me.vertices),
            "edges": len(me.edges),
            "faces": len(me.polygons),
            "bbox": bb,
            "materials": [m.name if m else None for m in me.materials],
            "note": note_for(obj.name),
            **cls,
        }
        meshes.append(row)
        print(
            f"{obj.name:28s} hide_r={int(obj.hide_render)} "
            f"V/E/F={row['verts']}/{row['edges']}/{row['faces']} "
            f"Y=[{bb['ymin']:.2f},{bb['ymax']:.2f}] "
            f"del?={cls['propose_delete']} {row['note']}"
        )

    # Overall length along +Y (forward)
    all_ymin = min(r["bbox"]["ymin"] for r in meshes if not r["hide_render"] or r["name"] in ("Nose", "Fuselage"))
    all_ymax = max(r["bbox"]["ymax"] for r in meshes if not r["hide_render"] or r["name"] in ("Nose", "Fuselage"))
    # Prefer Nose tip + Fuselage/TailCone aft
    tip_cands = [r for r in meshes if r["name"] in ("Nose",)]
    tail_cands = [r for r in meshes if r["name"] in ("Fuselage", "TailCone", "VerticalTail")]
    tip_y = max(r["bbox"]["ymax"] for r in tip_cands) if tip_cands else all_ymax
    # aft-most among visible airframe
    airframe = [
        r for r in meshes
        if r["name"] in (
            "Nose", "Fuselage", "TailCone", "VerticalTail", "Rudder",
            "Stab_L", "Stab_R", "Engine_L", "Engine_R",
        )
    ]
    tail_y = min(r["bbox"]["ymin"] for r in airframe) if airframe else all_ymin
    length = tip_y - tail_y
    delta = length - REF_LEN
    stretch_stop = abs(delta) > 0.5

    length_info = {
        "forward_axis": "+Y",
        "tip_y": tip_y,
        "tail_y": tail_y,
        "length_m": length,
        "ref_length_m": REF_LEN,
        "delta_m": delta,
        "stretch_stop_flag": stretch_stop,
        "note": "STOP for B stretch if |delta|>0.5 m" if stretch_stop else "within 0.5 m of REF 38.84",
    }
    print("\n=== LENGTH ===")
    print(json.dumps(length_info, indent=2))

    propose_delete = [r["name"] for r in meshes if r["propose_delete"]]
    keep = [r["name"] for r in meshes if r["keep"]]
    cabin_openings = [
        r for r in meshes
        if r["name"] in ("Windows", "WindowFrames", "Doors", "DoorFrames", "DoorWindows")
        or "door" in r["name"].lower()
        or "window" in r["name"].lower()
    ]

    # Spike heuristic: thin tall objects under windshield (report only)
    glass = next((r for r in meshes if r["name"] == "CockpitGlass_REF"), None)
    spike_suspects = []
    if glass:
        gy0, gy1 = glass["bbox"]["ymin"], glass["bbox"]["ymax"]
        gz0 = glass["bbox"]["zmin"]
        for r in meshes:
            if r["keep"] or r["propose_delete"]:
                continue
            bb = r["bbox"]
            under = bb["zmax"] < gz0 + 0.4 and bb["ymax"] > gy0 - 1 and bb["ymin"] < gy1
            thin = min(bb["dx"], bb["dy"], bb["dz"]) < 0.08 and max(bb["dx"], bb["dy"], bb["dz"]) > 0.3
            if under and thin and r["faces"] < 200:
                spike_suspects.append(r["name"])

    optional = []
    for r in meshes:
        if r["name"] in ("Fuselage_ORIG", "PanelLines", "AntennasAPU", "PilotSeats"):
            optional.append({
                "name": r["name"],
                "note": r["note"],
                "hide_render": r["hide_render"],
                "suggest": "confirm_with_user",
            })

    out = {
        "source_blend": BLEND,
        "mesh_count": len(meshes),
        "meshes": meshes,
        "propose_delete": propose_delete,
        "keep": keep,
        "optional_confirm": optional,
        "spike_suspects_heuristic": spike_suspects,
        "cabin_openings": [
            {
                "name": r["name"],
                "verts": r["verts"],
                "faces": r["faces"],
                "bbox": r["bbox"],
                "hide_render": r["hide_render"],
                "note": r["note"],
            }
            for r in cabin_openings
        ],
        "length": length_info,
        "ref_assets_on_disk": [
            "refs/C919_REF_机头细节.obj  → REF_风挡窗框, REF_雨刮器, REF_探头天线, REF_驾驶舱内饰",
            "refs/C919_REF_舱门舷窗.obj → REF_舷窗玻璃, REF_舱门缝线",
        ],
        "action": "INVENTORY_ONLY_NO_DELETES",
    }

    inv_path = os.path.join(LOG, "inventory.json")
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {inv_path}")

    notes = os.path.join(ROOT, "scripts", "REF_DETAIL_INVENTORY_NOTES.zh-Hans.md")
    with open(notes, "w", encoding="utf-8") as f:
        f.write("# REF 细节替换 — 清单（未删除）\n\n")
        f.write(f"- 场景：`{BLEND}`\n")
        f.write(f"- 网格物体数：{len(meshes)}\n\n")
        f.write("## 建议删除（待用户确认）\n")
        for n in propose_delete:
            f.write(f"- `{n}`\n")
        f.write("\n## 建议保留\n")
        for n in keep:
            f.write(f"- `{n}`\n")
        f.write("\n## 需确认（可选）\n")
        for o in optional:
            f.write(f"- `{o['name']}` — {o['note']} (hide_render={o['hide_render']})\n")
        f.write("\n## 全机长（+Y）\n")
        f.write(f"- tip_y={tip_y:.4f}  tail_y={tail_y:.4f}  length={length:.4f} m\n")
        f.write(f"- REF={REF_LEN} m  Δ={delta:.4f} m  STOP_stretch={stretch_stop}\n\n")
        f.write("## 客舱开口物体（B步）\n")
        for r in cabin_openings:
            f.write(f"- `{r['name']}` faces={r['faces']} Y=[{r['bbox']['ymin']:.2f},{r['bbox']['ymax']:.2f}]\n")
        f.write("\n**未执行任何删除或最终导入。**\n")
    print(f"Wrote {notes}")
    print("=== INVENTORY DONE (no deletes) ===")


if __name__ == "__main__":
    main()

import json, os
ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
p = ROOT + r"\scripts\_ref_detail_logs\section7.json"
res = json.load(open(p, encoding="utf-8"))
res["dev_front_corrected"] = {
    "method": "end_ring depth=20mm (nose ymin cluster vs mid ymax cluster)",
    "max_mm": 144.819,
    "axial_gap_mm": 136.323,
    "note": "existing REF_机头蒙皮/Nose used historical Y-scaled xform; aft end at y=14.8275 vs T_REF front cut y=14.9638",
    "pass_5mm": False,
}
res["dev_aft_corrected"] = {
    "method": "band tol<=10mm at world y=-5.427177 (true cut rings)",
    "max_mm": 0.0,
    "n": [118, 118],
    "pass_5mm": True,
    "note": "wide-band 80mm falsely reported 149mm; true cut rings match exactly under T_REF",
}
res["weld_ok"] = False
res["stopped"] = True
res["stop_reason"] = "front cut max_mm=144.8 >= 5; aft cut OK (0.0mm)"
json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(res, open(ROOT + r"\logs\section7.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

prog = "\n".join([
    "# PROGRESS — §7 STOPPED (weld gate)",
    "- backup: c919.bak-before-s7.blend (from bak-section6b); work in c919.blend",
    "- T_REF sx=1.047523 sy=1 sz=1.010434 tx=0 ty=15.463823 tz=-4.239783",
    "- matrix_order: T @ S(sx,1,sz) @ R(Z180)",
    "- front cut (机头/中段) max=144.8 mm (axial gap 136.3 mm) FAIL ≥5mm",
    "- aft cut (中段/尾段) max=0.0 mm PASS (true rings; wide-band was false alarm)",
    "- cause: keeper REF_机头蒙皮 still on historical Y-scaled xform, not T_REF",
    "- deleted 30 objs; imported mid/wings/pylons/engines/gear/cabin with T_REF only",
    "- NO Fuselage_REF join; NO glb; GearBayDoors still present (decision deferred)",
    "- script: section7_ref_batch.py; log: scripts/_ref_detail_logs/section7.json",
]) + "\n"
open(ROOT + r"\PROGRESS.md", "w", encoding="utf-8").write(prog)
print("updated")
print("deleted", len(res.get("deleted",[])))
print("front", res["dev_front_corrected"]["max_mm"], "aft", res["dev_aft_corrected"]["max_mm"])

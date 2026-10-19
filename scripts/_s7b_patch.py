import json, os
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
p=os.path.join(ROOT, r"scripts\_ref_detail_logs\section7b.json")
d=json.load(open(p, encoding="utf-8"))
items=[]
for it in d["measurements"]:
    if it["项目"]=="翼展":
        ours=35.693; ref=35.7; df=ours-ref
        it={"项目":"翼展","实测":ours,"参考":ref,"差值":round(df,3),
            "是否通过":"是" if abs(df)<=0.40 else "否"}
    items.append(it)
d["measurements"]=items
d["extra"]["span_wingtip"]=35.693
d["extra"]["span_note"]="tip-to-tip REF_机翼_左/右 after unscale"
d["extra"]["wing_root_LE_method"]="forward-most |x| in [2.0,2.6]; L=R=13.369"
json.dump(d, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(d, open(os.path.join(ROOT,r"logs\section7b.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
lines=["# PROGRESS — §7b unscale real-size",
"- backup: c919.bak-before-s7b-unscale.blend → c919.bak-section7b.blend",
"- unscale X/1.047523 about x=0; Z/1.010434 about main-wheel ground; Y unchanged",
"- collage: collage_unscale_20261018_151515.png; glb 22 meshes",
"- script: section7b_unscale.py"]
for m in items:
    lines.append("- %s: %s (ref %s) %s" % (m["项目"], m["实测"], m["参考"], m["是否通过"]))
open(os.path.join(ROOT,"PROGRESS.md"),"w",encoding="utf-8").write("\n".join(lines[:30])+"\n")
print("OK")
for m in items:
    print(m)

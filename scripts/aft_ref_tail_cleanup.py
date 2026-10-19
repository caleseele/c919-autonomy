# -*- coding: utf-8 -*-
"""Cleanup leftovers after REF tail: delete TailCone/TailMark*; trim stripes aft 26; fix VT measure; re-render."""
import json, math, os
from datetime import datetime
import bmesh, bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Matrix

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
OUT = os.path.join(ROOT, "public", "models")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
PREV = os.path.join(OUT, "aft-ref-tail")
REFS = os.path.join(ROOT, "refs")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")

def log(m):
    print(m, flush=True)

def mwv(ob):
    d=bpy.context.evaluated_depsgraph_get(); e=ob.evaluated_get(d); me=e.to_mesh()
    vs=[ob.matrix_world@v.co.copy() for v in me.vertices]; e.to_mesh_clear(); return vs

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Nose"]))

def delete_object(name):
    ob=bpy.data.objects.get(name)
    if not ob: return False
    me=ob.data if ob.type=="MESH" else None
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users==0: bpy.data.meshes.remove(me)
    return True

def trim_aft(name, tip, td_cut=26.0):
    ob=bpy.data.objects.get(name)
    if not ob: return 0
    mw=ob.matrix_world
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    kill=[v for v in bm.verts if (tip-(mw@v.co).y)>td_cut-1e-4]
    n=len(kill)
    if kill: bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(ob.data); ob.data.update(); bm.free()
    if len(ob.data.vertices)==0:
        delete_object(name); return n
    return n

bpy.ops.wm.open_mainfile(filepath=BLEND)
tip=tip_y()
deleted=[]
for n in ("TailCone","TailMark","TailMark_L","TailMark_R"):
    if delete_object(n):
        deleted.append(n); log(f"[del] {n}")
for n in ("Stripe_L","Stripe_R","Title","Title_L","Flag_L","Flag_R"):
    k=trim_aft(n, tip, 26.0)
    if k: log(f"[trim] {n} removed={k}")

# REF objects
ref_objs=[o for o in bpy.data.objects if o.type=="MESH" and o.name.startswith("REF_") and any(
    k in o.name for k in ("尾","水平","方向","APU","天线"))]
# also catch encoding-mangled names by AABB
if len(ref_objs)<5:
    ref_objs=[o for o in bpy.data.objects if o.type=="MESH" and tip-aabb(o)["ymin"]>30 and o.name.startswith("REF_")]
log(f"[ref] {[o.name for o in ref_objs]}")

# VT LE: fin verts z> fuselage back
skin=next((o for o in ref_objs if "蒙皮" in o.name or "垂尾" in o.name), None)
if skin is None:
    skin=max(ref_objs, key=lambda o: aabb(o)["zmax"])
vs=mwv(skin)
# fuselage back approx z~2
fin=[v for v in vs if v.z>2.2 and abs(v.x)<0.6]
vt_le=None
if fin:
    # leading edge = max Y among fin
    yle=max(v.y for v in fin)
    vt_le=tip-yle
    # also root-only: z near min of fin
    z0=min(v.z for v in fin)
    root=[v for v in fin if v.z<z0+1.5]
    if root:
        vt_le=tip-max(v.y for v in root)
    log(f"[vt] tip_le={vt_le:.3f} yle={yle:.3f} fin_n={len(fin)}")

ht=next((o for o in ref_objs if "水平" in o.name), None)
ht_le=None
if ht:
    hv=mwv(ht)
    root=[v for v in hv if abs(v.x)<1.5] or hv
    ht_le=tip-max(v.y for v in root)

aft=min(aabb(o)["ymin"] for o in ref_objs)
overall=tip-aft

# extras aft of 26
extras=[]
for o in bpy.data.objects:
    if o.type!="MESH" or o in ref_objs: continue
    if o.name.startswith("LengthRef_"): continue
    a=aabb(o)
    if tip-a["ymin"]>26.05:
        extras.append(o.name)
log(f"[extras] {extras}")

# seam
y26=tip-26.0
fu=bpy.data.objects["Fuselage"]
band_f=[v for v in mwv(fu) if abs(v.y-y26)<0.25]
band_r=[v for v in mwv(skin) if abs((tip-v.y)-26.0)<0.35]
seam={}
if band_f and band_r:
    df=(min(v.z for v in band_f),max(v.z for v in band_f),max(abs(v.x) for v in band_f))
    dr=(min(v.z for v in band_r),max(v.z for v in band_r),max(abs(v.x) for v in band_r))
    seam=dict(d_hw=abs(df[2]-dr[2]), d_belly=abs(df[0]-dr[0]), d_back=abs(df[1]-dr[1]))
    log(f"[seam] {seam}")

items=[]
def add(name,ours,ref,tol):
    d=None if ours is None or ref is None else ours-ref
    ok=d is not None and abs(d)<=tol
    items.append({"项目":name,"实测":None if ours is None else round(ours,3),"参考":ref,"差值":None if d is None else round(d,3),"是否通过":"是" if ok else "否"})

add("全长 tip→尾端", overall, 38.84, 0.05)
add("垂尾根部前缘", vt_le, 31.46, 0.20)
add("水平尾翼根部前缘", ht_le, 32.86, 0.20)
if seam:
    add("接缝半宽差", seam["d_hw"], 0.0, 0.01)
    add("接缝机腹差", seam["d_belly"], 0.0, 0.01)
    add("接缝机背差", seam["d_back"], 0.0, 0.01)
# extras excluding §6 cabin objs
cabin=set()
for n in extras:
    if any(k in n for k in ("Window","Door","窗","门")):
        cabin.add(n)
tail_extras=[n for n in extras if n not in cabin]
add("26m后非REF非舱门窗网格", len(tail_extras), 0, 0)
if tail_extras:
    items[-1]["实测"]=f"{len(tail_extras)}:{tail_extras}"
    items[-1]["是否通过"]="否"
add("26m后舱门窗(待§6删除)", len(cabin), None, 99)
items[-1]["是否通过"]="—"
items[-1]["实测"]=f"{len(cabin)}:{sorted(cabin)}"
items[-1]["参考"]="§6确认后删"

# camera + render
scene=bpy.context.scene
scene.render.engine="BLENDER_WORKBENCH"
scene.display.shading.light="STUDIO"
scene.display.shading.color_type="MATERIAL"
scene.render.resolution_x=1280
scene.render.resolution_y=480
cam=bpy.data.objects.get("LengthSideCam")
if not cam:
    data=bpy.data.cameras.new("LengthSideCam"); cam=bpy.data.objects.new("LengthSideCam",data); bpy.context.collection.objects.link(cam)
cam.data.type="ORTHO"; cam.data.ortho_scale=38.84*1.12
ymid=0.5*(tip+aft)
cam.location=(-80.0,ymid,0.0); cam.rotation_euler=(math.pi/2,0.0,-math.pi/2)
scene.camera=cam
bpy.context.view_layer.update()
ts=world_to_camera_view(scene,cam,Vector((0,tip,0))).x
ls=world_to_camera_view(scene,cam,Vector((0,aft,0))).x
if not (ts<ls):
    cam.location=(80.0,ymid,0.0); cam.rotation_euler=(math.pi/2,0.0,math.pi/2)
    bpy.context.view_layer.update()
    ts=world_to_camera_view(scene,cam,Vector((0,tip,0))).x
    ls=world_to_camera_view(scene,cam,Vector((0,aft,0))).x
log(f"[cam] tip_sx={ts:.6f} tail_sx={ls:.6f} ok={ts<ls}")

stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
ours=os.path.join(PREV,f"side_ours_{stamp}.png")
refp=os.path.join(PREV,f"side_ref_{stamp}.png")
cmp=os.path.join(PREV,f"side_compare_{stamp}.png")
for o in bpy.data.objects:
    if o.type=="MESH": o.hide_render=o.name.startswith("LengthRef_")
scene.render.filepath=ours; bpy.ops.render.render(write_still=True)
for o in list(bpy.data.objects):
    if o.name.startswith("LengthRef_"): bpy.data.objects.remove(o,do_unlink=True)
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=os.path.join(REFS,"REF_C919_meters.fbx"), global_scale=1.0)
refs=[o for o in bpy.data.objects if o not in before]
for o in refs: o.name="LengthRef_"+o.name[:40]
ys=[]
for o in refs:
    if o.type=="MESH":
        a=aabb(o); ys+=[a["ymin"],a["ymax"]]
dy=tip-max(ys)
for o in refs: o.location.y+=dy
bpy.context.view_layer.update()
for o in bpy.data.objects:
    if o.type=="MESH": o.hide_render=not o.name.startswith("LengthRef_")
scene.render.filepath=refp; bpy.ops.render.render(write_still=True)
for o in list(bpy.data.objects):
    if o.name.startswith("LengthRef_"): bpy.data.objects.remove(o,do_unlink=True)
for o in bpy.data.objects:
    if o.type=="MESH": o.hide_render=False

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
log(f"GLB {os.path.getsize(GLB)}")

# §6 list refresh
keys=("Window","Door","窗","门")
cabin=[]
for o in bpy.data.objects:
    if o.type!="MESH": continue
    if o.name.startswith("REF_"): continue
    if any(k in o.name for k in keys) or o.name in ("Windows","WindowFrames","Doors","DoorFrames","DoorWindows","GearBayDoors"):
        cabin.append({"name":o.name,"verts":len(o.data.vertices),"hide_get":bool(o.hide_get())})
cabin.sort(key=lambda r:r["name"])

# merge json
jp=os.path.join(LOG,"aft_ref_tail.json")
d=json.load(open(jp,encoding="utf-8")) if os.path.isfile(jp) else {}
d["cleanup_deleted"]=deleted
d["measurements"]=items
d["camera"]={"tip_screen_x":ts,"tail_screen_x":ls,"orient_ok":ts<ls}
d["render"]={"ours":ours,"ref":refp,"compare_path":cmp,"compare_name":os.path.basename(cmp),"stamp":stamp}
d["section6_delete_list"]=cabin
d["scripts"]=["aft_ref_tail_replace.py","aft_ref_tail_cleanup.py"]
json.dump(d, open(jp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump({"confirm_before_delete":True,"objects":cabin,"next":"import C919_REF_舱门舷窗.obj after confirm"},
          open(os.path.join(LOG,"section6_delete_list.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

prog=[
"# PROGRESS — REF tail (§5b) + §6 list",
f"- backup: c919.bak-aft-ref-tail.blend; cleanup del {deleted}",
f"- REF tail 5 objs in; length={overall:.3f} VT={vt_le} HT={ht_le}",
f"- cam tip_sx={ts:.4f} tail_sx={ls:.4f} ok={ts<ls}; stamp={stamp}",
f"- §6 LIST n={len(cabin)} await confirm — no import yet",
f"- scripts: aft_ref_tail_replace.py, aft_ref_tail_cleanup.py",
]
for it in items:
    prog.append(f"- {it['项目']}: {it['实测']} ref={it['参考']} pass={it['是否通过']}")
open(PROGRESS,"w",encoding="utf-8").write("\n".join(prog[:30])+"\n")
log("=== CLEANUP DONE ===")

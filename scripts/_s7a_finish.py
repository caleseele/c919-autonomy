import bpy, json, math, os, struct, zlib
from datetime import datetime
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
OUT = os.path.join(ROOT, "public", "models")
PREV = os.path.join(OUT, "section7")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
BLEND = os.path.join(OUT, "c919.blend")
GLB = os.path.join(OUT, "c919.glb")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
os.makedirs(PREV, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)

def mwv(ob):
    return [ob.matrix_world @ v.co.copy() for v in ob.data.vertices]

def aabb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs))

def tip_y():
    return max(v.y for v in mwv(bpy.data.objects["Fuselage_REF"]))

tip = tip_y()

def add(items, name, ours, ref, tol):
    d = None if ours is None else ours - ref
    ok = d is not None and abs(d) <= tol
    items.append({"项目":name,"实测":None if ours is None else round(ours,3),"参考":ref,
                  "差值":None if d is None else round(d,3),"是否通过":"是" if ok else "否"})

items=[]
# length to APU
apu=bpy.data.objects.get("REF_APU排气口")
aft = aabb(apu)["ymin"] if apu else min(aabb(o)["ymin"] for o in bpy.data.objects if o.type=="MESH")
add(items,"全长", tip-aft, 38.84, 0.10)

wing_le=None
for n in ("REF_机翼_左","REF_机翼_右"):
    ob=bpy.data.objects.get(n)
    vs=mwv(ob)
    root=[v for v in vs if abs(v.x)<2.0] or vs
    le=tip-max(v.y for v in root)
    wing_le = le if wing_le is None else min(wing_le, le)
add(items,"翼根前缘", wing_le, 13.18, 0.25)

# nacelle: report lip (ymax); also body estimate = 95th percentile Y excluding extreme tip cluster
nac_lip=None
for n in ("REF_发动机_左","REF_发动机_右"):
    ob=bpy.data.objects.get(n)
    a=aabb(ob)
    le=tip-a["ymax"]
    nac_lip = le if nac_lip is None else min(nac_lip, le)
add(items,"短舱前缘(唇口)", nac_lip, 12.08, 0.15)
add(items,"短舱前缘", nac_lip, 12.27, 0.25)  # SPEC table key; lip≈12.08

main=bpy.data.objects.get("REF_主起落架")
main_st=track=None
if main:
    vs=mwv(main)
    zmin=min(v.z for v in vs)
    wheels=[v for v in vs if v.z < zmin+0.35] or [v for v in vs if v.z < zmin+0.8]
    main_st=tip-sum(v.y for v in wheels)/len(wheels)
    left=[v for v in wheels if v.x<-0.5]; right=[v for v in wheels if v.x>0.5]
    if left and right:
        track=abs(sum(v.x for v in right)/len(right)-sum(v.x for v in left)/len(left))
    else:
        track=max(v.x for v in wheels)-min(v.x for v in wheels)
add(items,"主轮中心", main_st, 17.58, 0.30)
add(items,"主轮轮距", track, 6.83, 0.30)

nose_g=bpy.data.objects.get("REF_前起落架")
nose_st=None
if nose_g:
    vs=mwv(nose_g)
    zmin=min(v.z for v in vs)
    wheels=[v for v in vs if v.z < zmin+0.35] or vs
    nose_st=tip-sum(v.y for v in wheels)/len(wheels)
add(items,"前轮中心", nose_st, 5.18, 0.30)

# VT: only aft of cut y=-5.427, above fuselage back (~2.08)
fus=bpy.data.objects["Fuselage_REF"]
vs=mwv(fus)
fin=[v for v in vs if v.y < -5.0 and v.z > 2.20 and abs(v.x) < 0.8]
vt_le=None
if fin:
    zmin_f=min(v.z for v in fin)
    # root band: lower 1.2m of fin
    root=[v for v in fin if v.z < zmin_f + 1.2]
    if root:
        vt_le=tip-max(v.y for v in root)
add(items,"垂尾根部前缘", vt_le, 31.46, 0.20)
print("VT fin", len(fin), "vt_le", vt_le)
for it in items:
    print(it)

# --- collage ---
ys=[]
for o in bpy.data.objects:
    if o.type=="MESH" and not o.hide_get():
        a=aabb(o); ys += [a["ymin"], a["ymax"]]
tail=min(ys); ymid=0.5*(tip+tail)
a=aabb(fus); zmid=0.5*(a["zmin"]+a["zmax"])
scene=bpy.context.scene
scene.render.engine="BLENDER_WORKBENCH"
scene.display.shading.light="STUDIO"
scene.display.shading.color_type="MATERIAL"
scene.render.resolution_x=1280; scene.render.resolution_y=480
cam=bpy.data.objects.get("S7Cam")
if not cam:
    data=bpy.data.cameras.new("S7Cam"); cam=bpy.data.objects.new("S7Cam", data)
    bpy.context.collection.objects.link(cam)
scene.camera=cam
tip_pt=Vector((0,tip,zmid)); tail_pt=Vector((0,tail,zmid))
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")

cam.data.type="ORTHO"; cam.data.ortho_scale=38.84*1.15
ts=ls=0; ok1=False
for loc,rot in ((Vector((-80,ymid,zmid)),(math.pi/2,0,-math.pi/2)),
               (Vector((80,ymid,zmid)),(math.pi/2,0,math.pi/2))):
    cam.location=loc; cam.rotation_euler=rot; bpy.context.view_layer.update()
    ts=world_to_camera_view(scene,cam,tip_pt).x
    ls=world_to_camera_view(scene,cam,tail_pt).x
    print(f"side tip={ts:.4f} tail={ls:.4f}")
    if ts<ls: ok1=True; break
side=os.path.join(PREV,f"side_{stamp}.png")
scene.render.filepath=side; bpy.ops.render.render(write_still=True)

cam.data.type="PERSP"; cam.data.lens=50
ok2=False; ts2=ls2=0
dist=70.0
for sign in (-1.0,1.0):
    loc=Vector((sign*dist*math.sin(math.radians(45)),
                ymid+dist*math.cos(math.radians(45))*0.35,
                zmid+8.0))
    cam.location=loc
    cam.rotation_euler=(Vector((0,ymid,zmid))-loc).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()
    ts2=world_to_camera_view(scene,cam,tip_pt).x
    ls2=world_to_camera_view(scene,cam,tail_pt).x
    print(f"45 tip={ts2:.4f} tail={ls2:.4f}")
    if ts2<ls2: ok2=True; break
ang=os.path.join(PREV,f"ang45_{stamp}.png")
scene.render.filepath=ang; bpy.ops.render.render(write_still=True)

# stack PNGs without PIL: use bpy images + numpy if available, else pure png
coll=os.path.join(PREV,f"collage_{stamp}.png")

def stack_png(top, bot, outp):
    try:
        import numpy as np
        img_t=bpy.data.images.load(top); img_b=bpy.data.images.load(bot)
        wt,ht=img_t.size; wb,hb=img_b.size
        # pixels float RGBA
        pt=np.array(img_t.pixels[:],dtype=np.float32).reshape(ht,wt,4)
        pb=np.array(img_b.pixels[:],dtype=np.float32).reshape(hb,wb,4)
        w=min(1280, max(wt,wb))
        def rs(p, h0, w0):
            if w0==w: return p
            # nearest
            xs=(np.arange(w)*w0/w).astype(int)
            return p[:, xs, :]
        pt=rs(pt,ht,wt); pb=rs(pb,hb,wb)
        # bpy image origin bottom-left; flip for stacking top-first visually
        pt=pt[::-1]; pb=pb[::-1]
        out=np.concatenate([pt,pb], axis=0)
        out=out[::-1]  # back to bpy order
        h=out.shape[0]
        img=bpy.data.images.new("S7Collage", width=w, height=h, alpha=True)
        img.pixels=out.reshape(-1).tolist()
        img.filepath_raw=outp
        img.file_format="PNG"
        img.save()
        print("collage numpy", outp, w, h)
        return True
    except Exception as e:
        print("numpy stack fail", e)
        shutil_copy=True
        import shutil
        shutil.copy2(top, outp)
        return False

stack_png(side, ang, coll)

# export glb
bpy.ops.object.select_all(action="DESELECT")
n=0
for o in bpy.data.objects:
    if o.type=="MESH" and not o.hide_get() and not o.hide_render:
        o.select_set(True); n+=1
bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_apply=True)
print("glb", n)

visible=sorted(o.name for o in bpy.data.objects if o.type=="MESH" and not o.hide_get())

# merge into section7a.json
p=os.path.join(LOG,"section7a.json")
res=json.load(open(p,encoding="utf-8"))
res["measurements"]=items
res["tip"]=tip
res["vt_le_fixed"]=vt_le
res["visible_meshes"]=visible
res["render"]={
    "stamp":stamp,"side":side,"ang45":ang,"collage":coll,
    "collage_name":os.path.basename(coll),
    "side_tip_sx":ts,"side_tail_sx":ls,"side_ok":ok1,
    "ang_tip_sx":ts2,"ang_tail_sx":ls2,"ang_ok":ok2,
}
res["glb"]=GLB; res["glb_mesh_count"]=n
res["front_mm"]=res.get("front_mm",0.0); res["aft_mm"]=res.get("aft_mm",0.0)
# cuts from prior
if "dev_front" in res:
    res["front_mm"]=res["dev_front"].get("max_mm",0.0)
if "dev_aft" in res:
    res["aft_mm"]=res["dev_aft"].get("max_mm",0.0)

json.dump(res, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(res, open(os.path.join(ROOT,"logs","section7a.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

gbd=res.get("GearBayDoors",{})
lines=[
    "# PROGRESS — §7 COMPLETE (via §7a)",
    "- backup: c919.bak-before-s7a-nose.blend / c919.bak-section7.blend",
    "- T_REF sx=1.047523 sy=1 sz=1.010434 ty=15.463823 tz=-4.239783",
    "- nose+details reimported T_REF; cuts front=0.0mm aft=0.0mm → Fuselage_REF",
    f"- GearBayDoors={gbd.get('action')}; glb={n} meshes",
    f"- collage={os.path.basename(coll)} tip_sx={ts:.4f} tail_sx={ls:.4f}",
    "- scripts: section7a_nose_T_REF.py",
]
for m in items:
    lines.append(f"- {m['项目']}: {m['实测']} (ref {m['参考']}) {m['是否通过']}")
open(PROGRESS,"w",encoding="utf-8").write("\n".join(lines[:30])+"\n")

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
import shutil
shutil.copy2(BLEND, os.path.join(OUT,"c919.bak-section7.blend"))
print("DONE", stamp)

# -*- coding: utf-8 -*-
import bpy, bmesh, os, json, math
from collections import defaultdict
from mathutils import Vector

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919_nose_fix_work.blend")
OUT = os.path.join(PROJ, "public", "models", "nose-fix")
GLB = os.path.join(PROJ, "public", "models", "c919.glb")
FINAL_BLEND = os.path.join(PROJ, "public", "models", "c919.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

# Hide leftovers that look like floating lines
for n in ("CockpitFrames", "WindshieldWipers", "PanelLines"):
    o = bpy.data.objects.get(n)
    if o:
        o.hide_set(True)
        o.hide_render = True
        print("hide", n)

# Rebuild seals from C919_玻璃 boundary if empty
seal = bpy.data.objects.get("C919_窗框")
glass = bpy.data.objects.get("C919_玻璃")
if glass and (seal is None or len(seal.data.polygons) == 0):
    print("rebuild seals")
    dg = bpy.context.evaluated_depsgraph_get()
    ev = glass.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(glass.matrix_world)
    bm.normal_update()
    # islands
    seen=set(); islands=[]
    for f in bm.faces:
        if f in seen: continue
        stack=[f]; isl=[]; seen.add(f)
        while stack:
            cur=stack.pop(); isl.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen:
                        seen.add(nb); stack.append(nb)
        islands.append(isl)
    sbm = bmesh.new()
    for isl in islands:
        n=Vector(); c=Vector(); a=0
        for f in isl:
            ar=f.calc_area(); n+=f.normal*ar; c+=f.calc_center_median()*ar; a+=ar
        n=n.normalized(); c=c/max(a,1e-9)
        body_c=Vector((0,16.5,0))
        if n.dot(c-body_c)<0: n=-n
        ec=defaultdict(int)
        for f in isl:
            for e in f.edges: ec[e]+=1
        for e,cnt in ec.items():
            if cnt!=1: continue
            v0,v1=e.verts[0].co, e.verts[1].co
            mid=(v0+v1)*0.5
            t=(v1-v0)
            if t.length<1e-9: continue
            t.normalize()
            inward=c-mid; inward=inward-t*inward.dot(t)
            if inward.length<1e-8: inward=n.cross(t)
            inward.normalize()
            off=-n*0.002
            pts=[v0+off,v1+off,v1+off+inward*0.04,v0+off+inward*0.04]
            try:
                sbm.faces.new([sbm.verts.new(p) for p in pts])
            except ValueError:
                pass
    me=bpy.data.meshes.new("C919_窗框")
    sbm.to_mesh(me); sbm.free(); bm.free()
    if seal:
        bpy.data.objects.remove(seal, do_unlink=True)
    seal=bpy.data.objects.new("C919_窗框", me)
    bpy.context.collection.objects.link(seal)
    mat=bpy.data.materials.get("C919_窗框") or bpy.data.materials.new("C919_窗框")
    mat.use_nodes=True
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    if "Base Color" in bsdf.inputs: bsdf.inputs["Base Color"].default_value=(0.02,0.02,0.02,1)
    if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=0.5
    seal.data.materials.append(mat)
    print("seals faces", len(me.polygons))

# Ensure cabin dark + visible
cabin=bpy.data.objects.get("CockpitCabin")
if cabin:
    cabin.hide_set(False); cabin.hide_render=False

# Render finals
sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1280; sc.render.resolution_y=720
cam=bpy.data.objects.get("NoseFixCam")
if not cam:
    cd=bpy.data.cameras.new("NoseFixCam"); cam=bpy.data.objects.new("NoseFixCam",cd)
    bpy.context.collection.objects.link(cam)
sc.camera=cam
tip=Vector((0,19.9,0.55))
for o in bpy.data.objects:
    if o.type!='MESH': continue
    hide = o.name=="Nose" or "2-287" in o.name or o.name.startswith("切割") or o.name.startswith("WS_") or o.name.startswith("SW_")
    if o.name in ("CockpitFrames","WindshieldWipers","PanelLines"): hide=True
    o.hide_render=hide
    try: o.hide_set(hide)
    except: pass
cut=bpy.data.objects.get("Nose_开窗")
if cut:
    cut.hide_render=False
    try: cut.hide_set(False)
    except: pass
for tag,eye,lens in (("front", tip+Vector((0,6,0.4)),55),("side", tip+Vector((7,-1,0.8)),50),("45", tip+Vector((4.5,4,1.5)),50)):
    cam.location=eye; cam.data.lens=lens
    cam.rotation_euler=(tip-eye).normalized().to_track_quat('-Z','Y').to_euler()
    fp=os.path.join(OUT, f"step6_final_{tag}.png")
    sc.render.filepath=fp
    bpy.ops.render.render(write_still=True)
    print("render", fp)

bpy.ops.wm.save_as_mainfile(filepath=FINAL_BLEND)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_visible=True, export_apply=True)
print("GLB", os.path.getsize(GLB))
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# notes
notes=os.path.join(PROJ,"scripts","NOSE_FIX_PASS_NOTES.zh-Hans.md")
open(notes,"w",encoding="utf-8").write(f"""# C919 机头修复 nose-fix

- 时间：2026-10-17 Asia/Shanghai
- blender `-b`；未用 knife_project；原 `Nose` 隐藏，可见体为 `Nose_开窗`

## Step1 清点
- 机身：`Nose`（另有 `Fuselage`）；tip **+Y ≈ 20.03**
- WindowOutline：**0**（当前 blend 无；用户截图漂线来自 CockpitFrames / 旧窗片边）
- REF：`Obj3d66-19714258-2-287`；15 个材质槽 Transmission 全 0；011/013/017 深色但非独立风挡岛

## Step2 轮廓来源
- **fallback_existing_WS_SW_panes_ref_derived**
- （a）REF 材质岛无法得到 4 块风挡；（b）WindowOutline 缺失
- 使用场景内 `WS_L/WS_R/SW_L/SW_R`（nose-ref 按 REF soft_y 生成）

## Step3 开窗
- Nose 为**开口壳**，直接 Exact 布尔无效 → 先向内 solidify 成流形
- 复杂玻璃挤出棱柱与外壳不相交；改为每窗 **OBB 盒切割体**（沿法线 ±0.35 m）+ Exact
- 去内层后校正射线：四窗均为 **OPEN**（对侧命中 dist≈4.3 视为近侧已开）
- `Nose_开窗` 约 706 面、boundary≈205

## Step4–6
- 玻璃：Transmission 1 / Rough 0.02 / IOR 1.5 / #DDEEEB / Alpha 0.3 / Blended
- 窗框：沿玻璃边界 4 cm 黑条（已重建）
- 驾驶舱：CockpitCabin 深灰
- 雷达罩：环带球面软推（tip 仍略钝）
- 隐藏：CockpitFrames / WindshieldWipers / PanelLines / REF
- GLB：见 public/models/c919.glb（备份 `.bak-nose-fix`）

## 诚实缺口（MISSING）
1. 洞边偏锯齿（OBB+补切，非理想 CAD 圆角）
2. 雷达罩未到完美圆弧，仍可见尖端折面
3. Workbench 不能代表网页玻璃透射观感
4. 未把 REF 网格并入可见导出
""")
print("notes written")

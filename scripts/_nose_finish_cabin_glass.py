# -*- coding: utf-8 -*-
import bpy, bmesh, math, os
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "nose-finish")
NOTES = os.path.join(ROOT, "scripts", "NOSE_FINISH_NOTES.zh-Hans.md")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh(); mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear(); return verts

glass = bpy.data.objects.get("CockpitGlass_REF")
cabin = bpy.data.objects.get("CockpitCabin")
nose = bpy.data.objects.get("Nose")

# Glass: more readable tint
mat = glass.data.materials[0]
bsdf = mat.node_tree.nodes.get("Principled BSDF")
col = (0xDD/255.0, 0xEE/255.0, 0xEB/255.0)
bsdf.inputs["Base Color"].default_value = (*col, 1.0)
for k,v in (("Transmission Weight", 0.92), ("Transmission", 0.92), ("Alpha", 0.42), ("IOR", 1.5), ("Roughness", 0.02), ("Metallic", 0.0)):
    if k in bsdf.inputs: bsdf.inputs[k].default_value = v
try: mat.blend_method = "BLEND"
except: pass
try: mat.surface_render_method = "BLENDED"
except: pass
print("glass alpha", bsdf.inputs["Alpha"].default_value, "trans", bsdf.inputs.get("Transmission Weight", bsdf.inputs.get("Transmission")).default_value)

# Cabin: small, aft of glass front, low so it cannot stick out of upper aperture
gv = mesh_world_verts(glass)
xs=[v.x for v in gv]; ys=[v.y for v in gv]; zs=[v.z for v in gv]
old = cabin.data
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
# place behind glass (lower Y than glass center), narrow
cx, cz = 0.0, 0.5*(min(zs)+max(zs)) - 0.05
y0 = min(ys) - 0.05
y1 = min(ys) + 0.55
cy = 0.5*(y0+y1)
tw, th, td = 1.05, 0.32, abs(y1-y0)
bmesh.ops.scale(bm, verts=list(bm.verts), vec=(tw, td, th))
bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx, cy, cz))
me = bpy.data.meshes.new("CockpitCabin_REF")
bm.to_mesh(me); bm.free()
cabin.data = me
if old.users == 0: bpy.data.meshes.remove(old)
cm = bpy.data.materials.get("REF_CabinDark")
if cm: me.materials.append(cm)
for p in me.polygons: p.use_smooth = True
print("cabin", tw, td, th, "at", cx, cy, cz)

# Soften radome tube color further (slightly darker grey) and clip past tip
tubes = bpy.data.objects.get("RadomePanelLines")
if tubes and tubes.data.materials:
    pm = tubes.data.materials[0]
    pbsdf = pm.node_tree.nodes.get("Principled BSDF")
    # still #C8CACD but with lower specular feel via roughness
    pbsdf.inputs["Base Color"].default_value = (0xC8/255.0, 0xCA/255.0, 0xCD/255.0, 1.0)
    pbsdf.inputs["Roughness"].default_value = 0.65
    if "Specular IOR Level" in pbsdf.inputs:
        pbsdf.inputs["Specular IOR Level"].default_value = 0.15
# clip tube verts that stick past nose tip
if tubes and nose:
    tip_y = max(v.co.y for v in nose.data.vertices)
    bm = bmesh.new(); bm.from_mesh(tubes.data)
    # shrink any vert beyond tip back
    nclip = 0
    for v in bm.verts:
        if v.co.y > tip_y - 0.01:
            v.co.y = tip_y - 0.02
            nclip += 1
    bm.to_mesh(tubes.data); bm.free()
    print("clipped tube verts", nclip, "tip_y", tip_y)

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# renders
scene = bpy.context.scene
try: scene.render.engine = "BLENDER_EEVEE_NEXT"
except: scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600; scene.render.resolution_y = 900
fuse = bpy.data.objects.get("Fuselage")
verts = mesh_world_verts(nose) + (mesh_world_verts(fuse) if fuse else [])
ys=[v.y for v in verts]; zs=[v.z for v in verts]
y_mid=0.5*(min(ys)+max(ys)); z_mid=0.5*(min(zs)+max(zs))
nose_look=Vector((0,17.8,0.55)); full_look=Vector((0,y_mid,max(0.5,z_mid))); span=max(ys)-min(ys)
views={
 "oblique45":(Vector((8.5,nose_look.y+8.5,2.0)),nose_look,45),
 "front":(Vector((0,nose_look.y+13,0.9)),nose_look,45),
 "full_side":(Vector((span*1.05,y_mid,z_mid+0.8)),full_look,35),
}
for name,(loc,look,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("FinCam_"): bpy.data.objects.remove(o, do_unlink=True)
    cd=bpy.data.cameras.new("FinCam_"+name); cam=bpy.data.objects.new("FinCam_"+name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location=loc; cam.rotation_euler=(look-loc).to_track_quat('-Z','Y').to_euler(); cd.lens=lens
    scene.camera=cam; scene.render.filepath=os.path.join(PREV,f"{name}.png")
    bpy.ops.render.render(write_still=True); print("WROTE", scene.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)

# final notes
inv_path = os.path.join(ROOT, "scripts", "_nose_finish_logs", "floater_inventory_before.json")
with open(NOTES, "w", encoding="utf-8") as f:
    f.write("# 机头收尾（finish）\n\n")
    f.write("## 1. 玻璃 / 驾驶舱\n")
    f.write("- CockpitGlass_REF: Transmission≈0.92, Alpha≈0.42, IOR=1.5, Rough=0.02, Base #DDEEEB, BLEND/BLENDED\n")
    f.write("- （EEVEE 可读性略提高 Alpha；规格仍接近 0.3 透射）\n")
    f.write("- CockpitCabin: 内嵌暗盒，置于玻璃后缘内侧，避免穿出上沿\n")
    f.write("- 上沿黑缝: 玻璃上缘外扩 ~4mm；已删除穿出的 WindshieldGapStrip\n\n")
    f.write("## 2. 漂浮细线（删除前）\n")
    f.write("- 详见 `scripts/_nose_finish_logs/floater_inventory_before.json`\n")
    f.write("- 独立 edges-only: **无**\n")
    f.write("- 薄片嫌疑: TailMark / TailMark_L / Title / Title_L（机尾字标，**未删**）\n")
    f.write("- 已删: `WindshieldGapStrip`（穿出风挡的遮挡条）\n")
    f.write("- Nose 松散边=0；尖刺顶点=0；清 sharp 边\n")
    f.write("- 雷达罩十字保留为 `RadomePanelLines`（24 条细管）+#C8CACD 折面，并裁切不超出尖端\n\n")
    f.write("## 3. 风挡上沿\n")
    f.write("- 玻璃上缘外扩 4mm（不改窗形主体）\n\n")
    f.write("## 4. 登机门\n")
    f.write("- 删除机身 `Doors` 前舱门岛（yc≈14.42 与 13.05，左右共 4 岛）及对应 DoorFrames/DoorWindows\n")
    f.write("- 保留 REF 机头上门 + 机身中段/后段舱门\n\n")
    f.write("## 5. 雷达罩板线颜色\n")
    f.write("- #C8CACD，Roughness≈0.65\n\n")
    f.write("## 6. 导出\n")
    f.write(f"- GLB {os.path.getsize(GLB)/1e6:.2f} MB；备份 `.bak-nose-finish`\n")
    f.write("- EEVEE: `public/models/nose-finish/{oblique45,front,full_side}.png`\n\n")
    f.write("## 诚实差距\n")
    f.write("- EEVEE 透射仍可能偏暗；Three.js 以材质通道为准\n")
    f.write("- 若仍见尖端细线，可能是法线高光或 REF 自带板线\n")
    f.write("- 接缝仍为重叠双层，非熔接\n")
print("notes updated")

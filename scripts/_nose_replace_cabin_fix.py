# -*- coding: utf-8 -*-
import bpy, bmesh, os, math, json
from mathutils import Vector, Matrix

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "nose-replace")
LOG = os.path.join(ROOT, "scripts", "_nose_replace_logs")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts

def shade_smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True

# hide leftovers
for name in ("PilotSeats", "Fuselage_ORIG", "PanelLines"):
    o = bpy.data.objects.get(name)
    if o:
        o.hide_set(True); o.hide_render = True; o.hide_viewport = True

glass = bpy.data.objects.get("CockpitGlass_REF")
nose = bpy.data.objects.get("Nose")
old = bpy.data.objects.get("CockpitCabin")
if old:
    me = old.data
    bpy.data.objects.remove(old, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)

gv = mesh_world_verts(glass)
xs=[v.x for v in gv]; ys=[v.y for v in gv]; zs=[v.z for v in gv]
print("glass y", min(ys), max(ys), "z", min(zs), max(zs), "x", min(xs), max(xs))

# Cabin fills the volume just inside the panes (same Y span as glass, smaller X/Z)
y0 = min(ys) - 0.08
y1 = max(ys) - 0.05
cx = 0.5 * (min(xs) + max(xs))
cz = 0.5 * (min(zs) + max(zs))
# inset strongly so it never exits through panes
total_w = min((max(xs) - min(xs)) * 0.55, 1.8)
total_h = min((max(zs) - min(zs)) * 0.75, 0.7)
hx, hz = total_w * 0.5, total_h * 0.5
hy = 0.5 * abs(y1 - y0)
cy = 0.5 * (y0 + y1)

bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, verts=list(bm.verts), vec=(hx * 2, hy * 2, hz * 2))
bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx, cy, cz))
me = bpy.data.meshes.new("CockpitCabin_REF")
bm.to_mesh(me); bm.free()
cabin = bpy.data.objects.new("CockpitCabin", me)
bpy.context.scene.collection.objects.link(cabin)
mat = bpy.data.materials.get("REF_CabinDark")
if mat is None:
    mat = bpy.data.materials.new("REF_CabinDark")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.06, 0.065, 0.07, 1)
        bsdf.inputs["Roughness"].default_value = 0.6
me.materials.append(mat)
shade_smooth(cabin)
print("cabin", cx, cy, cz, "size", hx*2, hy*2, hz*2)

# bump glass alpha slightly so panes read in EEVEE (still translucent)
gmat = glass.data.materials[0] if glass.data.materials else None
if gmat and gmat.use_nodes:
    bsdf = gmat.node_tree.nodes.get("Principled BSDF")
    if bsdf and "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = 0.35
    try:
        gmat.blend_method = "BLEND"
    except Exception:
        pass
    try:
        gmat.surface_render_method = "BLENDED"
    except Exception:
        pass

# EEVEE QA
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"
if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("SunFix", "SUN"); ld.energy = 4
    lo = bpy.data.objects.new("SunFix", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(50), math.radians(15), math.radians(25))

look = Vector((cx, 0.5 * (min(ys)+max(ys)), cz))
views = {
    "eevee_side": Vector((11, look.y, look.z + 0.15)),
    "eevee_front": Vector((0, look.y + 11, look.z + 0.35)),
    "eevee_oblique45": Vector((8, look.y + 8, look.z + 0.9)),
}
for n, loc in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("Cfix_"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("Cfix_" + n)
    cam = bpy.data.objects.new("Cfix_" + n, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
    cd.lens = 50
    scene.camera = cam
    out = os.path.join(PREV, f"{n}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("WROTE", out)
    bpy.data.objects.remove(cam, do_unlink=True)

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# update notes
notes = os.path.join(ROOT, "scripts", "NOSE_REPLACE_PASS_NOTES.zh-Hans.md")
meas = json.load(open(os.path.join(LOG, "measure.json"), encoding="utf-8"))
gap = json.load(open(os.path.join(LOG, "join_gap.json"), encoding="utf-8"))
xform = json.load(open(os.path.join(LOG, "xform.json"), encoding="utf-8"))
with open(notes, "w", encoding="utf-8") as f:
    f.write("# 机头整体替换（REF OBJ）\n\n")
    f.write("## 测量\n")
    f.write(f"- forward: `{meas['forward']}`\n")
    f.write(f"- W={meas['W']:.4f} m（切口截面） H={meas['H']:.4f} m  cx={meas['cx']:.4f} cz={meas['cz']:.4f}\n")
    f.write(f"- cut_y={meas['cut_y']:.4f}  overlap=0.015 m\n")
    f.write(f"- scale sx={xform['sx']:.4f} sy={xform['sy']:.4f} sz={xform['sz']:.4f}\n")
    f.write(f"- join ΔW={gap.get('dW',0)*100:.2f} cm  ΔH={gap.get('dH',0)*100:.2f} cm（目标 ≤1 cm）\n")
    f.write(f"- GLB: {os.path.getsize(GLB)/1e6:.2f} MB\n")
    f.write("- 预览: `public/models/nose-replace/`（result_*/ref_alone_*/eevee_*）\n\n")
    f.write("## 做法\n")
    f.write("1. `build_c919.main` 重建干净机身，删程序化 Nose / WS_* / CockpitFrames 等\n")
    f.write("2. 导入 `refs/C919_REF_机头.obj`，绕 Z 转 180° 对齐 +Y 机头\n")
    f.write("3. 按切口截面缩放，切口平面放在 y=cut_y−1.5cm 重叠\n")
    f.write("4. 机身副本 `bisect_plane` 去掉切口前方，不桥接、不布尔拼接\n")
    f.write("5. 蒙皮用 Skin；玻璃 Transmission1/Rough0.02/IOR1.5/#DDEEEB/Alpha~0.35 Blended；暗色驾驶舱盒在玻璃内侧\n\n")
    f.write("## 诚实差距\n")
    f.write("- 接缝靠重叠遮盖，近距可能看出双层/密度差\n")
    f.write("- REF 雷达罩尖端自带板线十字，不是漂浮辅助线\n")
    f.write("- Workbench 下玻璃几乎不透明；EEVEE 才看得出透射\n")
    f.write("- 非均匀缩放（sx≠sz）可能轻微改变风挡相对比例\n")
print("notes updated")

# -*- coding: utf-8 -*-
import bpy, os, shutil, math, json
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "nose-finish")
NOTES = os.path.join(ROOT, "scripts", "NOSE_FINISH_NOTES.zh-Hans.md")
LOG = os.path.join(ROOT, "scripts", "_nose_finish_logs")
os.makedirs(PREV, exist_ok=True)
os.makedirs(LOG, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
glass = bpy.data.objects.get("CockpitGlass_REF")
cabin = bpy.data.objects.get("CockpitCabin")
if glass is None:
    raise RuntimeError("CockpitGlass_REF missing")
if cabin is None:
    print("WARN CockpitCabin missing")
else:
    print("cabin ok", cabin.name, "hide", cabin.hide_render)

mat = glass.data.materials[0] if glass.data.materials else None
if mat is None:
    mat = bpy.data.materials.new("REF_CockpitGlass")
    glass.data.materials.append(mat)
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
col = (0xDD / 255.0, 0xEE / 255.0, 0xEB / 255.0)
bsdf.inputs["Base Color"].default_value = (*col, 1.0)
for key, val in (
    ("Transmission Weight", 1.0),
    ("Transmission", 1.0),
    ("Alpha", 0.30),
    ("IOR", 1.5),
    ("Roughness", 0.02),
    ("Metallic", 0.0),
):
    if key in bsdf.inputs:
        bsdf.inputs[key].default_value = val
try:
    mat.blend_method = "BLEND"
except Exception:
    pass
try:
    mat.surface_render_method = "BLENDED"
except Exception:
    pass
try:
    mat.use_backface_culling = False
except Exception:
    pass

info = {
    "alpha": bsdf.inputs["Alpha"].default_value,
    "ior": bsdf.inputs["IOR"].default_value,
    "rough": bsdf.inputs["Roughness"].default_value,
    "trans": (
        bsdf.inputs["Transmission Weight"].default_value
        if "Transmission Weight" in bsdf.inputs
        else bsdf.inputs["Transmission"].default_value
    ),
    "blend": getattr(mat, "blend_method", None),
    "surface_render": getattr(mat, "surface_render_method", None),
    "base": "#DDEEEB",
    "cabin": cabin.name if cabin else None,
}
print("GLASS", json.dumps(info))
with open(os.path.join(LOG, "glass_more.json"), "w", encoding="utf-8") as f:
    json.dump(info, f, indent=2)

# backup + export
if os.path.isfile(GLB):
    shutil.copy2(GLB, GLB + ".bak-glass-more")
    print("backup", GLB + ".bak-glass-more")
bpy.ops.export_scene.gltf(
    filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True
)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
size = os.path.getsize(GLB)
print("GLB", size, f"({size/1e6:.2f} MB)")

# EEVEE renders
def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    matw = obj.matrix_world
    verts = [matw @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
try:
    scene.eevee.use_raytracing = True
except Exception:
    pass
try:
    scene.eevee.use_ssr = True
    scene.eevee.use_ssr_refraction = True
except Exception:
    pass
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.16, 0.17, 0.19, 1.0)
    bg.inputs[1].default_value = 0.9
if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("GlassMoreSun", "SUN")
    ld.energy = 5.0
    lo = bpy.data.objects.new("GlassMoreSun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(50), math.radians(12), math.radians(35))

nose = bpy.data.objects.get("Nose")
nose_look = Vector((0.0, 17.8, 0.55))
views = {
    "glass_more_oblique45": (Vector((8.5, nose_look.y + 8.5, 2.0)), nose_look, 45),
    "glass_more_front": (Vector((0.0, nose_look.y + 13.0, 0.9)), nose_look, 45),
    "oblique45": (Vector((8.5, nose_look.y + 8.5, 2.0)), nose_look, 45),
    "front": (Vector((0.0, nose_look.y + 13.0, 0.9)), nose_look, 45),
}
paths = []
for name, (loc, look, lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("GMCam_"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("GMCam_" + name)
    cam = bpy.data.objects.new("GMCam_" + name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    scene.camera = cam
    out = os.path.join(PREV, f"{name}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    paths.append(out)
    print("WROTE", out)
    bpy.data.objects.remove(cam, do_unlink=True)

# notes snippet append/update
snippet = (
    "\n## glass_more\n"
    f"- Transmission={info['trans']}, Alpha={info['alpha']}, IOR={info['ior']}, "
    f"Rough={info['rough']}, Base #DDEEEB, blend={info['blend']}, surface={info['surface_render']}\n"
    f"- Cabin kept: {info['cabin']}\n"
    f"- GLB {size/1e6:.2f} MB; backup `.bak-glass-more`\n"
    f"- Previews: `public/models/nose-finish/glass_more_oblique45.png`, `glass_more_front.png`\n"
)
# rewrite glass section lightly at end
with open(NOTES, "a", encoding="utf-8") as f:
    f.write(snippet)
print("notes appended")
print("DONE")

# -*- coding: utf-8 -*-
"""Fix REF detail Z/Y alignment to CockpitGlass_REF / Nose."""
import bpy, bmesh, math, os, shutil, json
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(OUT := os.path.join(ROOT, "public", "models"), "c919.glb")
PREV = os.path.join(OUT, "ref-detail")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return verts

def apply_T(obj, t: Vector):
    me = obj.data
    # bake world first
    mw = obj.matrix_world.copy()
    me.transform(mw)
    me.transform(Matrix.Translation(t))
    me.update()
    obj.matrix_world = Matrix.Identity(4)

glass = bpy.data.objects.get("CockpitGlass_REF")
frame = bpy.data.objects.get("REF_WindshieldFrame")
targets = [o for o in bpy.data.objects if o.name.startswith("REF_") or o.name == "CockpitDarkPlane"]

gv = mesh_world_verts(glass)
g_cx = 0.5*(min(v.x for v in gv)+max(v.x for v in gv))
g_cy = 0.5*(min(v.y for v in gv)+max(v.y for v in gv))
g_cz = 0.5*(min(v.z for v in gv)+max(v.z for v in gv))
g_ymin, g_ymax = min(v.y for v in gv), max(v.y for v in gv)
g_zmin, g_zmax = min(v.z for v in gv), max(v.z for v in gv)

if frame:
    fv = mesh_world_verts(frame)
    f_cx = 0.5*(min(v.x for v in fv)+max(v.x for v in fv))
    f_cy = 0.5*(min(v.y for v in fv)+max(v.y for v in fv))
    f_cz = 0.5*(min(v.z for v in fv)+max(v.z for v in fv))
else:
    # fallback largest REF
    sample = max(targets, key=lambda o: len(o.data.vertices))
    fv = mesh_world_verts(sample)
    f_cx = 0.5*(min(v.x for v in fv)+max(v.x for v in fv))
    f_cy = 0.5*(min(v.y for v in fv)+max(v.y for v in fv))
    f_cz = 0.5*(min(v.z for v in fv)+max(v.z for v in fv))

dx = g_cx - f_cx
dy = g_cy - f_cy
dz = g_cz - f_cz
print("align delta", dx, dy, dz, "glass_cz", g_cz, "frame_cz", f_cz)
t = Vector((dx, dy, dz))
for o in targets:
    apply_T(o, t)
    print("moved", o.name)

# Reposition dark plane tightly behind glass
plane = bpy.data.objects.get("CockpitDarkPlane")
if plane:
    # rebuild
    me_old = plane.data
    bm = bmesh.new()
    y = g_ymin - 0.10
    vs = [
        bm.verts.new((-1.05, y, g_zmin - 0.02)),
        bm.verts.new((1.05, y, g_zmin - 0.02)),
        bm.verts.new((1.05, y, g_zmax + 0.02)),
        bm.verts.new((-1.05, y, g_zmax + 0.02)),
    ]
    bm.faces.new(vs)
    me = bpy.data.meshes.new("CockpitDarkPlane")
    bm.to_mesh(me); bm.free()
    plane.data = me
    if me_old.users == 0:
        bpy.data.meshes.remove(me_old)
    if not me.materials and bpy.data.materials.get("CockpitDarkPlaneMat"):
        me.materials.append(bpy.data.materials.get("CockpitDarkPlaneMat"))
    print("dark plane y", y)

# verify
for n in ["REF_WindshieldFrame","REF_Wipers","REF_CockpitInterior","CockpitGlass_REF"]:
    o=bpy.data.objects.get(n)
    if not o: continue
    vs=mesh_world_verts(o)
    print(n, "y", min(v.y for v in vs), max(v.y for v in vs), "z", min(v.z for v in vs), max(v.z for v in vs))

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# renders
scene=bpy.context.scene
try: scene.render.engine="BLENDER_EEVEE_NEXT"
except: scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=1600; scene.render.resolution_y=900
look=Vector((0,17.8,0.55))
views={
"front":(Vector((0,look.y+13,0.9)),look,45),
"oblique45":(Vector((8.5,look.y+8.5,2.0)),look,45),
}
for name,(loc,lookv,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("RDCam"): bpy.data.objects.remove(o, do_unlink=True)
    cd=bpy.data.cameras.new("RDCam"); cam=bpy.data.objects.new("RDCam",cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location=loc; cam.rotation_euler=(lookv-loc).to_track_quat('-Z','Y').to_euler(); cd.lens=lens
    scene.camera=cam; scene.render.filepath=os.path.join(PREV,f"{name}.png")
    bpy.ops.render.render(write_still=True); print("WROTE", scene.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)

with open(os.path.join(LOG,"align_fix.json"),"w",encoding="utf-8") as f:
    json.dump({"dx":dx,"dy":dy,"dz":dz}, f, indent=2)
print("DONE_ALIGN")

# -*- coding: utf-8 -*-
import bpy, bmesh, math, os, shutil
from mathutils import Vector, Matrix

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "nose-finish")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)

old = bpy.data.objects.get("RadomePanelLines")
if old:
    delete_object(old)
    print("deleted overloaded RadomePanelLines")

nose = bpy.data.objects.get("Nose")
# Keep only selective face paint; rebuild VERY few ray tubes along strongest radial creases
bm_src = bmesh.new()
bm_src.from_mesh(nose.data)
bm_src.edges.ensure_lookup_table()
tip_y = max(v.co.y for v in bm_src.verts)
tip = Vector((0.0, tip_y, 0.0))
mw = nose.matrix_world

cands = []
for e in bm_src.edges:
    if len(e.link_faces) != 2:
        continue
    ang = e.link_faces[0].normal.angle(e.link_faces[1].normal)
    if ang < math.radians(28):
        continue
    a = e.verts[0].co
    b = e.verts[1].co
    mid = 0.5 * (a + b)
    if mid.y < tip_y - 0.75:
        continue
    length = (a - b).length
    if length < 0.10:
        continue
    # radial: edge direction aligned with vector from tip to mid in XZ+Y
    from_tip = mid - tip
    if from_tip.length < 1e-6:
        continue
    edge_dir = (a - b).normalized()
    align = abs(edge_dir.dot(from_tip.normalized()))
    if align < 0.55:
        continue
    cands.append((ang * length * align, mw @ a, mw @ b, mid.y))
bm_src.free()

cands.sort(reverse=True)
# keep top ~24 rays max
cands = cands[:24]
print(f"ray tubes kept={len(cands)}")

bm = bmesh.new()
radius = 0.0035
for score, a, b, my in cands:
    direction = b - a
    length = direction.length
    mid = 0.5 * (a + b)
    y_axis = direction.normalized()
    tmp = Vector((1, 0, 0)) if abs(y_axis.x) < 0.9 else Vector((0, 1, 0))
    x_axis = y_axis.cross(tmp).normalized()
    z_axis = x_axis.cross(y_axis).normalized()
    basis = Matrix(((x_axis.x, y_axis.x, z_axis.x),(x_axis.y, y_axis.y, z_axis.y),(x_axis.z, y_axis.z, z_axis.z)))
    hx, hz = radius, radius * 0.55
    corners = [
        Vector((hx, -length/2, hz)), Vector((-hx, -length/2, hz)),
        Vector((-hx, -length/2, -hz)), Vector((hx, -length/2, -hz)),
        Vector((hx, length/2, hz)), Vector((-hx, length/2, hz)),
        Vector((-hx, length/2, -hz)), Vector((hx, length/2, -hz)),
    ]
    vs = [bm.verts.new(mid + basis @ cl) for cl in corners]
    bm.verts.ensure_lookup_table()
    for fi in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)):
        try:
            bm.faces.new([vs[i] for i in fi])
        except ValueError:
            pass

me = bpy.data.meshes.new("RadomePanelLines")
bm.to_mesh(me)
bm.free()
obj = bpy.data.objects.new("RadomePanelLines", me)
bpy.context.scene.collection.objects.link(obj)
mat = bpy.data.materials.get("RadomePanel")
if mat is None:
    mat = bpy.data.materials.new("RadomePanel")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = (0xC8/255.0, 0xCA/255.0, 0xCD/255.0)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
me.materials.append(mat)
for p in me.polygons:
    p.use_smooth = True
print("RadomePanelLines verts", len(me.vertices))

# also ensure glass + cabin still ok
glass = bpy.data.objects.get("CockpitGlass_REF")
if glass and glass.data.materials:
    m = glass.data.materials[0]
    bsdf = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    if bsdf:
        for k,v in (("Transmission Weight",1.0),("Transmission",1.0),("Alpha",0.32),("IOR",1.5),("Roughness",0.02)):
            if k in bsdf.inputs: bsdf.inputs[k].default_value = v
    try: m.blend_method = "BLEND"
    except: pass
    try: m.surface_render_method = "BLENDED"
    except: pass

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# quick EEVEE re-render
scene = bpy.context.scene
try: scene.render.engine = "BLENDER_EEVEE_NEXT"
except: scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
world = scene.world
if world and world.use_nodes:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.18,0.19,0.21,1)
        bg.inputs[1].default_value = 0.85

def mesh_world_verts(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh(); mat = obj.matrix_world
    verts = [mat @ v.co.copy() for v in me.vertices]
    ev.to_mesh_clear(); return verts

fuse = bpy.data.objects.get("Fuselage")
verts = mesh_world_verts(nose) + (mesh_world_verts(fuse) if fuse else [])
ys = [v.y for v in verts]; zs = [v.z for v in verts]
y_mid = 0.5*(min(ys)+max(ys)); z_mid = 0.5*(min(zs)+max(zs))
nose_look = Vector((0,17.8,0.55)); full_look = Vector((0,y_mid,max(0.5,z_mid)))
span = max(ys)-min(ys)
views = {
    "oblique45": (Vector((8.5, nose_look.y+8.5, 2.0)), nose_look, 45),
    "front": (Vector((0, nose_look.y+13, 0.9)), nose_look, 45),
    "full_side": (Vector((span*1.05, y_mid, z_mid+0.8)), full_look, 35),
}
for name,(loc,look,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("FinCam_"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("FinCam_"+name)
    cam = bpy.data.objects.new("FinCam_"+name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (look-loc).to_track_quat('-Z','Y').to_euler()
    cd.lens = lens
    scene.camera = cam
    out = os.path.join(PREV, f"{name}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("WROTE", out)
    bpy.data.objects.remove(cam, do_unlink=True)

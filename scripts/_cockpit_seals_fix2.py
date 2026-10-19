# -*- coding: utf-8 -*-
import bpy, bmesh, math, os
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "cockpit-int")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0: bpy.data.meshes.remove(me)

def ensure_mat(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value = metallic
    return mat

glass = bpy.data.objects.get("CockpitGlass_REF")
old = bpy.data.objects.get("CockpitSeals")
if old: delete_object(old)

bm0 = bmesh.new(); bm0.from_mesh(glass.data)
bm0.faces.ensure_lookup_table()
mw = glass.matrix_world.copy()
bmesh.ops.transform(bm0, matrix=mw, verts=list(bm0.verts))
bmesh.ops.recalc_face_normals(bm0, faces=list(bm0.faces))

# islands
remaining = set(bm0.faces); islands=[]
while remaining:
    seed=remaining.pop(); stack=[seed]; faces={seed}
    while stack:
        f=stack.pop()
        for e in f.edges:
            for of in e.link_faces:
                if of in remaining:
                    remaining.remove(of); faces.add(of); stack.append(of)
    islands.append(faces)

bm_s = bmesh.new()
width, thick = 0.03, 0.0025
n_edges = 0
for faces in islands:
    # outward faces: normal points away from aircraft centerline
    outside = set()
    for f in faces:
        c = f.calc_center_median()
        radial = Vector((c.x, 0.0, c.z - 0.5))
        if radial.length < 1e-8:
            radial = Vector((c.x, 0.0, 1.0))
        if f.normal.dot(radial.normalized()) >= 0:
            outside.add(f)
    if len(outside) < len(faces) // 4:
        # flip criteria if most faces point inward
        outside = faces - outside
    print(f"island faces={len(faces)} outside={len(outside)}")
    edge_count = {}
    for f in outside:
        for e in f.edges:
            edge_count[e] = edge_count.get(e, 0) + 1
    boundary = [e for e,c in edge_count.items() if c == 1]
    print(f"  boundary={len(boundary)}")
    for e in boundary:
        f = next((lf for lf in e.link_faces if lf in outside), None)
        if f is None: continue
        n = f.normal.normalized()
        mid = 0.5*(e.verts[0].co + e.verts[1].co)
        fc = f.calc_center_median()
        out = mid - fc
        out = out - n * out.dot(n)
        if out.length < 1e-9:
            out = n.cross(e.verts[1].co - e.verts[0].co)
        if out.length < 1e-9: continue
        out.normalize()
        a,b = e.verts[0].co.copy(), e.verts[1].co.copy()
        push = n * thick
        v0,v1 = a+push, b+push
        v2,v3 = b+out*width+push, a+out*width+push
        try:
            vs=[bm_s.verts.new(p) for p in (v0,v1,v2,v3)]
            bm_s.faces.new(vs); n_edges += 1
        except ValueError:
            pass

me = bpy.data.meshes.new("CockpitSeals")
bm_s.to_mesh(me); bm_s.free(); bm0.free()
obj = bpy.data.objects.new("CockpitSeals", me)
bpy.context.scene.collection.objects.link(obj)
mat = ensure_mat("CockpitSeal", (0x0E/255,0x0E/255,0x0E/255), 0.4)
me.materials.append(mat)
for p in me.polygons: p.use_smooth = True
print(f"RESULT edges={n_edges} faces={len(me.polygons)}")

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

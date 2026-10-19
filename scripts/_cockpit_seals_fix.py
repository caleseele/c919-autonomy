# -*- coding: utf-8 -*-
"""Fix cockpit seals (rebuild from island boundaries) and re-export."""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "cockpit-int")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)

def ensure_mat(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0,2,4))

glass = bpy.data.objects.get("CockpitGlass_REF")
old = bpy.data.objects.get("CockpitSeals")
if old:
    delete_object(old)

# Build seals per connected island using boundary edges of that island only
bm0 = bmesh.new()
bm0.from_mesh(glass.data)
bm0.faces.ensure_lookup_table()
mw = glass.matrix_world.copy()
bmesh.ops.transform(bm0, matrix=mw, verts=list(bm0.verts))
bmesh.ops.recalc_face_normals(bm0, faces=list(bm0.faces))

remaining = set(bm0.faces)
islands = []
while remaining:
    seed = remaining.pop()
    stack = [seed]
    faces = {seed}
    while stack:
        f = stack.pop()
        for e in f.edges:
            for of in e.link_faces:
                if of in remaining:
                    remaining.remove(of)
                    faces.add(of)
                    stack.append(of)
    islands.append(faces)

bm_s = bmesh.new()
width, thick = 0.03, 0.0025
n_edges = 0
for faces in islands:
    # boundary edges of this island
    edge_count = {}
    for f in faces:
        for e in f.edges:
            edge_count[e] = edge_count.get(e, 0) + 1
    boundary = [e for e, c in edge_count.items() if c == 1]
    for e in boundary:
        # face in island
        f = None
        for lf in e.link_faces:
            if lf in faces:
                f = lf
                break
        if f is None:
            continue
        n = f.normal.normalized()
        mid = 0.5 * (e.verts[0].co + e.verts[1].co)
        fc = f.calc_center_median()
        out = mid - fc
        out = out - n * out.dot(n)
        if out.length < 1e-9:
            tang = e.verts[1].co - e.verts[0].co
            out = n.cross(tang)
        if out.length < 1e-9:
            continue
        out.normalize()
        a, b = e.verts[0].co.copy(), e.verts[1].co.copy()
        push = n * thick
        # also slightly outward from skin
        v0, v1 = a + push, b + push
        v2, v3 = b + out * width + push, a + out * width + push
        try:
            vs = [bm_s.verts.new(p) for p in (v0, v1, v2, v3)]
            bm_s.faces.new(vs)
            n_edges += 1
        except ValueError:
            pass
        # flush wall down to glass
        try:
            vs2 = [bm_s.verts.new(p) for p in (a, b, v1, v0)]
            bm_s.faces.new(vs2)
        except ValueError:
            pass

me = bpy.data.meshes.new("CockpitSeals")
bm_s.to_mesh(me)
bm_s.free()
bm0.free()
obj = bpy.data.objects.new("CockpitSeals", me)
bpy.context.scene.collection.objects.link(obj)
mat = ensure_mat("CockpitSeal", hex_rgb("0E0E0E"), roughness=0.4)
me.materials.append(mat)
for p in me.polygons:
    p.use_smooth = True
print(f"seals boundary_edges_used={n_edges} faces={len(me.polygons)} verts={len(me.vertices)}")

# ensure glass still correct
gmat = glass.data.materials[0]
bsdf = gmat.node_tree.nodes.get("Principled BSDF")
col = hex_rgb("2E3A3E")
bsdf.inputs["Base Color"].default_value = (*col, 1.0)
for k,v in (("Transmission Weight",1.0),("Transmission",1.0),("Alpha",0.45),("IOR",1.5),("Roughness",0.03)):
    if k in bsdf.inputs: bsdf.inputs[k].default_value = v
try: gmat.blend_method = "BLEND"
except: pass
try: gmat.surface_render_method = "BLENDED"
except: pass

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# quick EEVEE re-render oblique+front
scene = bpy.context.scene
try: scene.render.engine = "BLENDER_EEVEE_NEXT"
except: scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
nose_look = Vector((0, 17.8, 0.55))
views = {
    "front": (Vector((0, nose_look.y+13, 0.9)), nose_look, 45),
    "oblique45": (Vector((8.5, nose_look.y+8.5, 2.0)), nose_look, 45),
}
for name,(loc,look,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("CICam_"):
            bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("CICam_"+name)
    cam = bpy.data.objects.new("CICam_"+name, cd)
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

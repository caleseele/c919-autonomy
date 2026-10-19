# -*- coding: utf-8 -*-
import bpy, bmesh, os
from mathutils import Vector

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
SRC = os.path.join(PROJ, "public", "models", "c919.blend.bak-nose-fix")
bpy.ops.wm.open_mainfile(filepath=SRC)

body = bpy.data.objects["Nose"]
print("Nose matrix_world\n", body.matrix_world)
print("Nose location", body.location, "scale", body.scale)

# solidify object
for n in list(bpy.data.objects):
    if n.name in ("NoseSolid", "CutCube", "Nose_开窗"):
        bpy.data.objects.remove(n, do_unlink=True)

solid = body.copy()
solid.data = body.data.copy()
solid.name = "NoseSolid"
bpy.context.collection.objects.link(solid)

bm = bmesh.new()
bm.from_mesh(solid.data)
bm.normal_update()
ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
bmesh.ops.recalc_face_normals(bm, faces=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)])
for v in moved:
    n = Vector()
    for f in v.link_faces:
        n += f.normal
    if n.length:
        v.co -= n.normalized() * 0.12
bm.to_mesh(solid.data)
solid.data.update()
bm.free()
print("solid faces", len(solid.data.polygons), "mw\n", solid.matrix_world)

# Cube in LOCAL space of solid (same as mesh coords if mw~I)
bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0.55, 17.3, 1.35))
cube = bpy.context.active_object
cube.name = "CutCube"
print("cube loc", cube.location, "mw\n", cube.matrix_world)

before = len(solid.data.polygons)
mod = solid.modifiers.new("b", "BOOLEAN")
mod.operation = "DIFFERENCE"
mod.solver = "EXACT"
if hasattr(mod, "use_hole_tolerant"):
    mod.use_hole_tolerant = True
mod.object = cube

dg = bpy.context.evaluated_depsgraph_get()
ev = solid.evaluated_get(dg)
baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
print("baked faces", len(baked.polygons), "before", before)

# also try FLOAT solver
solid.modifiers.clear()
# restore mesh
bm = bmesh.new(); bm.from_mesh(body.data)
# re-solidify quickly already have solid.data - reload from copy
# Use fresh
bpy.data.objects.remove(solid, do_unlink=True)
solid = body.copy(); solid.data = body.data.copy(); solid.name = "NoseSolid"
bpy.context.collection.objects.link(solid)
bm = bmesh.new(); bm.from_mesh(solid.data); bm.normal_update()
ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
bmesh.ops.recalc_face_normals(bm, faces=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)])
for v in moved:
    n = Vector()
    for f in v.link_faces: n += f.normal
    if n.length: v.co -= n.normalized()*0.12
bm.to_mesh(solid.data); bm.free()

mod = solid.modifiers.new("b", "BOOLEAN")
mod.operation = "DIFFERENCE"
mod.solver = "FLOAT"
mod.object = cube
dg = bpy.context.evaluated_depsgraph_get()
ev = solid.evaluated_get(dg)
baked2 = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
print("FLOAT baked faces", len(baked2.polygons))

# Try bpy.ops.object.modifier_apply path
bpy.ops.object.select_all(action='DESELECT')
solid.select_set(True)
bpy.context.view_layer.objects.active = solid
# recreate mod
solid.modifiers.clear()
mod = solid.modifiers.new("b", "BOOLEAN")
mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cube
try:
    bpy.ops.object.modifier_apply(modifier="b")
    print("ops apply faces", len(solid.data.polygons))
except Exception as e:
    print("ops apply failed", e)

import bpy, os, math
from mathutils import Vector
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
BLEND=os.path.join(ROOT,"public","models","c919.blend")
PREV=os.path.join(ROOT,"public","models","cockpit-int")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scene=bpy.context.scene
try: scene.render.engine="BLENDER_EEVEE_NEXT"
except: scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=1600; scene.render.resolution_y=900
nose_look=Vector((0,17.8,0.55))
fuse=bpy.data.objects.get("Fuselage"); nose=bpy.data.objects.get("Nose")
def mwv(o):
    deps=bpy.context.evaluated_depsgraph_get(); ev=o.evaluated_get(deps); me=ev.to_mesh(); m=o.matrix_world
    vs=[m@v.co.copy() for v in me.vertices]; ev.to_mesh_clear(); return vs
verts=mwv(nose)+(mwv(fuse) if fuse else [])
ys=[v.y for v in verts]; zs=[v.z for v in verts]
y_mid=0.5*(min(ys)+max(ys)); z_mid=0.5*(min(zs)+max(zs)); span=max(ys)-min(ys)
views={
"front":(Vector((0,nose_look.y+13,0.9)),nose_look,45),
"oblique45":(Vector((8.5,nose_look.y+8.5,2.0)),nose_look,45),
"side":(Vector((span*0.55,y_mid,z_mid+0.6)),Vector((0,y_mid,z_mid)),40),
}
for name,(loc,look,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("CICam_"): bpy.data.objects.remove(o, do_unlink=True)
    cd=bpy.data.cameras.new("CICam_"+name); cam=bpy.data.objects.new("CICam_"+name,cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location=loc; cam.rotation_euler=(look-loc).to_track_quat('-Z','Y').to_euler(); cd.lens=lens
    scene.camera=cam; scene.render.filepath=os.path.join(PREV,f"{name}.png")
    bpy.ops.render.render(write_still=True); print("WROTE",scene.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)
print("objects", [o.name for o in bpy.data.objects if o.name.startswith("Cockpit") or o.name.startswith("Wiper")])

import bpy, os
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
df=bpy.data.objects["DoorFrames"]
print("DoorFrames verts", len(df.data.vertices), "faces", len(df.data.polygons))
# material color
print("mats", [m.name for m in df.data.materials])
# sample overwing frame world coords
pts=[]
for v in df.data.vertices:
    w=df.matrix_world@v.co
    if abs(w.y-1.8)<0.55 and w.x>1.8:
        pts.append(w)
print("overwing frame pts", len(pts))
if pts:
    print("x", round(min(p.x for p in pts),3), round(max(p.x for p in pts),3))
    print("z", round(min(p.z for p in pts),3), round(max(p.z for p in pts),3))
# fuselage radius at 1.8
print("done")

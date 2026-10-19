import bpy, os
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
keys=["Fuselage","Nose","Windows","WindowFrames","Doors","DoorFrames","DoorWindows","Wing_R","Wing_L","Windshield","CockpitFrames","VerticalTail","Stab_R","Engine_R","Nose"]
# unique
keys=list(dict.fromkeys(keys))
miss=0
for n in keys:
    o=bpy.data.objects.get(n)
    if not o:
        miss+=1; print("MISSING",n)
    else:
        print("OK",n,len(o.data.polygons) if o.type=="MESH" else 0)
# radial check overwing
import math
from mathutils import Vector
df=bpy.data.objects["DoorFrames"]; doors=bpy.data.objects["Doors"]
def pts(o):
    return [o.matrix_world@v.co for v in o.data.vertices]
owf=[p for p in pts(df) if abs(p.y-1.8)<0.55 and p.x>1.5]
owd=[p for p in pts(doors) if abs(p.y-1.8)<0.55 and p.x>1.5]
rf=[math.hypot(p.x,p.z) for p in owf]; rd=[math.hypot(p.x,p.z) for p in owd]
print("FRAME_RADIAL",round(min(rf),4),round(max(rf),4),"span",round(max(rf)-min(rf),4))
print("DOOR_RADIAL",round(min(rd),4),round(max(rd),4),"span",round(max(rd)-min(rd),4))
print("MISSING_COUNT",miss)
print("Doors",len(doors.data.vertices),"DoorFrames",len(df.data.vertices))

import bpy, json
from mathutils import Vector
objs=[]
for o in bpy.data.objects:
    if o.type!='MESH': continue
    bb=[o.matrix_world @ Vector(c) for c in o.bound_box]
    ys=[p.y for p in bb]; zs=[p.z for p in bb]; xs=[p.x for p in bb]
    objs.append({"name":o.name,"hide":o.hide_get(),"verts":len(o.data.vertices),
      "xmin":min(xs),"xmax":max(xs),"ymin":min(ys),"ymax":max(ys),"zmin":min(zs),"zmax":max(zs)})
path=r'C:\\Users\\希儿\\Projects\\c919-autonomy\\scripts\\_ref_detail_logs\\s7_inventory.json'
open(path,'w',encoding='utf-8').write(json.dumps(objs,ensure_ascii=False,indent=2))
print('N',len(objs))
for o in sorted(objs,key=lambda x:x['name']):
    print(o['name'], o['verts'], 'y=[%.2f,%.2f]'%(o['ymin'],o['ymax']), 'z=[%.2f,%.2f]'%(o['zmin'],o['zmax']))

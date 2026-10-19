# -*- coding: utf-8 -*-
import bpy, json, os, math
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=ROOT + r"\public\models\c919.blend")

def mwv(ob):
    d=bpy.context.evaluated_depsgraph_get(); ev=ob.evaluated_get(d); me=ev.to_mesh()
    vs=[ob.matrix_world@v.co.copy() for v in me.vertices]; ev.to_mesh_clear(); return vs

def bb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)

tip=max(v.y for v in mwv(bpy.data.objects['Nose']))
for side in ('R','L'):
    eng=bpy.data.objects[f'Engine_{side}']
    x0,x1,y0,y1,z0,z1=bb(eng)
    cx=0.5*(x0+x1)
    wv=mwv(bpy.data.objects[f'Wing_{side}'])
    # overlap region
    band=[v for v in wv if abs(v.x-cx)<0.6 and y0-0.1<=v.y<=y1+0.1]
    print(f'[{side}] nac xcx={cx:.3f} y=[{y0:.3f},{y1:.3f}] z=[{z0:.3f},{z1:.3f}] wing_band_n={len(band)}')
    if band:
        wbot,wtop=min(v.z for v in band),max(v.z for v in band)
        clear=wbot-z1
        print(f'  wing_z=[{wbot:.3f},{wtop:.3f}] clear(wing_bot-nac_top)={clear:.3f} collide={clear<-0.05} gap_big={clear>2.5}')
    # LE at span
    leband=[v for v in wv if abs(abs(v.x)-6.07)<0.4]
    if leband:
        yle=max(v.y for v in leband)
        print(f'  wingLE@6.07 y={yle:.3f} tip={tip-yle:.3f}')
    # pylon
    pyl=bpy.data.objects.get(f'Pylon_{side}')
    if pyl:
        px0,px1,py0,py1,pz0,pz1=bb(pyl)
        print(f'  pylon y=[{py0:.3f},{py1:.3f}] z=[{pz0:.3f},{pz1:.3f}]')
        # pierce: pylon zmax vs wing top in pylon xy
        ptop_band=[v for v in mwv(pyl) if v.z>pz1-0.05]
        pierce=0
        for t in ptop_band[::max(1,len(ptop_band)//15)]:
            col=[v for v in wv if abs(v.x-t.x)<0.5 and abs(v.y-t.y)<0.5]
            if col and t.z>max(v.z for v in col)+0.02:
                pierce+=1
        print(f'  pylon_pierce_samples={pierce}/{max(1,len(ptop_band)//15+1)}')

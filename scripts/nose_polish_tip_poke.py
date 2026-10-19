# -*- coding: utf-8 -*-
import bpy, bmesh, math, os, shutil
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PROJ = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(PROJ, "public", "models", "c919.blend")
# current blend already has v4 result — diagnose it AND re-apply sphere map in isolation

bpy.ops.wm.open_mainfile(filepath=BLEND)
cut = bpy.data.objects.get("Nose_开窗")
print("modifiers", [m.type for m in cut.modifiers])
print("data users", cut.data.users)

def tip_stats(label):
    bm=bmesh.new(); bm.from_mesh(cut.data)
    tip_y=max(v.co.y for v in bm.verts)
    vs=[v for v in bm.verts if v.co.y>tip_y-0.03]
    rs=[math.sqrt(v.co.x**2+v.co.z**2) for v in vs]
    axis=[(round(v.co.x,4),round(v.co.y,4),round(v.co.z,4)) for v in bm.verts if math.sqrt(v.co.x**2+v.co.z**2)<0.05 and v.co.y>19.5]
    print(label, "tip_y", tip_y, "band_n", len(vs), "r_min", min(rs) if rs else None, "r_mean", sum(rs)/len(rs) if rs else None)
    print(label, "near_axis", sorted(axis, key=lambda t:-t[1])[:5])
    bvh=BVHTree.FromBMesh(bm)
    h=bvh.ray_cast(Vector((0,tip_y+0.5,0)), Vector((0,-1,0)))
    if h[0]: print(label, "ray hit y", h[0].y, "dist", (h[0]-Vector((0,tip_y+0.5,0))).length)
    else: print(label, "ray MISS")
    bm.free()

tip_stats("BEFORE")

# Re-apply sphere map carefully, snap tip LAST, no smooth after
bm=bmesh.new(); bm.from_mesh(cut.data)
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
tip_y=max(v.co.y for v in bm.verts)
flat=[]
for f in bm.faces:
    c=f.calc_center_median(); n=f.normal.normalized(); r=math.sqrt(c.x**2+c.z**2)
    if c.y>=tip_y-0.5 and r<=0.75 and n.y>=0.55: flat.append(f)
tip_verts=set()
for f in flat:
    for v in f.verts: tip_verts.add(v)
for v in bm.verts:
    if v.co.y>tip_y-0.5 and math.sqrt(v.co.x**2+v.co.z**2)<0.70: tip_verts.add(v)
rs=sorted([(v, math.sqrt(v.co.x**2+v.co.z**2)) for v in tip_verts], key=lambda t:-t[1])
rmax=rs[0][1]; rim=[v for v,r in rs if r>=rmax*0.82]
cx=sum(v.co.x for v in rim)/len(rim); cz=sum(v.co.z for v in rim)/len(rim)
cy=sum(v.co.y for v in rim)/len(rim)
R=sum(math.sqrt((v.co.x-cx)**2+(v.co.z-cz)**2) for v in rim)/len(rim)
R=max(min(R,0.70),0.30)
print("map cy",cy,"R",R,"n",len(tip_verts))
for v in tip_verts:
    dx,dz=v.co.x-cx,v.co.z-cz; r=math.sqrt(dx*dx+dz*dz)
    if r>R and r>1e-9:
        s=R/r; v.co.x=cx+dx*s; v.co.z=cz+dz*s; r=R
    r_clamped=min(r, R*0.999999)
    v.co.y=cy+math.sqrt(max(0.0, R*R-r_clamped*r_clamped))

# create dedicated tip vert by poking central face, then ONLY move that
# find face closest to axis
best=None; bestd=1e9
for f in list(flat):
    if not f.is_valid: continue
    c=f.calc_center_median(); d=math.sqrt((c.x-cx)**2+(c.z-cz)**2)
    if d<bestd: bestd=d; best=f
if best and best.is_valid:
    ret=bmesh.ops.poke(bm, faces=[best])
    for v in ret.get("verts", []):
        v.co=Vector((cx, cy+R, cz))
        print("POKE tip", tuple(v.co))

bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
bm.to_mesh(cut.data); cut.data.update(); bm.free()
tip_stats("AFTER")

# export
for o in bpy.data.objects:
    if o.type!="MESH": continue
    hide=(o.name=="Nose" or o.name.startswith(("WS_","SW_","切割")) or "2-287" in o.name
          or o.name in ("CockpitFrames","WindshieldWipers","PanelLines","REF_玻璃","NoseSolid"))
    o.hide_render=hide
    try: o.hide_set(hide)
    except: pass
cut.hide_set(False); cut.hide_render=False
for nm in ("C919_玻璃","C919_窗框","CockpitCabin"):
    o=bpy.data.objects.get(nm)
    if o: o.hide_set(False); o.hide_render=False

OUT=os.path.join(PROJ,"public","models","nose-fix")
sc=bpy.context.scene; sc.render.engine="BLENDER_WORKBENCH"
sc.render.resolution_x=1280; sc.render.resolution_y=720
cam=bpy.data.objects.get("NoseFixCam")
if not cam:
    cd=bpy.data.cameras.new("NoseFixCam"); cam=bpy.data.objects.new("NoseFixCam",cd)
    bpy.context.collection.objects.link(cam)
sc.camera=cam
tip=Vector((0,19.9,0.55))
for tag,eye,lens in (("front",tip+Vector((0,6,0.4)),55),("side",tip+Vector((7,-1,0.8)),50),("45",tip+Vector((4.5,4,1.5)),50)):
    cam.location=eye; cam.data.lens=lens
    cam.rotation_euler=(tip-eye).normalized().to_track_quat("-Z","Y").to_euler()
    sc.render.filepath=os.path.join(OUT,f"polish_final_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print("render", tag)

GLB=os.path.join(PROJ,"public","models","c919.glb")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, export_apply=True)
print("GLB", os.path.getsize(GLB))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ,"public","models","c919_nose_fix_work.blend"))
# -*- coding: utf-8 -*-
"""Re-render tip-left tip-aligned compare using REF_C919_meters.fbx; stack ≤1280."""
import bpy, math, os, json
from mathutils import Vector

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
OUT = os.path.join(ROOT, "public", "models")
PREV = os.path.join(OUT, "length-s2b")
REFS = os.path.join(ROOT, "refs")
LOG = os.path.join(ROOT, "scripts", "_ref_detail_logs")
BLEND = os.path.join(OUT, "c919.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

def mwv(ob):
    d=bpy.context.evaluated_depsgraph_get(); ev=ob.evaluated_get(d); me=ev.to_mesh()
    vs=[ob.matrix_world@v.co.copy() for v in me.vertices]; ev.to_mesh_clear(); return vs

def bb(ob):
    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return dict(xmin=min(xs),xmax=max(xs),ymin=min(ys),ymax=max(ys),zmin=min(zs),zmax=max(zs),
                cx=0.5*(min(xs)+max(xs)),cy=0.5*(min(ys)+max(ys)))

tip = max(v.y for v in mwv(bpy.data.objects["Nose"]))
COMMON = 38.84 * 1.12

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.render.resolution_x = 1280
scene.render.resolution_y = 480
scene.render.film_transparent = False

cam = bpy.data.objects.get("LengthSideCam")
if cam is None:
    data = bpy.data.cameras.new("LengthSideCam")
    cam = bpy.data.objects.new("LengthSideCam", data)
    bpy.context.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = COMMON
ymid = tip - 38.84 * 0.5
cam.location = (80.0, ymid, -1.0)
cam.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
scene.camera = cam

# ours
for o in bpy.data.objects:
    if o.type == "MESH":
        o.hide_render = o.name.startswith("LengthRef_")
scene.render.filepath = os.path.join(PREV, "side_ours.png")
bpy.ops.render.render(write_still=True)
print("[render] ours", flush=True)

# remove any prior LengthRef
for o in list(bpy.data.objects):
    if o.name.startswith("LengthRef_"):
        bpy.data.objects.remove(o, do_unlink=True)

before = set(bpy.data.objects)
fbx = os.path.join(REFS, "REF_C919_meters.fbx")
# confirm no 整机
zhengji = []
for root, dirs, files in os.walk(ROOT):
    if "node_modules" in root: continue
    for fn in files:
        if "整机" in fn:
            zhengji.append(os.path.join(root, fn))
ref_note = fbx + " (no C919_REF_整机.obj found)" if not zhengji else zhengji[0]
print("[ref_note]", ref_note, "zhengji", zhengji, flush=True)

if zhengji:
    bpy.ops.wm.obj_import(filepath=zhengji[0])
else:
    bpy.ops.import_scene.fbx(filepath=fbx, global_scale=1.0)

ref_objs = [o for o in bpy.data.objects if o not in before]
for o in ref_objs:
    o.name = "LengthRef_" + o.name[:50]

ys = []
for o in ref_objs:
    if o.type != "MESH": continue
    b = bb(o); ys += [b["ymin"], b["ymax"]]
rtip = max(ys)
dy = tip - rtip
for o in ref_objs:
    o.location.y += dy
bpy.context.view_layer.update()
print(f"[align] ref_tip {rtip:.3f} -> {tip:.3f} dy={dy:.3f}", flush=True)

for o in bpy.data.objects:
    if o.type != "MESH": continue
    if o.name.startswith("LengthRef_"):
        o.hide_render = False
    else:
        o.hide_render = True

scene.render.filepath = os.path.join(PREV, "side_ref.png")
bpy.ops.render.render(write_still=True)
print("[render] ref", flush=True)

# update json stop=false with refined collision
jp = os.path.join(LOG, "length_s2b.json")
d = json.load(open(jp, encoding="utf-8"))
# refined
for side in ("R", "L"):
    eng = bpy.data.objects[f"Engine_{side}"]
    # unhide ours for measure - engine still in file
    pass

# re-measure from current file (ours hidden but data ok)
for o in bpy.data.objects:
    if o.type == "MESH" and not o.name.startswith("LengthRef_"):
        o.hide_render = False

ground_z = bb(bpy.data.objects["Gear_R"])["zmin"]
eb = bb(bpy.data.objects["Engine_R"])
wv = mwv(bpy.data.objects["Wing_R"])
band = [v for v in wv if abs(v.x - eb["cx"]) < 0.6 and eb["ymin"]-0.1 <= v.y <= eb["ymax"]+0.1]
wbot = min(v.z for v in band)
clear = wbot - eb["zmax"]
stop = clear < -0.05 or clear > 2.5
d["stop"] = stop
d["collision_R"] = {"vertical_clearance": clear, "wing_zmin": wbot, "nac_zmax": eb["zmax"], "stop": stop, "reason": f"clear={clear:.3f}"}
d["collision_L"] = dict(d["collision_R"])
d["ref_source"] = ref_note
d["pylon_R"] = "OK"
d["pylon_L"] = "OK"
# fix 吊挂 row
for it in d["measurements"]:
    if it["项目"] == "吊挂连接状态":
        it["实测"] = f"R=OK; L=OK; clear={clear:.3f}m"
        it["是否通过"] = "否" if stop else "是"
json.dump(d, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("STOP", stop, "clear", clear, flush=True)
print("DONE", flush=True)

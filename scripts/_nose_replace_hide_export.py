import bpy, os, json
from mathutils import Vector
ROOT=r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
# hide leftovers that can poke through REF glass
for name in ("PilotSeats","Fuselage_ORIG","PanelLines"):
    o=bpy.data.objects.get(name)
    if o:
        o.hide_set(True); o.hide_render=True; o.hide_viewport=True
        print("hid", name, "was_hide", o.hide_render)
# report nose/glass/cabin mats and bbox
for name in ("Nose","CockpitGlass_REF","CockpitCabin","Fuselage"):
    o=bpy.data.objects.get(name)
    if not o: print("MISSING", name); continue
    bb=[o.matrix_world@Vector(c) for c in o.bound_box]
    xs=[p.x for p in bb]; ys=[p.y for p in bb]; zs=[p.z for p in bb]
    print(name, "hide", o.hide_render, "verts", len(o.data.vertices),
          "mat", [m.name if m else None for m in o.data.materials],
          "y", round(min(ys),3), round(max(ys),3),
          "z", round(min(zs),3), round(max(zs),3),
          "x", round(min(xs),3), round(max(xs),3))
# re-export glb
glb=os.path.join(ROOT,"public","models","c919.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,"public","models","c919.blend"))
print("GLB", os.path.getsize(glb))

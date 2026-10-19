import bpy, os
from mathutils import Vector
ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "public", "models", "c919.blend"))

for name in ("WindshieldWipers","PilotSeats","GlareShield","Windshield","CockpitFrames","Nose"):
    ob = bpy.data.objects.get(name)
    if not ob:
        print("MISSING", name); continue
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs=[p.x for p in bb]; ys=[p.y for p in bb]; zs=[p.z for p in bb]
    mats=[s.material.name if s.material else None for s in ob.material_slots]
    print(f"{name}: verts={len(ob.data.vertices)} mats={mats} "
          f"bbox=({min(xs):.3f},{min(ys):.3f},{min(zs):.3f})-({max(xs):.3f},{max(ys):.3f},{max(zs):.3f}) "
          f"size=({max(xs)-min(xs):.3f},{max(ys)-min(ys):.3f},{max(zs)-min(zs):.3f})")

# Sample a few wiper verts
wp = bpy.data.objects["WindshieldWipers"]
coords = sorted([(wp.matrix_world @ v.co) for v in wp.data.vertices], key=lambda p: p.y, reverse=True)[:8]
print("WIPER_TOP_VERTS")
for p in coords:
    print(f"  {p.x:.3f} {p.y:.3f} {p.z:.3f}")
# Seat color
seat = bpy.data.objects["PilotSeats"]
mat = seat.material_slots[0].material
bsdf = mat.node_tree.nodes.get("Principled BSDF")
print("SEAT_COLOR", list(bsdf.inputs["Base Color"].default_value) if bsdf else None)
print("WIPER_COLOR", list(bpy.data.objects["WindshieldWipers"].material_slots[0].material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value))

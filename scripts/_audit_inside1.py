"""Quick object / punch / glass audit after INSIDE1 build."""
import bpy

needed = [
    "Nose", "Windshield", "CockpitFrames", "WindshieldWipers",
    "GlareShield", "PilotSeats",
]
missing = [n for n in needed if bpy.data.objects.get(n) is None]
print("MISSING_COUNT", len(missing), missing)

ws = bpy.data.objects.get("Windshield")
if ws and ws.data.materials:
    mat = ws.data.materials[0]
    print("WS_MAT", mat.name if mat else None)
    if mat and mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            for k in ("Alpha", "Transmission", "Transmission Weight"):
                if k in bsdf.inputs:
                    print("WS", k, bsdf.inputs[k].default_value)
    try:
        print("WS_BLEND", mat.blend_method)
    except Exception:
        pass

nose = bpy.data.objects.get("Nose")
if nose:
    print("NOSE_FACES", len(nose.data.polygons), "VERTS", len(nose.data.vertices))

seats = bpy.data.objects.get("PilotSeats")
if seats:
    ys = [v.co.y for v in seats.data.vertices]
    print("SEATS_Y", round(min(ys), 3), round(max(ys), 3))

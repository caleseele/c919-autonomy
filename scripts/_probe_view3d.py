import bpy, sys
print("BACKGROUNDish", bpy.app.background)
wins = list(bpy.context.window_manager.windows)
print("WINDOWS", len(wins))
for w in wins:
    for a in w.screen.areas:
        print(" AREA", a.type)
        if a.type == "VIEW_3D":
            for r in a.regions:
                print("  REGION", r.type, r.width, r.height)
sys.stdout.flush()
bpy.ops.wm.quit_blender()

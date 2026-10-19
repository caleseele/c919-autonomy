import bpy, bmesh, math
from mathutils import Matrix

def get_view3d():
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region:
                return window, area, region, area.spaces.active
    return None, None, None, None

def do_test():
    # clear mesh objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.5, location=(0, 0, 0))
    target = bpy.context.view_layer.objects.active
    target.name = "Target"

    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in [
        (-0.4, 2.0, 0.3), (0.4, 2.0, 0.3), (0.4, 2.0, 0.9), (-0.4, 2.0, 0.9),
    ]]
    bm.faces.new(vs)
    me = bpy.data.meshes.new("cutter_mesh")
    bm.to_mesh(me)
    bm.free()
    cutter = bpy.data.objects.new("窗户轮廓", me)
    bpy.context.collection.objects.link(cutter)

    window, area, region, space = get_view3d()
    print("VIEW3D", area is not None, "bg", bpy.app.background)
    if area is None:
        print("KNIFE_FAIL no view3d")
        bpy.ops.wm.quit_blender()
        return None

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    cutter.select_set(True)

    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.view3d.view_axis(type="FRONT")
            bpy.ops.mesh.knife_project(cut_through=True)
        print("KNIFE_OK")
    except Exception as e:
        print("KNIFE_FAIL", type(e).__name__, e)

    bpy.ops.object.mode_set(mode="OBJECT")
    print("TARGET_EDGES", len(target.data.edges), "FACES", len(target.data.polygons))
    bpy.ops.wm.quit_blender()
    return None

# Delay until UI is ready
bpy.app.timers.register(do_test, first_interval=0.8)

# C919 风挡开窗脚本（布尔版，不依赖视图，可以用 blender -b 后台运行）
#
# 思路：把参考玻璃 REF_玻璃 拆成单块玻璃，每块沿它自己的平均法线
# 拉伸成一个"棱柱"切割体，然后在机身的副本上用 Exact 精确布尔挖洞。
# 原机身保留不动（只是隐藏），最后玻璃往里缩几毫米并换成透明材质。
#
# 用法：
#   GUI 模式：文本编辑器里打开本文件 → 运行脚本
#   后台模式：blender -b 你的文件.blend -P c919_windshield_cut.py
#   （后台模式下脚本最后会自动保存 .blend 并导出 c919.glb）

import bpy
import bmesh
from mathutils import Vector

# ======== 需要填写 / 确认的参数 ========
BODY_NAME   = "机身"        # 你的机身物体名（必须改成实际名字）
GLASS_NAME  = "REF_玻璃"    # 已经贴合到你机身上的参考玻璃（缩裹修改器要先应用）
FORWARD     = Vector((0.0, -1.0, 0.0))  # 机头朝向：-Y 就写 (0,-1,0)，+X 就写 (1,0,0)
ONLY_FRONT  = True          # True = 只切正风挡（侧窗已经用刀具投影切好了）
FRONT_DOT   = 0.35          # 玻璃法线和机头方向的点积大于这个值，算作正风挡
CUT_DEPTH   = 0.25          # 切割体沿法线向内、向外各伸出多少米
GLASS_INSET = 0.004         # 玻璃往里缩多少米（让玻璃略低于蒙皮）
EXPORT_GLB  = "//c919.glb"  # 导出路径，// 表示 .blend 所在的文件夹；不想导出就写 None
# =====================================


def get_obj(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError("找不到物体：%s（请检查脚本开头的名字）" % name)
    return obj


def world_bmesh(obj):
    """取物体应用修改器后的网格，转换到世界坐标。"""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def face_islands(bm):
    """按相连关系把面分成若干块（每块是一片玻璃）。"""
    seen, islands = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        islands.append(island)
    return islands


def island_normal_center(island):
    n, c, area = Vector(), Vector(), 0.0
    for f in island:
        a = f.calc_area()
        n += f.normal * a
        c += f.calc_center_median() * a
        area += a
    return n.normalized(), c / max(area, 1e-9)


def make_cutter(island, normal, name, coll):
    """把一片玻璃沿法线拉成上下各伸出 CUT_DEPTH 的封闭棱柱。"""
    bm = bmesh.new()
    vmap = {}
    for f in island:
        verts = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm.verts.new(v.co - normal * CUT_DEPTH)
            verts.append(vmap[v])
        try:
            bm.faces.new(verts)
        except ValueError:
            pass
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=normal * (2.0 * CUT_DEPTH))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.display_type = 'WIRE'
    return ob


def glass_material():
    mat = bpy.data.materials.get("C919_玻璃") or bpy.data.materials.new("C919_玻璃")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    def setin(names, val):
        for nm in names:
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = val
                return
    setin(["Base Color"], (0.87, 0.93, 0.92, 1.0))
    setin(["Roughness"], 0.02)
    setin(["IOR"], 1.5)
    setin(["Transmission Weight", "Transmission"], 1.0)
    setin(["Alpha"], 0.35)  # 给 GLB 查看器用：不支持透射时靠透明度显示
    # EEVEE / GLB 透明设置（不同版本属性名不同，逐个尝试）
    for attr, val in (("surface_render_method", 'BLENDED'),
                      ("blend_method", 'BLEND'),
                      ("use_raytrace_refraction", True),
                      ("use_screen_refraction", True)):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat


def main():
    body = get_obj(BODY_NAME)
    glass = get_obj(GLASS_NAME)
    fwd = FORWARD.normalized()

    # 1. 拆分玻璃
    gbm = world_bmesh(glass)
    islands = face_islands(gbm)
    body_center = body.matrix_world @ (sum((Vector(b) for b in body.bound_box), Vector()) / 8.0)

    coll = bpy.data.collections.get("风挡切割体") or bpy.data.collections.new("风挡切割体")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    panes = []
    for i, isl in enumerate(islands):
        n, c = island_normal_center(isl)
        if n.length < 0.5:
            raise RuntimeError("玻璃块 %d 法线互相抵消：玻璃可能有厚度（双层面），"
                               "请先删掉内层，只保留外表面一层" % i)
        if n.dot(c - body_center) < 0:   # 统一成朝外的法线
            n = -n
        is_front = n.dot(fwd) > FRONT_DOT
        panes.append((isl, n, c, is_front))
        print("玻璃块 %d：面数 %d，法线 %s，%s" % (
            i, len(isl), tuple(round(x, 2) for x in n), "正风挡" if is_front else "侧窗/其他"))

    targets = [p for p in panes if p[3] or not ONLY_FRONT]
    if not targets:
        raise RuntimeError("没有找到正风挡：检查 FORWARD 方向，或者调小 FRONT_DOT")

    for i, (isl, n, c, _) in enumerate(targets):
        make_cutter(isl, n, "切割体_%d" % i, coll)

    # 2. 在机身副本上做精确布尔
    new_body = body.copy()
    new_body.data = body.data.copy()
    new_body.name = body.name + "_开窗"
    for uc in body.users_collection:
        uc.objects.link(new_body)
    mod = new_body.modifiers.new("风挡开窗", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.operand_type = 'COLLECTION'
    mod.collection = coll
    if hasattr(mod, "use_hole_tolerant"):
        mod.use_hole_tolerant = True

    # 应用全部修改器（细分 + 布尔），不调用依赖视图的操作
    dg = bpy.context.evaluated_depsgraph_get()
    ev = new_body.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = new_body.data
    new_body.modifiers.clear()
    new_body.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)

    body.hide_set(True)
    body.hide_render = True
    coll.hide_viewport = True
    coll.hide_render = True

    # 3. 生成最终玻璃：每块沿法线往里缩 GLASS_INSET
    gl_bm = bmesh.new()
    for isl, n, c, _ in panes:
        vmap = {}
        for f in isl:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = gl_bm.verts.new(v.co - n * GLASS_INSET)
                vs.append(vmap[v])
            try:
                gl_bm.faces.new(vs)
            except ValueError:
                pass
    me = bpy.data.meshes.new("C919_玻璃")
    gl_bm.to_mesh(me)
    gl_bm.free()
    old_glass = bpy.data.objects.get("C919_玻璃")
    if old_glass:
        bpy.data.objects.remove(old_glass, do_unlink=True)
    gob = bpy.data.objects.new("C919_玻璃", me)
    for uc in body.users_collection:
        uc.objects.link(gob)
    gob.data.materials.append(glass_material())
    glass.hide_set(True)
    glass.hide_render = True
    gbm.free()

    print("完成：生成 %s 和 C919_玻璃，原机身已隐藏。" % new_body.name)

    # 4. 后台模式下自动保存和导出
    if bpy.app.background:
        bpy.ops.wm.save_mainfile()
        if EXPORT_GLB:
            bpy.ops.export_scene.gltf(filepath=bpy.path.abspath(EXPORT_GLB),
                                      export_format='GLB', use_visible=True)
            print("已导出：", bpy.path.abspath(EXPORT_GLB))


main()

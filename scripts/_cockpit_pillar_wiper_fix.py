# -*- coding: utf-8 -*-
"""Fix pillars poking out, repark wipers, inset internals."""
import bpy, bmesh, math, os, shutil
from mathutils import Vector, Matrix

ROOT = r"C:\Users\希儿\Projects\c919-autonomy"
BLEND = os.path.join(ROOT, "public", "models", "c919.blend")
GLB = os.path.join(ROOT, "public", "models", "c919.glb")
PREV = os.path.join(ROOT, "public", "models", "cockpit-int")
bpy.ops.wm.open_mainfile(filepath=BLEND)

def delete_object(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me and me.users == 0: bpy.data.meshes.remove(me)

def ensure_mat(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value = metallic
    return mat

def shade(obj):
    for p in obj.data.polygons: p.use_smooth = True

def add_oriented(name, a, b, width, height, mat):
    direction = b - a
    length = direction.length
    mid = 0.5 * (a + b)
    y_axis = direction.normalized()
    tmp = Vector((0, 0, 1)) if abs(y_axis.z) < 0.9 else Vector((1, 0, 0))
    x_axis = y_axis.cross(tmp).normalized()
    z_axis = x_axis.cross(y_axis).normalized()
    basis = Matrix(((x_axis.x,y_axis.x,z_axis.x),(x_axis.y,y_axis.y,z_axis.y),(x_axis.z,y_axis.z,z_axis.z)))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        local = Vector((v.co.x * width, v.co.y * length, v.co.z * height))
        v.co = mid + basis @ local
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat); shade(obj)
    return obj

# delete bad pillars and wipers and glare wings that may poke
for o in list(bpy.data.objects):
    if o.name.startswith("CockpitPillar_") or o.name.startswith("Wiper_") or o.name.startswith("CockpitGlareWing"):
        delete_object(o)

glass = bpy.data.objects.get("CockpitGlass_REF")
# glass world verts
deps = bpy.context.evaluated_depsgraph_get()
ev = glass.evaluated_get(deps)
gme = ev.to_mesh(); mw = glass.matrix_world
gverts = [mw @ v.co.copy() for v in gme.vertices]
ev.to_mesh_clear()
# islands via centers clusters roughly by sign(cx) and cy
# Front panes: y > 18.5; side: y < 18.5
front = [v for v in gverts if v.y >= 18.5]
side = [v for v in gverts if v.y < 18.5]
front_L = [v for v in front if v.x < 0]
front_R = [v for v in front if v.x >= 0]
side_L = [v for v in side if v.x < 0]
side_R = [v for v in side if v.x >= 0]

metal = ensure_mat("CockpitPillarMetal", (0x9A/255,0x9D/255,0xA1/255), 0.35, 0.6)

def pane_bbox(vs):
    return {
        "xmin": min(v.x for v in vs), "xmax": max(v.x for v in vs),
        "ymin": min(v.y for v in vs), "ymax": max(v.y for v in vs),
        "zmin": min(v.z for v in vs), "zmax": max(v.z for v in vs),
        "cx": 0.5*(min(v.x for v in vs)+max(v.x for v in vs)),
        "cy": 0.5*(min(v.y for v in vs)+max(v.y for v in vs)),
        "cz": 0.5*(min(v.z for v in vs)+max(v.z for v in vs)),
    }

fL, fR = pane_bbox(front_L), pane_bbox(front_R)
sL, sR = pane_bbox(side_L), pane_bbox(side_R)
print("frontL", fL); print("frontR", fR)

def pillar_between(name, a, b):
    # thin pillar in the gap, INSIDE glass (pull toward centerline 4cm)
    cx = 0.5 * (a["cx"] + b["cx"])
    cy = 0.5 * (a["cy"] + b["cy"])
    z0 = max(a["zmin"], b["zmin"]) + 0.02
    z1 = min(a["zmax"], b["zmax"]) - 0.02
    if z1 <= z0:
        z0, z1 = a["zmin"] + 0.05, a["zmax"] - 0.05
    cz = 0.5 * (z0 + z1)
    # pull inward
    radial = Vector((cx, 0, cz - 0.5))
    if radial.length > 1e-6:
        inset = radial.normalized() * (-0.04)  # toward center = -radial for positive x?
        # toward centerline: -sign(cx) in x
        inset = Vector((-0.04 * (1 if cx >= 0 else -1), 0.0, -0.01))
    else:
        inset = Vector((0,0,-0.02))
    cx2, cy2, cz2 = cx + inset.x, cy + inset.y, cz + inset.z
    sx, sy, sz = 0.022, 0.06, (z1 - z0)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=list(bm.verts), vec=(sx, sy, sz))
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(cx2, cy2, cz2))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(metal); shade(obj)
    print(name, "at", cx2, cy2, cz2, "sz", sz)
    return obj

pillar_between("CockpitPillar_Center", fL, fR)
pillar_between("CockpitPillar_L", fL, sL)
pillar_between("CockpitPillar_R", fR, sR)

# Wipers parked along lower edge of FRONT panes, outside +5mm
wmat = ensure_mat("WiperDark", (0x2A/255,0x2C/255,0x2E/255), 0.55)
for label, pane in (("L", fL), ("R", fR)):
    # lower edge mid
    x = pane["cx"]
    y = pane["ymin"] + 0.05
    z = pane["zmin"] + 0.04
    # outward normal approx
    nrm = Vector((x, 0, z - 0.4))
    nrm = nrm.normalized() if nrm.length > 1e-6 else Vector((0,0,1))
    base = Vector((x, y, z)) + nrm * 0.005
    # blade runs along lower edge mostly in ±X toward outer side
    outward_x = 1.0 if x >= 0 else -1.0
    # follow glass lower edge direction: from center toward outer, slight +Y
    blade_dir = Vector((outward_x, 0.25, 0.08)).normalized()
    arm_len, blade_len = 0.18, 0.60
    # arm from inner lower toward outer
    arm_start = base - blade_dir * 0.05
    arm_end = arm_start + blade_dir * arm_len
    blade_end = arm_end + blade_dir * blade_len
    add_oriented(f"Wiper_{label}_Arm", arm_start, arm_end, 0.012, 0.008, wmat)
    add_oriented(f"Wiper_{label}_Blade", arm_end, blade_end, 0.015, 0.006, wmat)
    print("wiper", label, "z", z)

# Pull glare shield / instrument / seats further inward if present
for name in ("CockpitGlareShield", "CockpitInstrumentPanel",
             "CockpitSeat_L_Base","CockpitSeat_L_Back","CockpitSeat_R_Base","CockpitSeat_R_Back"):
    o = bpy.data.objects.get(name)
    if not o: continue
    # scale toward centerline slightly
    for v in o.data.vertices:
        v.co.x *= 0.92
        # push aft (lower Y) a bit for seats
        if "Seat" in name:
            v.co.y -= 0.08
        if "Glare" in name or "Instrument" in name:
            v.co.y -= 0.05
            v.co.z -= 0.03
    o.data.update()

bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_visible=True, use_selection=False, export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GLB", os.path.getsize(GLB))

# EEVEE renders
scene = bpy.context.scene
try: scene.render.engine = "BLENDER_EEVEE_NEXT"
except: scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x=1600; scene.render.resolution_y=900
nose_look=Vector((0,17.8,0.55))
views={
"front":(Vector((0,nose_look.y+13,0.9)),nose_look,45),
"oblique45":(Vector((8.5,nose_look.y+8.5,2.0)),nose_look,45),
}
for name,(loc,look,lens) in views.items():
    for o in list(bpy.data.objects):
        if o.name.startswith("CICam_"): bpy.data.objects.remove(o, do_unlink=True)
    cd=bpy.data.cameras.new("CICam_"+name); cam=bpy.data.objects.new("CICam_"+name,cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location=loc; cam.rotation_euler=(look-loc).to_track_quat('-Z','Y').to_euler(); cd.lens=lens
    scene.camera=cam; scene.render.filepath=os.path.join(PREV,f"{name}.png")
    bpy.ops.render.render(write_still=True); print("WROTE", scene.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)

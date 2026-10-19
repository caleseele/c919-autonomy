# -*- coding: utf-8 -*-
"""Pack textures, align mesh names, re-export GLB after section11."""
import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLEND = ROOT / "public" / "models" / "c919.blend"
GLB = ROOT / "public" / "models" / "c919.glb"

bpy.ops.wm.open_mainfile(filepath=str(BLEND))

for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    if me.name == ob.name:
        continue
    target = ob.name
    existing = bpy.data.meshes.get(target)
    if existing is not None and existing != me:
        if existing.users == 0:
            bpy.data.meshes.remove(existing)
    me.name = target
    print(f"mesh rename -> {me.name} (obj {ob.name})", flush=True)

for img in bpy.data.images:
    if img.filepath and not img.packed_file:
        try:
            img.pack()
            print(f"packed {img.name} {img.filepath}", flush=True)
        except Exception as e:
            print(f"pack fail {img.name}: {e}", flush=True)

for m in bpy.data.materials:
    if not m.node_tree:
        continue
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            print(
                f"mat {m.name} img={n.image.name} packed={bool(n.image.packed_file)} size={tuple(n.image.size)}",
                flush=True,
            )

bpy.ops.object.select_all(action="DESELECT")
n = 0
for o in bpy.data.objects:
    if o.type == "MESH" and not o.hide_get() and not o.hide_render:
        o.select_set(True)
        n += 1
bpy.ops.export_scene.gltf(
    filepath=str(GLB),
    use_selection=True,
    export_apply=True,
    export_image_format="AUTO",
)
print(f"exported {n} -> {GLB} bytes={GLB.stat().st_size}", flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
print("saved blend", flush=True)

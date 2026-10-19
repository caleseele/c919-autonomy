# -*- coding: utf-8 -*-
"""ws2c: exclude hidden seats from GLB; export visible only."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "build_c919.py"
t = p.read_text(encoding="utf-8")

old = '''def export_glb():
    os.makedirs(OUT_DIR, exist_ok=True)
    addon = "io_scene_gltf2"
    if addon not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon)
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_extras=True,
    )
'''

new = '''def export_glb():
    os.makedirs(OUT_DIR, exist_ok=True)
    addon = "io_scene_gltf2"
    if addon not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon)
    # ws2c: do not ship hidden interior seats/glare into GLB
    for name in ("PilotSeats", "GlareShield"):
        ob = bpy.data.objects.get(name)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
    kwargs = dict(
        filepath=GLB_PATH,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_extras=True,
    )
    # Blender 4+/5: prefer visible-only if supported
    for key, val in (("use_visible", True), ("export_visible", True)):
        try:
            bpy.ops.export_scene.gltf(**kwargs, **{key: val})
            print("C919_NOTE gltf_export", key)
            return
        except TypeError:
            continue
    bpy.ops.export_scene.gltf(**kwargs)
'''

if "ws2c: do not ship hidden" in t:
    print("EXPORT already")
elif old in t:
    t = t.replace(old, new, 1)
    print("EXPORT exact")
else:
    raise SystemExit("export_glb not found")

assert "ws2: NO punch" in t
p.write_text(t, encoding="utf-8")
print("WS2C_OK", p.stat().st_size)

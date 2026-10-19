# -*- coding: utf-8 -*-
import bpy
from pathlib import Path
ROOT = Path(r"C:\Users\希儿\Projects\c919-autonomy")
BLEND = ROOT / "public" / "models" / "c919.blend"
bpy.ops.wm.open_mainfile(filepath=str(BLEND))
m = bpy.data.materials.get("REF_舷窗玻璃")
print("props:", [p.identifier for p in m.bl_rna.properties if "blend" in p.identifier.lower() or "render" in p.identifier.lower() or "alpha" in p.identifier.lower() or "trans" in p.identifier.lower()], flush=True)
bm = m.bl_rna.properties.get("blend_method")
if bm:
    print("blend_method enum:", [i.identifier for i in bm.enum_items], flush=True)
sr = m.bl_rna.properties.get("surface_render_method")
if sr:
    print("surface_render_method enum:", [i.identifier for i in sr.enum_items], flush=True)
print("current blend", m.blend_method, "surface", getattr(m,"surface_render_method",None), flush=True)
# try set OPAQUE
for v in ["OPAQUE","CLIP","HASHED","BLEND"]:
    try:
        m.blend_method = v
        print(f"set blend_method={v} -> {m.blend_method} surface={getattr(m,'surface_render_method',None)}", flush=True)
    except Exception as e:
        print(f"fail blend {v}: {e}", flush=True)
for v in ["DITHERED","BLENDED","OPAQUE"]:
    try:
        m.surface_render_method = v
        print(f"set surface={v} -> blend={m.blend_method} surface={m.surface_render_method}", flush=True)
    except Exception as e:
        print(f"fail surface {v}: {e}", flush=True)
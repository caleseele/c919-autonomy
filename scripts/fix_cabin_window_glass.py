# -*- coding: utf-8 -*-
"""Make cabin passenger window glass opaque dark (#2A3440). Do not touch CockpitGlass_REF."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "models"
BLEND = OUT / "c919.blend"
GLB = OUT / "c919.glb"
BAK = OUT / "c919.bak-before-cabin-glass.blend"

CABIN_OBJ_MARKERS = ("舷窗玻璃",)  # REF_舷窗玻璃
COCKPIT_NAMES = {"CockpitGlass_REF"}
TARGET_RGB = (42 / 255.0, 52 / 255.0, 64 / 255.0, 1.0)  # #2A3440


def mat_snapshot(mat):
    info = {
        "name": mat.name,
        "blend_method": getattr(mat, "blend_method", None),
        "surface_render_method": getattr(mat, "surface_render_method", None),
        "use_transparency": getattr(mat, "use_transparency", None),
        "alpha": None,
        "base_color": None,
        "metallic": None,
        "roughness": None,
        "transmission": None,
    }
    if mat.use_nodes and mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if "Alpha" in bsdf.inputs:
                info["alpha"] = float(bsdf.inputs["Alpha"].default_value)
            if "Base Color" in bsdf.inputs:
                c = bsdf.inputs["Base Color"].default_value
                info["base_color"] = tuple(round(float(x), 4) for x in c)
            if "Metallic" in bsdf.inputs:
                info["metallic"] = float(bsdf.inputs["Metallic"].default_value)
            if "Roughness" in bsdf.inputs:
                info["roughness"] = float(bsdf.inputs["Roughness"].default_value)
            for key in ("Transmission Weight", "Transmission"):
                if key in bsdf.inputs:
                    info["transmission"] = float(bsdf.inputs[key].default_value)
                    info["transmission_socket"] = key
                    break
    return info


def set_opaque_cabin(mat):
    before = mat_snapshot(mat)
    if not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.get("Material Output")
        if out:
            nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Disconnect anything feeding Base Color / Alpha / Transmission so defaults stick
    for sock_name in ("Base Color", "Alpha", "Transmission Weight", "Transmission", "Metallic", "Roughness"):
        if sock_name not in bsdf.inputs:
            continue
        sock = bsdf.inputs[sock_name]
        for link in list(sock.links):
            nt.links.remove(link)

    bsdf.inputs["Base Color"].default_value = TARGET_RGB
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.08
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = 1.0
    for key in ("Transmission Weight", "Transmission"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.0

    # Blender 4.x / 5.x opaque flags
    for attr, val in (
        ("blend_method", "OPAQUE"),
        ("surface_render_method", "DITHERED"),  # EEVEE Next opaque-ish; try OPAQUE if exists
        ("use_screen_refraction", False),
        ("use_backface_culling", False),
        ("show_transparent_back", False),
    ):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception as e:
                print(f"  warn set {attr}={val!r}: {e}", flush=True)

    # Some builds use surface_render_method = 'OPAQUE' instead of DITHERED
    if hasattr(mat, "surface_render_method"):
        for candidate in ("OPAQUE", "DITHERED"):
            try:
                mat.surface_render_method = candidate
                break
            except Exception:
                continue

    if hasattr(mat, "blend_method"):
        try:
            mat.blend_method = "OPAQUE"
        except Exception as e:
            print(f"  warn blend_method: {e}", flush=True)

    after = mat_snapshot(mat)
    return before, after


def is_cabin_window_obj(ob):
    if ob.type != "MESH":
        return False
    if ob.name in COCKPIT_NAMES:
        return False
    # exact / prefix style REF_舷窗玻璃
    if "舷窗玻璃" in ob.name:
        return True
    return False


def main():
    print("=== fix_cabin_window_glass ===", flush=True)
    print(f"BLEND={BLEND} exists={BLEND.is_file()}", flush=True)
    if not BLEND.is_file():
        raise FileNotFoundError(BLEND)

    shutil.copy2(BLEND, BAK)
    print(f"backup -> {BAK}", flush=True)

    bpy.ops.wm.open_mainfile(filepath=str(BLEND))

    cabin_objs = [o for o in bpy.data.objects if is_cabin_window_obj(o)]
    print(f"cabin window objects ({len(cabin_objs)}):", flush=True)
    for o in cabin_objs:
        mats = [m.name if m else None for m in o.data.materials]
        print(f"  {o.name} mats={mats} hide={o.hide_get()} hide_render={o.hide_render}", flush=True)

    cockpit = bpy.data.objects.get("CockpitGlass_REF")
    cockpit_mat_names = set()
    cockpit_before = []
    if cockpit and cockpit.type == "MESH":
        for m in cockpit.data.materials:
            if m:
                cockpit_mat_names.add(m.name)
                cockpit_before.append(mat_snapshot(m))
        print(f"CockpitGlass_REF mats={sorted(cockpit_mat_names)} (will not touch)", flush=True)
    else:
        print("CockpitGlass_REF not found (ok)", flush=True)

    # Collect unique materials used by cabin window objects, excluding cockpit mats
    to_update = {}
    for o in cabin_objs:
        for m in o.data.materials:
            if m is None:
                continue
            if m.name in cockpit_mat_names:
                print(f"  skip shared-with-cockpit mat {m.name} on {o.name}", flush=True)
                continue
            to_update[m.name] = m

    if not to_update:
        # Fallback: any material whose name suggests cabin window glass
        for m in bpy.data.materials:
            if m.name in cockpit_mat_names:
                continue
            if "舷窗" in m.name or "CabinGlass" in m.name or "cabin_glass" in m.name.lower():
                to_update[m.name] = m
        print(f"fallback mat scan -> {list(to_update)}", flush=True)

    changed = []
    for name, mat in sorted(to_update.items()):
        print(f"\n--- updating material: {name} ---", flush=True)
        before, after = set_opaque_cabin(mat)
        print(f"  BEFORE: {before}", flush=True)
        print(f"  AFTER:  {after}", flush=True)
        changed.append({"name": name, "before": before, "after": after})

    # Confirm cockpit unchanged
    if cockpit and cockpit.type == "MESH":
        print("\n--- CockpitGlass_REF verification ---", flush=True)
        for m in cockpit.data.materials:
            if not m:
                continue
            now = mat_snapshot(m)
            print(f"  {now}", flush=True)
            # Compare alpha/blend/base to before
            for prev in cockpit_before:
                if prev["name"] == m.name:
                    same = (
                        prev.get("alpha") == now.get("alpha")
                        and prev.get("blend_method") == now.get("blend_method")
                        and prev.get("base_color") == now.get("base_color")
                        and prev.get("transmission") == now.get("transmission")
                    )
                    print(f"  unchanged={same}", flush=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print(f"\nsaved blend -> {BLEND}", flush=True)

    # Export visible meshes (same as section11)
    bpy.ops.object.select_all(action="DESELECT")
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.hide_get() or o.hide_render:
            continue
        o.select_set(True)
        n += 1
    bpy.ops.export_scene.gltf(
        filepath=str(GLB),
        use_selection=True,
        export_apply=True,
        export_image_format="AUTO",
    )
    size = GLB.stat().st_size
    print(f"exported {n} meshes -> {GLB} bytes={size}", flush=True)
    print(f"CHANGED_MATERIALS={ [c['name'] for c in changed] }", flush=True)
    print("=== done ===", flush=True)


if __name__ == "__main__":
    main()
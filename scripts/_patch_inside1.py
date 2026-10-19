#!/usr/bin/env python3
"""INSIDE1: restore see-through windshield without VIS1 cavity look.

Edits scripts/build_c919.py in place (expects WS1 baseline on disk).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_c919.py"


NEW_PUNCH = r'''def punch_windshield_openings(nose_obj):
    """Clean inset openings under the four panes + thin inward reveal flange.

    inside1: restore see-through without VIS1 ragged cavity.
    - Shrink kill region under mullion/brow/sill so frames cover the rim.
    - Delete only outer-skin faces, dissolve short boundary edges, drop orphans.
    - Cap each hole with a thin inward flange (reads as glass-in-reveal, not tear).
    """
    if nose_obj is None or nose_obj.type != "MESH":
        return
    mesh = nose_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    panes = _cockpit_pane_defs()
    # Angular / longitudinal inset so thin WS1 frames hide the rim
    A_INSET = math.radians(1.05)
    Y_INSET = 0.045

    def _in_inset_pane(a, y, pane):
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        if not (lo + A_INSET <= a <= hi - A_INSET):
            return False
        y_fwd = pane["y_fwd"](a)
        y_aft = pane["y_aft"](a)
        y_lo, y_hi = (y_aft, y_fwd) if y_aft <= y_fwd else (y_fwd, y_aft)
        return (y_lo + Y_INSET) <= y <= (y_hi - Y_INSET)

    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        y = c.y
        if y < 15.40 or y > 17.80:
            continue
        a = math.atan2(c.x, c.z)
        hit = False
        for pane in panes:
            if _in_inset_pane(a, y, pane):
                hit = True
                break
        if not hit:
            continue
        rx, rz = _section_at_y(y)
        r_skin = math.hypot(c.x / max(rx, 1e-6), c.z / max(rz, 1e-6))
        # Outer skin only
        if r_skin > 0.86:
            kill.append(f)

    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")

    dead = [v for v in bm.verts if not v.link_faces]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="VERTS")

    bm.edges.ensure_lookup_table()
    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.012]
    if short:
        try:
            bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
        except Exception:
            pass

    # Thin inward reveal flange per pane
    FLANGE_DEPTH = 0.032
    FLANGE_SEGS_A = 18
    FLANGE_SEGS_Y = 10
    for pane in panes:
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        a_lo = lo + A_INSET
        a_hi = hi - A_INSET
        if a_hi - a_lo < math.radians(2.0):
            continue
        outer = []
        inner = []
        for j in range(FLANGE_SEGS_Y + 1):
            ty = j / float(FLANGE_SEGS_Y)
            row_o, row_i = [], []
            for i in range(FLANGE_SEGS_A + 1):
                ta = i / float(FLANGE_SEGS_A)
                a = _lerp(a_lo, a_hi, ta)
                y_fwd = pane["y_fwd"](a)
                y_aft = pane["y_aft"](a)
                y = _lerp(y_fwd - Y_INSET, y_aft + Y_INSET, ty)
                row_o.append(bm.verts.new(_canopy_point(a, y, -0.002)))
                row_i.append(bm.verts.new(_canopy_point(a, y, -FLANGE_DEPTH)))
            outer.append(row_o)
            inner.append(row_i)
        for j in range(FLANGE_SEGS_Y + 1):
            for i in range(FLANGE_SEGS_A):
                o0, o1 = outer[j][i], outer[j][i + 1]
                i0, i1 = inner[j][i], inner[j][i + 1]
                try:
                    bm.faces.new((o0, o1, i1, i0))
                except ValueError:
                    pass
        for j in range(FLANGE_SEGS_Y):
            for edge_i in (0, FLANGE_SEGS_A):
                o0, o1 = outer[j][edge_i], outer[j + 1][edge_i]
                i0, i1 = inner[j][edge_i], inner[j + 1][edge_i]
                try:
                    if edge_i == 0:
                        bm.faces.new((o0, i0, i1, o1))
                    else:
                        bm.faces.new((o0, o1, i1, i0))
                except ValueError:
                    pass
        for i in range(FLANGE_SEGS_A):
            for edge_j in (0, FLANGE_SEGS_Y):
                o0, o1 = outer[edge_j][i], outer[edge_j][i + 1]
                i0, i1 = inner[edge_j][i], inner[edge_j][i + 1]
                try:
                    if edge_j == 0:
                        bm.faces.new((o0, o1, i1, i0))
                    else:
                        bm.faces.new((o0, i0, i1, o1))
                except ValueError:
                    pass

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    print("C919_NOTE punched_ws_faces", len(kill), "(inside1 inset+flange)")


'''


def replace_function(src: str, func_name: str, new_body: str) -> str:
    """Replace from 'def func_name' through the line before the next top-level def."""
    pat = re.compile(
        rf"^def {re.escape(func_name)}\(.*?(?=^def |\Z)",
        re.M | re.S,
    )
    m = pat.search(src)
    if not m:
        raise SystemExit(f"function not found: {func_name}")
    return src[: m.start()] + new_body + src[m.end() :]


def tweak_cockpit_glass(src: str) -> str:
    """Make CockpitGlass see-through for glTF / Three.js."""
    old = '''    # ws1c: medium-dark exterior panes (read as glass panels, not voids)
    cockpit_glass = material("CockpitGlass", (0.07, 0.08, 0.10), 0.22, 0.15)
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.12),
            ("Transmission", 0.12),
            ("Alpha", 1.0),
            ("Roughness", 0.10),
            ("IOR", 1.45),
            ("Metallic", 0.25),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.07, 0.08, 0.10, 1.0)
    try:
        cockpit_glass.blend_method = "OPAQUE"
    except Exception:
        pass'''

    new = '''    # inside1: transparent cockpit glass so seats show through openings
    cockpit_glass = material("CockpitGlass", (0.06, 0.09, 0.12), 0.06, 0.0)
    bsdf = cockpit_glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key, val in (
            ("Transmission Weight", 0.86),
            ("Transmission", 0.86),
            ("Alpha", 0.28),
            ("Roughness", 0.05),
            ("IOR", 1.45),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.06, 0.09, 0.12, 1.0)
    try:
        cockpit_glass.blend_method = "BLEND"
    except Exception:
        pass
    try:
        cockpit_glass.use_backface_culling = False
    except Exception:
        pass
    try:
        cockpit_glass.shadow_method = "NONE"
    except Exception:
        pass'''

    if old not in src:
        # fuzzy: replace by marker block
        pat = re.compile(
            r'    # ws1c: medium-dark exterior panes.*?except Exception:\n        pass',
            re.S,
        )
        if not pat.search(src):
            raise SystemExit("CockpitGlass block not found")
        src = pat.sub(new.rstrip("\n"), src, count=1)
        return src
    return src.replace(old, new, 1)


def nudge_seats(src: str) -> str:
    """Shift pilot seat assembly slightly forward (+Y) for better through-glass view."""
    # Pedestal / cushion / rails were at ~16.38–16.40; bump +0.12
    repls = [
        ("vec=(sx, 16.38, 0.05)", "vec=(sx, 16.50, 0.05)"),
        ("vec=(sx + rx, 16.40, -0.02)", "vec=(sx + rx, 16.52, -0.02)"),
        ("vec=(sx, 16.42, 0.22)", "vec=(sx, 16.54, 0.22)"),
        ("vec=(sx, 16.28, 0.62)", "vec=(sx, 16.40, 0.62)"),
        ("vec=(sx, 16.22, 1.05)", "vec=(sx, 16.34, 1.05)"),
        ("vec=(sx, 16.20, 1.18)", "vec=(sx, 16.32, 1.18)"),
        ("vec=(sx, 16.35, 0.38)", "vec=(sx, 16.47, 0.38)"),
        ("cent=(sx, 16.28, 0.62)", "cent=(sx, 16.40, 0.62)"),
        # glare shield slight forward too
        ("vec=(0.0, 17.02, 0.96)", "vec=(0.0, 17.08, 0.96)"),
        ("cent=(0.0, 17.02, 0.96)", "cent=(0.0, 17.08, 0.96)"),
        ("vec=(0.0, 17.28, 0.90)", "vec=(0.0, 17.32, 0.90)"),
        ("vec=(sx, 16.88, 0.74)", "vec=(sx, 16.94, 0.74)"),  # may not match - cheeks use ±1.05
        ("vec=(0.0, 16.78, 0.72)", "vec=(0.0, 16.84, 0.72)"),
        ("cent=(0.0, 16.78, 0.72)", "cent=(0.0, 16.84, 0.72)"),
        ("vec=(sx, 16.88, 0.82)", "vec=(sx, 16.94, 0.82)"),  # displays - pattern uses enumerate sx
        ("vec=(0.0, 16.35, 0.28)", "vec=(0.0, 16.45, 0.28)"),
    ]
    # More careful replacements for glare cheek/display lines
    src2 = src
    for a, b in repls:
        src2 = src2.replace(a, b)
    # cheek: bmesh.ops.translate(..., vec=(sx, 16.88, 0.74)) where sx is -1.05/1.05
    src2 = src2.replace("vec=(sx, 16.88, 0.74)", "vec=(sx, 16.94, 0.74)")
    src2 = src2.replace("vec=(sx, 16.88, 0.82)", "vec=(sx, 16.94, 0.82)")
    return src2


def bump_glass_offset(src: str) -> str:
    """Keep glass slightly proud so it covers flange lip."""
    return src.replace(
        '''        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.004)''',
        '''        pane["segs_a"] = max(pane["segs_a"], 26)
        pane["segs_y"] = max(pane["segs_y"], 18)
        _add_canopy_pane(bm, pane, r_off=0.006)''',
        1,
    )


def bump_note(src: str) -> str:
    src = src.replace(
        'print("C919_NOTE ws1d=single-sided-frames+dark-pane-contrast+vertical-wipers+no-punch")',
        'print("C919_NOTE inside1=inset-punch+inward-flange+clear-glass+seats-fwd+ws1-frames")',
    )
    return src


def main():
    if not SCRIPT.exists():
        raise SystemExit(f"missing {SCRIPT}")
    text = SCRIPT.read_text(encoding="utf-8")
    if "inside1 inset+flange" in text:
        print("already patched")
        return
    text = replace_function(text, "punch_windshield_openings", NEW_PUNCH)
    text = tweak_cockpit_glass(text)
    text = nudge_seats(text)
    text = bump_glass_offset(text)
    text = bump_note(text)
    SCRIPT.write_text(text, encoding="utf-8")
    print("patched", SCRIPT)
    print("size", SCRIPT.stat().st_size)


if __name__ == "__main__":
    main()

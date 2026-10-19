"""Splice tail1 helpers into build_c919.py (from.bak-tail1 base)."""
from pathlib import Path
import re

ROOT = Path(r"C:\Users\希儿\Projects\c919-autonomy")
BUILD = ROOT / "scripts" / "build_c919.py"
BAK = ROOT / "scripts" / "build_c919.py.bak-tail1"
FUNCS = ROOT / "scripts" / "_tail1_funcs.py"
# Also accept box-copied path next to patch
if not FUNCS.exists():
    FUNCS = Path(__file__).resolve().parent / "_tail1_funcs.py"


def replace_between(text: str, start_marker: str, end_marker: str, new_body: str) -> str:
    i0 = text.find(start_marker)
    if i0 < 0:
        raise SystemExit(f"START not found: {start_marker!r}")
    i1 = text.find(end_marker, i0 + 1)
    if i1 < 0:
        raise SystemExit(f"END not found after start: {end_marker!r}")
    return text[:i0] + new_body.rstrip() + "\n\n\n" + text[i1:]


def soft_aft_profile(text: str) -> str:
    """Slightly smoother aft taper (no abrupt neck); keep tip soft."""
    old = """    (-16.60, 1.640, 1.650),
    (-17.25, 1.400, 1.410),
    (-17.80, 1.120, 1.130),
    (-18.25, 0.860, 0.875),
    (-18.65, 0.620, 0.635),
    (-18.95, 0.400, 0.415),
    (-19.20, 0.230, 0.245),
    (-19.40, 0.100, 0.110),
    (-19.55, 0.030, 0.035),  # soft cone tip
]"""
    new = """    (-16.55, 1.660, 1.670),
    (-17.10, 1.460, 1.470),
    (-17.55, 1.240, 1.255),
    (-17.95, 1.000, 1.015),
    (-18.30, 0.780, 0.795),
    (-18.60, 0.580, 0.595),
    (-18.88, 0.400, 0.415),
    (-19.12, 0.250, 0.265),
    (-19.32, 0.130, 0.140),
    (-19.48, 0.055, 0.060),
    (-19.58, 0.018, 0.020),  # soft cone tip (tail1)
]"""
    if old not in text:
        if "tail1" in text and "(-19.58, 0.018" in text:
            print("AFT_PROFILE already patched")
            return text
        raise SystemExit("FUSELAGE aft block not found for soft refine")
    return text.replace(old, new)


def refine_apu(text: str) -> str:
    """Gentler APU scoop under cone; keep antennas."""
    start = "def antennas_and_apu():"
    end = "def build():"
    body = '''def antennas_and_apu():
    """Blade antennas aft of cockpit + refined APU scoop under tail cone."""
    bm = bmesh.new()
    blades = [
        (0.0, 15.15, 0.38, 0.12, 0.025),
        (0.0, 14.55, 0.28, 0.10, 0.022),
    ]
    for x, y, h, chord, thick in blades:
        z0 = _radius_at_y(y) - 0.02
        v0 = bm.verts.new((x - thick * 0.5, y - chord * 0.35, z0))
        v1 = bm.verts.new((x - thick * 0.5, y + chord * 0.55, z0))
        v2 = bm.verts.new((x - thick * 0.5, y + chord * 0.05, z0 + h))
        v3 = bm.verts.new((x + thick * 0.5, y - chord * 0.35, z0))
        v4 = bm.verts.new((x + thick * 0.5, y + chord * 0.55, z0))
        v5 = bm.verts.new((x + thick * 0.5, y + chord * 0.05, z0 + h))
        bm.faces.new((v0, v1, v2))
        bm.faces.new((v3, v5, v4))
        bm.faces.new((v0, v2, v5, v3))
        bm.faces.new((v1, v4, v5, v2))
        bm.faces.new((v0, v3, v4, v1))

    # Streamlined APU inlet scoop under aft cone (not a floating box)
    y_apu = -18.70
    r = _radius_at_y(y_apu)
    segs = 12
    length = 0.42
    width = 0.16
    height = 0.09
    rings = []
    for i in range(7):
        t = i / 6.0
        s = math.sin(math.pi * t) ** 0.75
        s = max(s, 0.08)
        yy = y_apu - length * 0.45 + length * t
        ww = width * 0.5 * s
        hh = height * 0.5 * s
        ring = []
        for k in range(segs):
            a = math.tau * k / segs
            # flatten top against belly
            zx = math.cos(a) * ww
            zz = math.sin(a) * hh
            if zz > 0:
                zz *= 0.35
            ring.append(bm.verts.new((zx, yy, -r + 0.01 + zz)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    return finish(bm)


'''
    return replace_between(text, start, end, body)


def link_tail_cone(text: str) -> str:
    """Insert TailCone link after VerticalTail/Rudder links."""
    needle = '''    link("Stab_R", stab(1), "tail", skin, "skin")
    link("Stab_L", stab(-1), "tail", skin, "skin")
    link("VerticalTail", vertical_tail(), "tail", navy, "navy")
    link("Rudder", rudder(), "tail", stripe, "stripe")
'''
    insert = '''    link("Stab_R", stab(1), "tail", skin, "skin")
    link("Stab_L", stab(-1), "tail", skin, "skin")
    link("VerticalTail", vertical_tail(), "tail", navy, "navy")
    link("Rudder", rudder(), "tail", stripe, "stripe")
    # Dark metallic aft cone + APU exhaust lip (real C919 photo cue)
    cone_mat = material("TailConeMetal", (0.22, 0.23, 0.25), 0.32, 0.55)
    link("TailCone", tail_cone_cap(), "tail", cone_mat, "engine")
'''
    if "link(\"TailCone\"" in text or "link('TailCone'" in text:
        print("TailCone link already present")
        return text
    if needle not in text:
        raise SystemExit("Stab/VerticalTail link block not found")
    return text.replace(needle, insert)


def ensure_skip_subdiv(text: str) -> str:
    """Keep Stab/VerticalTail out of subdiv; add TailCone to skip list."""
    if '"TailCone"' in text and "skip_prefix" in text:
        # try add near VerticalTail in skip tuple
        pass
    old = '''        "Stab",
        "VerticalTail",
        "Engine",
    )'''
    new = '''        "Stab",
        "VerticalTail",
        "TailCone",
        "Engine",
    )'''
    if old in text:
        text = text.replace(old, new)
    return text


def main():
    if not BAK.exists():
        raise SystemExit(f"missing backup {BAK}")
    text = BAK.read_text(encoding="utf-8")
    funcs = FUNCS.read_text(encoding="utf-8")
    lines = funcs.splitlines()
    while lines and (lines[0].startswith("#") or not lines[0].strip()):
        lines.pop(0)
    funcs_body = "\n".join(lines).rstrip() + "\n"

    # Replace stab() ... rudder() inclusive; stop before _engine_xz
    text2 = replace_between(text, "def stab(side):", "def _engine_xz(side):", funcs_body)
    text2 = soft_aft_profile(text2)
    text2 = refine_apu(text2)
    text2 = link_tail_cone(text2)
    text2 = ensure_skip_subdiv(text2)

    # Update note line (whatever the previous pass printed)
    text2 = re.sub(
        r'print\("C919_NOTE [^"]*"\)',
        'print("C919_NOTE tail1=fin-loft+ht-airfoil+elevator-crease+dark-cone+apu-scoop")',
        text2,
        count=1,
    )
    # Also the main() note at end if different
    text2 = re.sub(
        r'print\("C919_NOTE inside1b=[^"]*"\)',
        'print("C919_NOTE tail1=fin-loft+ht-airfoil+elevator-crease+dark-cone+apu-scoop")',
        text2,
    )

    BUILD.write_text(text2, encoding="utf-8")
    print("PATCHED", BUILD, "BYTES", BUILD.stat().st_size)


if __name__ == "__main__":
    main()

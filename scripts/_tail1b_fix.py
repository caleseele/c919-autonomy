"""Quick fix: rounder fin tip + flush APU exhaust (no needle)."""
from pathlib import Path
import re

ROOT = Path(r"C:\Users\希儿\Projects\c919-autonomy")
BUILD = ROOT / "scripts" / "build_c919.py"


def replace_between(text, start, end, body):
    i0 = text.find(start)
    if i0 < 0:
        raise SystemExit(f"missing {start}")
    i1 = text.find(end, i0 + 1)
    if i1 < 0:
        raise SystemExit(f"missing {end}")
    return text[:i0] + body.rstrip() + "\n\n\n" + text[i1:]


VT = '''def vertical_tail():
    """Normal-tail vertical stabilizer: airfoil loft root→tip, rounded tip, soft LE.

    Conventional single fin (NOT T-tail). Tip height stays in ~12 m overall class.
    Root bottom hugs tapering crown so aft heel does not hover over the cone.
    """
    r_fwd = fuselage_radius_at(-14.7)
    stations = [
        # plant below crown
        (0.42 * r_fwd, -14.55, -17.85, 0.46),
        (0.55 * r_fwd + 0.15, -14.70, -18.05, 0.42),
        (1.8, -15.05, -18.25, 0.36),
        (3.2, -15.45, -18.35, 0.30),
        (4.6, -15.90, -18.40, 0.24),
        (5.9, -16.35, -18.38, 0.19),
        (7.0, -16.75, -18.28, 0.145),
        (7.85, -17.10, -18.10, 0.110),
        (8.35, -17.35, -17.95, 0.080),
        # rounded tip dome — chord collapses, z keeps climbing
        (8.58, -17.48, -17.82, 0.050),
        (8.70, -17.55, -17.72, 0.028),
        (8.78, -17.60, -17.68, 0.012),
    ]
    n_half = 11
    bm = bmesh.new()
    rings = []
    for z, yle, yte, th in stations:
        ring = []
        for y, t in _tail_airfoil_2d(yle, yte, th, n_half):
            ring.append(bm.verts.new((t, y, z)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    try:
        bm.faces.new(list(reversed(rings[0])))
    except ValueError:
        pass
    # Dome tip pole instead of flat tip cap
    tip = bm.verts.new((0.0, -17.64, 8.82))
    last = rings[-1]
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((last[i], last[j], tip))
        except ValueError:
            pass

    for ri, (z, yle, yte, th) in enumerate(stations[:-3]):
        chord = yle - yte
        y_hinge = yte + chord * 0.18
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.035:
                v.co.x *= 0.78

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)
'''

CONE = '''def tail_cone_cap():
    """Dark metallic aft cone tip + circular APU exhaust (flush, no needle)."""
    bm = bmesh.new()
    stations = [
        (-18.55, 0.66, 0.68),
        (-18.80, 0.48, 0.50),
        (-19.05, 0.30, 0.32),
        (-19.25, 0.16, 0.175),
        (-19.42, 0.07, 0.08),
        (-19.52, 0.028, 0.032),
    ]
    segs = 48
    rings = []
    for y, rx, rz in stations:
        rx *= 1.03
        rz *= 1.03
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rx, y, math.sin(ang) * rz))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            try:
                bm.faces.new((a[i], b[i], b[j], a[j]))
            except ValueError:
                pass
    # Flush circular APU exhaust lip (slightly inset disk, no protruding rod)
    tip_y = -19.55
    r_ex = 0.048
    outer = []
    for i in range(segs):
        ang = math.tau * i / segs
        outer.append(
            bm.verts.new((math.cos(ang) * r_ex, tip_y, math.sin(ang) * r_ex))
        )
    last = rings[-1]
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new((last[i], outer[i], outer[j], last[j]))
        except ValueError:
            pass
    # Dark exhaust face slightly inset
    disc_y = tip_y + 0.02
    pole = bm.verts.new((0.0, disc_y, 0.0))
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new((pole, outer[j], outer[i]))
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)
'''


def main():
    text = BUILD.read_text(encoding="utf-8")
    text = replace_between(text, "def vertical_tail():", "def rudder():", VT)
    text = replace_between(text, "def tail_cone_cap():", "def _engine_xz(side):", CONE)
    # Nudge TailMark onto thicker mid-fin skin
    text = text.replace(
        "mark.location = (side * 0.185, -17.0, 5.8)",
        "mark.location = (side * 0.14, -16.85, 5.6)",
    )
    text = re.sub(
        r'print\("C919_NOTE [^"]*"\)',
        'print("C919_NOTE tail1b=rounded-fin-tip+flush-apu+mark-nudge")',
        text,
    )
    BUILD.write_text(text, encoding="utf-8")
    print("FIXED", BUILD.stat().st_size)


if __name__ == "__main__":
    main()

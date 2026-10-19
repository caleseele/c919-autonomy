from pathlib import Path
p = Path("scripts/build_c919.py")
t = p.read_text(encoding="utf-8")

old = '''            if kind == "overwing":
                _add_skin_seal_loft(
                    bm, y, z, w + 0.08, h + 0.08, corner + 0.02, side,
                    border=0.070, r_off=0.022, segs=10, rings=6,
                )
            else:'''

new = '''            if kind == "overwing":
                _add_skin_seal_loft(
                    bm, y, z, w + 0.10, h + 0.10, corner + 0.025, side,
                    border=0.085, r_off=0.028, segs=10, rings=6,
                )
                # Bold axis-aligned bezel (same language as cabin windows)
                # so the exit reads clearly above the wing in clay/Three.js.
                rx, _rz = _section_at_y(y)
                x_off = rx + 0.018
                m = Matrix.Translation((side * x_off, y, z))
                if side < 0:
                    m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
                add_rounded_frame(
                    bm, w + 0.06, h + 0.06, 0.014, corner + 0.02,
                    border=0.055, segs=7, matrix=m,
                )
            else:'''

if old not in t:
    raise SystemExit("overwing seal block missing")
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("BOLD_DOOR_OK")

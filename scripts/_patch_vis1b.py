# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("scripts/build_c919.py")
text = path.read_text(encoding="utf-8")

# 1) Add punch_windshield_openings after cockpit_frames / before pitot
fn = '''
def punch_windshield_openings(nose_obj):
    """Delete nose skin faces under the four windshield panes so glass sees interior."""
    if nose_obj is None or nose_obj.type != "MESH":
        return
    mesh = nose_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    panes = _cockpit_pane_defs()
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        y = c.y
        # Only forward canopy band
        if y < 15.35 or y > 17.85:
            continue
        # Angle from +Z crown
        a = math.atan2(c.x, c.z)
        for pane in panes:
            a0, a1 = pane["a0"], pane["a1"]
            lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
            if not (lo - 0.02 <= a <= hi + 0.02):
                continue
            y_fwd = pane["y_fwd"](a)
            y_aft = pane["y_aft"](a)
            y_lo, y_hi = (y_aft, y_fwd) if y_aft <= y_fwd else (y_fwd, y_aft)
            if y_lo - 0.04 <= y <= y_hi + 0.04:
                # Keep only outer skin (near section radius)
                rx, rz = _section_at_y(y)
                r_skin = math.hypot(c.x / max(rx, 1e-6), c.z / max(rz, 1e-6))
                if r_skin > 0.82:
                    kill.append(f)
                break
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(mesh)
        mesh.update()
    bm.free()
    print("C919_NOTE punched_ws_faces", len(kill))


'''

if "def punch_windshield_openings(" not in text:
    marker = "\ndef pitot_probes():\n"
    if marker not in text:
        raise SystemExit("pitot marker missing")
    text = text.replace(marker, fn + marker, 1)

# 2) Call punch after nose is linked — find Nose link and add after
old_nose = '''    link(
        "Nose",
        nose_with_cap(list(NOSE_PROFILE), segments=120),
        "nose",
        skin,
        "skin",
    )'''
# may be formatted differently — search
import re
m = re.search(r'link\(\s*"Nose".*?\n\s*\)', text, re.S)
if not m:
    raise SystemExit("Nose link not found")
nose_block = m.group(0)
if "punch_windshield_openings" not in text[m.end():m.end()+200]:
    text = text[:m.end()] + "\n    punch_windshield_openings(bpy.data.objects.get(\"Nose\"))\n" + text[m.end():]

# 3) Make overwing door seal more readable + slightly proud
old_frames = '''def cabin_door_frames():
    """Dark seal loft on skin'''
# bump overwing-only: change cabin_door_frames to thicken overwing
old_cf = '''def cabin_door_frames():
    """Dark seal loft on skin — continuous rounded rectangle, all four sides."""
    bm = bmesh.new()
    for y, z, w, h, corner, _kind in _door_specs():
        for side in (1, -1):
            _add_skin_seal_loft(
                bm, y, z, w + 0.05, h + 0.05, corner + 0.015, side,
                border=0.050, r_off=0.013, segs=8, rings=5,
            )
    _orient_faces_outward(bm)
    return finish(bm)'''

# The docstring may have encoding issues — use flexible replace
import re
pat = re.compile(
    r'def cabin_door_frames\(\):\n(?:.*\n)*?    return finish\(bm\)\n',
    re.M,
)
new_cf = '''def cabin_door_frames():
    """Dark seal loft on skin — continuous rounded rectangle, all four sides."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Overwing: thicker/darker-readable seal so exit reads above wing
            if kind == "overwing":
                _add_skin_seal_loft(
                    bm, y, z, w + 0.08, h + 0.08, corner + 0.02, side,
                    border=0.070, r_off=0.022, segs=10, rings=6,
                )
            else:
                _add_skin_seal_loft(
                    bm, y, z, w + 0.05, h + 0.05, corner + 0.015, side,
                    border=0.050, r_off=0.013, segs=8, rings=5,
                )
    _orient_faces_outward(bm)
    return finish(bm)
'''
m2 = pat.search(text)
if not m2:
    raise SystemExit("cabin_door_frames not found")
text = text[:m2.start()] + new_cf + text[m2.end():]

path.write_text(text, encoding="utf-8")
print("PATCH2_OK", path.stat().st_size)

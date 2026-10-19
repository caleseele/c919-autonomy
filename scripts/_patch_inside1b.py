from pathlib import Path
import re
p = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = p.read_text(encoding="utf-8")

NEW = r'''def punch_windshield_openings(nose_obj):
    """Clean inset openings under the four panes + thin inward reveal flange.

    inside1b: restore see-through without VIS1 ragged cavity.
    - Shrink kill region under mullion/brow/sill so frames cover the rim.
    - Delete only outer-skin faces, dissolve short boundary edges, drop orphans.
    - PERIMETER-ONLY inward flange (not a filled radial slab that blocks seats).
    """
    if nose_obj is None or nose_obj.type != "MESH":
        return
    mesh = nose_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    panes = _cockpit_pane_defs()
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
        if not any(_in_inset_pane(a, y, pane) for pane in panes):
            continue
        rx, rz = _section_at_y(y)
        r_skin = math.hypot(c.x / max(rx, 1e-6), c.z / max(rz, 1e-6))
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

    # Perimeter-only reveal flange: outline path → outer/inner loft
    FLANGE_DEPTH = 0.028
    SEGS_A = 20
    SEGS_Y = 12

    def _outline(pane):
        """CCW outline of inset pane in (a,y) space: fwd → right → aft → left."""
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        a_lo, a_hi = lo + A_INSET, hi - A_INSET
        pts = []
        # forward edge a_lo → a_hi
        for i in range(SEGS_A + 1):
            a = _lerp(a_lo, a_hi, i / float(SEGS_A))
            pts.append((a, pane["y_fwd"](a) - Y_INSET))
        # right edge aftward
        for j in range(1, SEGS_Y + 1):
            t = j / float(SEGS_Y)
            a = a_hi
            y = _lerp(pane["y_fwd"](a) - Y_INSET, pane["y_aft"](a) + Y_INSET, t)
            pts.append((a, y))
        # aft edge a_hi → a_lo
        for i in range(1, SEGS_A + 1):
            a = _lerp(a_hi, a_lo, i / float(SEGS_A))
            pts.append((a, pane["y_aft"](a) + Y_INSET))
        # left edge forward
        for j in range(1, SEGS_Y):
            t = j / float(SEGS_Y)
            a = a_lo
            y = _lerp(pane["y_aft"](a) + Y_INSET, pane["y_fwd"](a) - Y_INSET, t)
            pts.append((a, y))
        return pts

    for pane in panes:
        outline = _outline(pane)
        n = len(outline)
        if n < 8:
            continue
        outer = [bm.verts.new(_canopy_point(a, y, -0.001)) for a, y in outline]
        inner = [bm.verts.new(_canopy_point(a, y, -FLANGE_DEPTH)) for a, y in outline]
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
            except ValueError:
                pass

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    print("C919_NOTE punched_ws_faces", len(kill), "(inside1b perimeter-flange)")


'''

pat = re.compile(r"^def punch_windshield_openings\(.*?(?=^def |\Z)", re.M | re.S)
m = pat.search(text)
if not m:
    raise SystemExit("punch not found")
text = text[: m.start()] + NEW + text[m.end():]
# also nudge seats a bit more forward/up for visibility through front panes
text = text.replace("vec=(sx, 16.50, 0.05)", "vec=(sx, 16.58, 0.08)")
text = text.replace("vec=(sx + rx, 16.52, -0.02)", "vec=(sx + rx, 16.60, 0.01)")
text = text.replace("vec=(sx, 16.54, 0.22)", "vec=(sx, 16.62, 0.28)")
text = text.replace("vec=(sx, 16.40, 0.62)", "vec=(sx, 16.50, 0.70)")
text = text.replace("cent=(sx, 16.40, 0.62)", "cent=(sx, 16.50, 0.70)")
text = text.replace("vec=(sx, 16.34, 1.05)", "vec=(sx, 16.44, 1.12)")
text = text.replace("vec=(sx, 16.32, 1.18)", "vec=(sx, 16.42, 1.22)")
text = text.replace("vec=(sx, 16.47, 0.38)", "vec=(sx, 16.55, 0.42)")
text = text.replace(
    'print("C919_NOTE inside1=inset-punch+inward-flange+clear-glass+seats-fwd+ws1-frames")',
    'print("C919_NOTE inside1b=inset-punch+perimeter-flange+clear-glass+seats-fwd+ws1-frames")',
)
p.write_text(text, encoding="utf-8")
print("patched", p.stat().st_size)

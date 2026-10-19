"""Build a low-poly C919 in background Blender and export a glb.

Run:
  blender --background --factory-startup --python scripts/build_c919.py
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "public", "models")
GLB_PATH = os.path.join(OUT_DIR, "c919.glb")
BLEND_PATH = os.path.join(OUT_DIR, "c919.blend")

SEGMENTS = 80


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, color, roughness=0.42, metallic=0.08):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def glass_material(name="Glass"):
    """Cabin window glass (lighter). Cockpit uses cockpit_glass_material()."""
    mat = material(name, (0.08, 0.12, 0.18), 0.05, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.08, 0.12, 0.18, 1.0)
        for key, val in (
            ("Transmission Weight", 0.55),
            ("Transmission", 0.55),
            ("Alpha", 0.55),
            ("IOR", 1.45),
            ("Roughness", 0.06),
            ("Metallic", 0.0),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    try:
        mat.shadow_method = "NONE"
    except Exception:
        pass
    return mat


def cockpit_glass_material(name="CockpitGlass"):
    """ws3: clear tinted windshield — Transmission 1.0, faint blue-green #DDEEEB."""
    # #DDEEEB → linear-ish approx
    col = (0.867, 0.933, 0.922)
    mat = material(name, col, 0.02, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (col[0], col[1], col[2], 1.0)
        for key, val in (
            ("Transmission Weight", 1.0),
            ("Transmission", 1.0),
            ("Alpha", 0.18),
            ("IOR", 1.5),
            ("Roughness", 0.02),
            ("Metallic", 0.0),
            ("Specular IOR Level", 0.5),
        ):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    try:
        mat.blend_method = "HASHED"  # EEVEE: not Opaque; better than BLEND for glass
    except Exception:
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    try:
        mat.shadow_method = "NONE"
    except Exception:
        pass
    # Blender 5 / EEVEE raytrace hints when present
    for attr, val in (
        ("use_screen_refraction", True),
        ("use_raytrace_refraction", True),
        ("refraction_depth", 0.02),
    ):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat



def _paint_star(pixels, width, height, cx, cy, radius, rot=0.0):
    """Rasterize a filled 5-point star onto an RGBA float pixel buffer."""
    pts = []
    for i in range(5):
        a = -math.pi / 2 + rot + i * 2 * math.pi / 5
        b = a + math.pi / 5
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
        pts.append((cx + math.cos(b) * radius * 0.382, cy + math.sin(b) * radius * 0.382))

    min_x = max(0, int(cx - radius) - 2)
    max_x = min(width - 1, int(cx + radius) + 2)
    min_y = max(0, int(cy - radius) - 2)
    max_y = min(height - 1, int(cy + radius) + 2)
    yellow = (1.0, 0.87, 0.0, 1.0)

    def inside(px, py):
        odd = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi
            ):
                odd = not odd
            j = i
        return odd

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if inside(x + 0.5, y + 0.5):
                i = (y * width + x) * 4
                pixels[i : i + 4] = yellow


def flag_material():
    """PRC flag per GB 12982 / 鍥芥棗娉?construction sheet.

    Flag ratio 3:2. Canton = upper-left quarter with a 15脳10 grid.
    Large star center at canton grid (5,5) from top-left; diameter = 3/10 of
    flag height. Small stars at (10,2),(12,4),(12,7),(10,9); diameter = 1/10
    of flag height; each tip aims at the large-star center.
    Blender image Y grows upward (V=0 bottom).
    """
    width, height = 900, 600  # 3:2
    img = bpy.data.images.new("PRC_Flag", width, height)
    pixels = [0.0] * (width * height * 4)
    red = (0.878, 0.165, 0.063, 1.0)  # approx #E02A10
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            pixels[i : i + 4] = red

    # Canton = left half 脳 upper half. Grid unit within canton:
    ux = (width * 0.5) / 15.0   # = width/30
    uy = (height * 0.5) / 10.0  # = height/20
    # From top-left of canton: row r means r*uy down 鈫?Y-up cy = height - r*uy
    cx0 = 5.0 * ux
    cy0 = height - 5.0 * uy
    r0 = height * 0.15  # diameter 3/10 鈫?radius 0.15*h
    _paint_star(pixels, width, height, cx0, cy0, r0, 0.0)

    small_grid = [(10, 2), (12, 4), (12, 7), (10, 9)]
    rs = height * 0.05  # diameter 1/10 鈫?radius 0.05*h
    for gx, gy in small_grid:
        sx = gx * ux
        sy = height - gy * uy
        # Default tip is up (-pi/2); rotate so a tip aims at large center
        ang = math.atan2(cy0 - sy, cx0 - sx) + math.pi / 2
        _paint_star(pixels, width, height, sx, sy, rs, ang)

    img.pixels.foreach_set(pixels)
    img.pack()

    mat = material("Flag", (0.878, 0.165, 0.063), 0.5, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def link(name, mesh, part_id, mat, slot="skin"):
    obj = bpy.data.objects.new(name, mesh)
    obj["partId"] = part_id
    obj["liverySlot"] = slot
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        mesh.materials.append(mat)
        # Thin fins/wings must render both sides in the Three.js viewer
        if name.startswith(("VerticalTail", "Rudder", "Wing", "Winglet", "Stab", "Title", "TailMark", "Flag", "Windshield", "CockpitFrames", "Door")):
            try:
                mat.use_backface_culling = False
            except Exception:
                pass
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.normalize_normals()
    except Exception:
        pass
    return obj


GLYPHS = {
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
}


def text_image(text, fg, bg=(0, 0, 0, 0), scale=8):
    glyph_w, glyph_h = 5, 7
    width = (glyph_w * len(text) + (len(text) - 1)) * scale
    height = glyph_h * scale
    img = bpy.data.images.new("Title_" + text, width, height, alpha=True)
    pixels = [0.0] * (width * height * 4)
    for ci, ch in enumerate(text):
        rows = GLYPHS[ch]
        for gy, row in enumerate(rows):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        x = ci * (glyph_w + 1) * scale + gx * scale + sx
                        y = (glyph_h - 1 - gy) * scale + sy
                        i = (y * width + x) * 4
                        pixels[i : i + 4] = fg
    img.pixels.foreach_set(pixels)
    img.pack()
    return img


def image_material(name, image, clip_alpha=True):
    mat = material(name, (1, 1, 1), 0.4, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Alpha" in bsdf.inputs:
        mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    # Avoid opaque black quads looking like floating shards around glyph text
    if clip_alpha:
        try:
            mat.blend_method = "CLIP"
            mat.alpha_threshold = 0.1
        except Exception:
            pass
        try:
            mat.shadow_method = "CLIP"
        except Exception:
            pass
    return mat


def ensure_uv(bm):
    if not bm.loops.layers.uv:
        bm.loops.layers.uv.new("UVMap")
    return bm.loops.layers.uv["UVMap"]


def finish(bm):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new("mesh")
    bm.to_mesh(me)
    bm.free()
    return me


def quad(width, height):
    bm = bmesh.new()
    verts = [
        bm.verts.new((-width / 2, -height / 2, 0)),
        bm.verts.new((width / 2, -height / 2, 0)),
        bm.verts.new((width / 2, height / 2, 0)),
        bm.verts.new((-width / 2, height / 2, 0)),
    ]
    face = bm.faces.new(verts)
    uv_layer = ensure_uv(bm)
    for loop, uv in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv_layer].uv = uv
    return finish(bm)


def flag_plane(width, height, thickness=0.04):
    """Thin flag box with correct UVs on both faces (U along width, V along height)."""
    bm = bmesh.new()
    hw, hh, ht = width / 2, height / 2, thickness / 2
    # Build as a flat box: X = thickness, Y = length(width of flag), Z = height of flag
    coords = [
        (-ht, -hw, -hh),
        (ht, -hw, -hh),
        (ht, hw, -hh),
        (-ht, hw, -hh),
        (-ht, -hw, hh),
        (ht, -hw, hh),
        (ht, hw, hh),
        (-ht, hw, hh),
    ]
    vs = [bm.verts.new(c) for c in coords]
    faces_idx = [
        (0, 1, 2, 3),  # bottom
        (4, 7, 6, 5),  # top
        (0, 4, 5, 1),  # -Y
        (1, 5, 6, 2),  # +X (outer right side when side=+1)
        (2, 6, 7, 3),  # +Y
        (3, 7, 4, 0),  # -X (outer left side when side=-1)
    ]
    uv_layer = ensure_uv(bm)
    for idxs in faces_idx:
        f = bm.faces.new([vs[i] for i in idxs])
        # Map Y->U, Z->V for the large faces (卤X).
        # Hoist (stars, low U) faces nose (+Y): flip U vs local Y.
        for loop in f.loops:
            co = loop.vert.co
            u = (hw - co.y) / width
            v = (co.z + hh) / height
            loop[uv_layer].uv = (u, v)
    return finish(bm)


def lathe(profile, segments=None):
    segs = segments or SEGMENTS
    bm = bmesh.new()
    rings = []
    for y, radius in profile:
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * radius, y, math.sin(ang) * radius))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    return finish(bm)



def fuselage_body(profile, segments=None):
    """Loft elliptical fuselage stations (y, rx, rz) 鈥?continuous commercial tube.

    Mid cabin stays nearly cylindrical; FWD/AFT stations provide gradual taper
    into the nose join and soft tail cone without abrupt diameter jumps.
    """
    segs = segments or max(SEGMENTS, 96)
    bm = bmesh.new()
    rings = []
    for station in profile:
        y = station[0]
        rx = station[1]
        rz = station[2] if len(station) > 2 else station[1]
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
            bm.faces.new((a[i], b[i], b[j], a[j]))
    tip = rings[-1]
    if profile[-1][1] < 0.08:
        pole = bm.verts.new((0.0, profile[-1][0] - 0.06, 0.0))
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((tip[i], tip[j], pole))
    return finish(bm)

def nose_with_cap(profile, segments=None):
    """Elliptical-station nose + blunt parabolic radome tip (commercial jet).

    Each station is (y, rx, rz) or (y, rx, rz, z_off). z_off drops the
    section center for mild C919 radome droop (REF ~0.5 m tip vs cabin).
    Tip cap is short commercial dome — not a missile cone.
    """
    segs = segments or SEGMENTS
    bm = bmesh.new()

    def _unpack(st):
        y, rx, rz = st[0], st[1], st[2]
        z0 = st[3] if len(st) > 3 else 0.0
        return y, rx, rz, z0

    def ring_at(y, rx, rz, z0=0.0):
        ring = []
        for i in range(segs):
            ang = math.tau * i / segs
            ring.append(
                bm.verts.new((math.cos(ang) * rx, y, math.sin(ang) * rz + z0))
            )
        return ring

    rings = [ring_at(*_unpack(st)) for st in profile]
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    # Blunt parabolic tip: short axial throw, follows first-station droop.
    y0, rx0, rz0, z00 = _unpack(profile[0])
    tip_spec = [
        (0.018, 0.96),
        (0.034, 0.90),
        (0.048, 0.80),
        (0.058, 0.66),
        (0.066, 0.48),
    ]
    prev = rings[0]
    for dy, s in tip_spec:
        ring = ring_at(y0 + dy, rx0 * s, rz0 * s, z00)
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((prev[i], ring[i], ring[j], prev[j]))
        prev = ring
    # Pole almost flush with last ring — rounded dome end.
    pole = bm.verts.new(
        (0.0, y0 + 0.066 + min(rx0, rz0) * 0.48 * 0.50, z00)
    )
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((pole, prev[i], prev[j]))
    return finish(bm)


def pose_wing(bm, side):
    bmesh.ops.rotate(
        bm,
        verts=list(bm.verts),
        cent=(0, 0, 0),
        matrix=Matrix.Rotation(side * math.radians(5), 4, "Y"),
    )
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0, 0.2, -0.35))


def _wing_airfoil_yz(yle, yte, thick, n_half=12):
    """Closed supercritical-ish airfoil as (y, z) points.

    Order: LE upper 鈫?TE upper 鈫?TE lower 鈫?near-LE lower.
    Fuller rounded nose, flatter upper aft, mild rear loading.
    """
    chord = max(yle - yte, 0.08)
    pts = []

    def thick_at(t):
        peak = 0.30
        if t <= 1e-6:
            return 0.0
        if t < 0.05:
            # Rounded LE bulb
            return thick * math.sin(0.5 * math.pi * (t / 0.05)) * 0.62
        if t <= peak:
            u = (t - 0.05) / (peak - 0.05)
            return thick * (0.62 + 0.38 * math.sin(0.5 * math.pi * u))
        u = (t - peak) / (1.0 - peak)
        # Flatter upper aft (supercritical), thin TE
        return thick * ((1.0 - u) ** 1.15) * (0.92 + 0.08 * (1.0 - u))

    def camber_at(t):
        return 0.020 * chord * math.sin(math.pi * (t ** 0.88))

    for i in range(n_half):
        t = i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        z_scale = 0.58 if t < 0.42 else 0.46
        y = yle - t * chord
        z = cam + yt * z_scale
        pts.append((y, z))

    for i in range(1, n_half - 1):
        t = 1.0 - i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        z_scale = 0.50 if t < 0.50 else 0.60
        y = yle - t * chord
        z = cam - yt * z_scale
        pts.append((y, z))
    return pts


def wing(side):
    """Swept supercritical loft: broad root, gradual taper, mild TE kink."""
    # More stations = smoother LE/TE (less triangular)
    stations = [
        (1.30, 3.58, -2.82, 0.68),
        (2.20, 3.32, -3.05, 0.60),
        (3.40, 2.95, -3.25, 0.52),
        (5.00, 2.42, -3.45, 0.44),   # TE kink (deepest)
        (6.60, 1.88, -3.28, 0.38),
        (8.40, 1.35, -3.02, 0.32),
        (10.4, 0.78, -2.62, 0.25),
        (12.4, 0.22, -2.22, 0.19),
        (14.2, -0.28, -1.92, 0.14),
        (15.5, -0.58, -1.74, 0.11),
        (16.05, -0.72, -1.66, 0.090),
    ]
    n_half = 13
    bm = bmesh.new()
    rings = []
    for sx, yle, yte, th in stations:
        ring = []
        for y, z in _wing_airfoil_yz(yle, yte, th, n_half):
            ring.append(bm.verts.new((side * sx, y, z)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass

    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass

    # Subtle upper TE hinge crease
    for ri, (sx, yle, yte, th) in enumerate(stations[:-1]):
        chord = yle - yte
        y_hinge = yte + chord * 0.20
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.035 and v.co.z > 0.01:
                v.co.z -= 0.010

    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def winglet(side):
    """Blended winglet: continuous arc from tip, upward + slightly outboard."""
    bm = bmesh.new()
    # Match wing tip station chord/thickness, then curl up
    tip_x0 = 16.00
    # (dx, y_le, y_te, z_mid, thick) 鈥?first row 鈮?wing tip airfoil
    path = [
        (0.00, -0.72, -1.66, 0.00, 0.088),
        (0.10, -0.78, -1.62, 0.08, 0.080),
        (0.22, -0.88, -1.58, 0.28, 0.068),
        (0.34, -0.98, -1.55, 0.58, 0.055),
        (0.44, -1.08, -1.54, 0.95, 0.042),
        (0.52, -1.16, -1.55, 1.30, 0.032),
        (0.58, -1.24, -1.58, 1.62, 0.024),
        (0.60, -1.30, -1.62, 1.88, 0.016),
    ]
    n_half = 9
    rings = []
    for dx, yle, yte, z_mid, th in path:
        local = _wing_airfoil_yz(yle, yte, th, n_half)
        ring = []
        for y, z in local:
            ring.append(bm.verts.new((side * (tip_x0 + dx), y, z + z_mid)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass
    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass

    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def _add_canoe_fairing(bm, cx, cy, cz, length, width, height):
    """Long slender flap-track canoe aligned with airflow (Y)."""
    n_len = 11
    n_rad = 10
    rings = []
    for i in range(n_len):
        t = i / (n_len - 1)
        # Sharp pointed ends, elongated mid
        s = math.sin(math.pi * t)
        s = max(s, 0.04) ** 0.70
        ww = width * 0.5 * s
        hh = height * 0.5 * s
        yy = cy - length * 0.58 + length * t
        ring = []
        for k in range(n_rad):
            a = math.tau * k / n_rad
            xz_x = math.cos(a) * ww
            xz_z = math.sin(a) * hh
            # Flatten top to hug wing underside
            if xz_z > 0:
                xz_z *= 0.40
            ring.append(bm.verts.new((cx + xz_x, yy, cz + xz_z)))
        rings.append(ring)

    for a, b in zip(rings, rings[1:]):
        for i in range(n_rad):
            j = (i + 1) % n_rad
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    try:
        aft = bm.verts.new((cx, cy - length * 0.58 - 0.04, cz - 0.01))
        fwd = bm.verts.new((cx, cy - length * 0.58 + length + 0.04, cz - 0.01))
        for i in range(n_rad):
            j = (i + 1) % n_rad
            bm.faces.new((aft, rings[0][j], rings[0][i]))
            bm.faces.new((fwd, rings[-1][i], rings[-1][j]))
    except ValueError:
        pass


def wing_flap_fairings(side):
    """Four slender canoe flap-track fairings under trailing edge per wing."""
    bm = bmesh.new()
    # Longer, slimmer canoes; pressed up under TE (cz closer to 0)
    fairings = [
        (4.10, -3.35, 1.75, 0.20, 0.24),
        (7.00, -3.18, 1.55, 0.17, 0.21),
        (10.00, -2.72, 1.35, 0.15, 0.18),
        (13.00, -2.20, 1.15, 0.12, 0.15),
    ]
    for sx, sy, length, width, height in fairings:
        _add_canoe_fairing(
            bm,
            side * sx,
            sy + 0.15,
            -0.16,
            length,
            width,
            height,
        )
    pose_wing(bm, side)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def wing_le_strip(side):
    """Subtle rounded leading-edge bead along the sweep."""
    bm = bmesh.new()
    beads = [
        (2.00, 3.35, 1.20),
        (4.20, 2.60, 1.30),
        (6.80, 1.80, 1.25),
        (9.80, 0.90, 1.20),
        (12.8, 0.05, 1.10),
        (14.8, -0.40, 0.85),
    ]
    for sx, sy, length in beads:
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.048, length * 0.45, 0.036))
        bmesh.ops.translate(bm, verts=created, vec=(side * sx, sy, 0.14))
    pose_wing(bm, side)
    return finish(bm)


def _tail_airfoil_2d(yle, yte, thick, n_half=11):
    """Closed airfoil in chord(Y) / thickness(T) plane. LE fuller, thinner TE."""
    chord = max(yle - yte, 0.06)
    pts = []

    def thick_at(t):
        peak = 0.28
        if t <= 1e-6:
            return 0.0
        if t < 0.06:
            return thick * math.sin(0.5 * math.pi * (t / 0.06)) * 0.70
        if t <= peak:
            u = (t - 0.06) / (peak - 0.06)
            return thick * (0.70 + 0.30 * math.sin(0.5 * math.pi * u))
        u = (t - peak) / (1.0 - peak)
        return thick * ((1.0 - u) ** 1.20) * 0.95

    def camber_at(t):
        return 0.012 * chord * math.sin(math.pi * (t ** 0.9))

    for i in range(n_half):
        t = i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        y = yle - t * chord
        # +T side
        pts.append((y, cam + yt * 0.55))
    for i in range(1, n_half - 1):
        t = 1.0 - i / (n_half - 1)
        yt = thick_at(t)
        cam = camber_at(t)
        y = yle - t * chord
        pts.append((y, cam - yt * 0.55))
    return pts


def stab(side):
    """Conventional low-mounted HT: swept airfoil loft, mild dihedral, elevator crease.

    NOT a T-tail. Root plants into aft fuselage; tip is clean squared-off with
    slightly rounded edges. Soft span/chord check vs C919 class (~12 m span).
    """
    # Local stations before placement: (x_span, y_le, y_te, thick)
    # Root chord ~2.7 m, tip ~0.85 m, half-span ~6.1 m → span ~12.2 m
    stations = [
        (0.88, 1.40, -1.30, 0.36),
        (1.80, 1.12, -1.20, 0.30),
        (2.90, 0.82, -1.10, 0.25),
        (4.00, 0.52, -0.98, 0.20),
        (4.95, 0.28, -0.86, 0.155),
        (5.65, 0.12, -0.74, 0.115),
        (6.10, 0.02, -0.62, 0.085),
    ]
    n_half = 11
    bm = bmesh.new()
    rings = []
    for sx, yle, yte, th in stations:
        ring = []
        for y, t in _tail_airfoil_2d(yle, yte, th, n_half):
            # thickness along Z for horizontal stab
            ring.append(bm.verts.new((side * sx, y, t)))
        rings.append(ring)

    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass
    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass

    # Subtle elevator hinge crease (~22% chord from TE), both surfaces
    for ri, (sx, yle, yte, th) in enumerate(stations[:-1]):
        chord = yle - yte
        y_hinge = yte + chord * 0.22
        for v in rings[ri]:
            if abs(v.co.y - y_hinge) < chord * 0.04:
                # push slightly toward midplane of airfoil (shallow seam)
                v.co.z *= 0.82

    # Mild dihedral (~6°) about local root, then place on aft fuselage
    bmesh.ops.rotate(
        bm,
        verts=list(bm.verts),
        cent=(0, 0, 0),
        matrix=Matrix.Rotation(side * math.radians(6.0), 4, "Y"),
    )
    # Mid/upper rear fuselage — flush with skin
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0.0, -16.35, 0.90))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def fuselage_radius_at(y):
    """Mean radius from NOSE/FUSELAGE elliptical stations (keeps fin root on skin)."""
    return _radius_at_y(y)


def vertical_tail():
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


def rudder():
    """Red rudder livery strip along fin TE — thin, follows lofted TE, not a rod."""
    bm = bmesh.new()
    # Follows vertical_tail TE with a slim chord strip on +X face
    shape = [
        (-18.20, 1.6),
        (-18.05, 1.6),
        (-17.88, 7.6),
        (-18.05, 7.6),
    ]
    verts = [bm.verts.new((0.095, y, z)) for y, z in shape]
    face = bm.faces.new(verts)
    extruded = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in extruded["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0.045, 0, 0))
    return finish(bm)


def tail_cone_cap():
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


def _engine_xz(side):
    return side * 6.2, -1.95


def _add_lathe_rings(bm, x, z, profile, segs=40, close_aft=False, close_fwd=False):
    """Connect circular rings of (y, radius). Optional end caps."""
    rings = []
    for y, radius in profile:
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            ring.append(
                bm.verts.new((x + math.cos(a) * radius, y, z + math.sin(a) * radius))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    if close_fwd and rings:
        yf = profile[0][0]
        pole = bm.verts.new((x, yf, z))
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((pole, rings[0][j], rings[0][i]))
    if close_aft and rings:
        ya = profile[-1][0]
        pole = bm.verts.new((x, ya, z))
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((pole, rings[-1][i], rings[-1][j]))
    return rings


def engine(side):
    """LEAP-like high-bypass nacelle: fan case break, aft body, core+bypass nozzle."""
    bm = bmesh.new()
    x, z = _engine_xz(side)
    segs = 40
    # Outer skin aft of rounded lip (lip is a separate mesh). Forward = +Y.
    outer = [
        (2.62, 1.12),   # aft of lip inner attach
        (2.35, 1.18),   # fan-case max diameter
        (1.70, 1.165),
        (1.10, 1.12),   # fan-case / aft-body break
        (0.55, 1.06),
        (0.00, 1.02),
        (-0.55, 0.96),
        (-1.10, 0.88),
        (-1.45, 0.80),  # bypass nozzle outer
        (-1.72, 0.74),
    ]
    _add_lathe_rings(bm, x, z, outer, segs=segs)

    # Subtle chevron hint: scalloped aft edge ring (low poly)
    y_chev, r_chev = -1.78, 0.72
    chev_n = 12
    chev_outer, chev_inner = [], []
    for i in range(chev_n):
        a0 = math.tau * i / chev_n
        a1 = math.tau * (i + 0.5) / chev_n
        # tip out / valley in
        for a, rr, yoff in (
            (a0, r_chev + 0.035, 0.00),
            (a1, r_chev - 0.01, -0.06),
        ):
            chev_outer.append(
                bm.verts.new((x + math.cos(a) * rr, y_chev + yoff, z + math.sin(a) * rr))
            )
    # Build strip against a simple aft ring
    aft = []
    for i in range(chev_n * 2):
        a = math.tau * i / (chev_n * 2)
        aft.append(
            bm.verts.new((x + math.cos(a) * (r_chev - 0.04), y_chev - 0.10, z + math.sin(a) * (r_chev - 0.04)))
        )
    for i in range(len(chev_outer)):
        j = (i + 1) % len(chev_outer)
        try:
            bm.faces.new((chev_outer[i], chev_outer[j], aft[j], aft[i]))
        except ValueError:
            pass

    # Core nozzle (inner plug look)
    core = [
        (-1.15, 0.50),
        (-1.45, 0.44),
        (-1.85, 0.36),
        (-2.05, 0.22),
    ]
    _add_lathe_rings(bm, x, z, core, segs=24, close_aft=True)

    # Pointed spinner ogive (visible in intake)
    spin = [
        (2.55, 0.40),
        (2.72, 0.32),
        (2.88, 0.22),
        (3.00, 0.12),
        (3.08, 0.04),
    ]
    _add_lathe_rings(bm, x, z, spin, segs=24, close_fwd=True, close_aft=True)

    return finish(bm)


def _add_twisted_blade(bm, cx0, cy, cz0, ang, r0, r1):
    """Wide-chord LEAP-like twisted airfoil blade (not a thick spoke)."""
    n = 6
    stations = []
    for si in range(n):
        t = si / (n - 1)
        r = r0 + t * (r1 - r0)
        # Wide chord near hub, still broad at tip (LEAP wide-chord)
        chord = 0.34 * (1.0 - 0.28 * t)
        thick = 0.022 * (1.0 - 0.40 * t)
        pitch = math.radians(42.0 - 22.0 * t)
        sect = [
            (0.0, chord * 0.50),
            (thick * 0.55, chord * 0.08),
            (0.0, -chord * 0.50),
            (-thick * 0.50, chord * 0.06),
        ]
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        cos_p, sin_p = math.cos(pitch), math.sin(pitch)
        ring = []
        for thick_l, chord_l in sect:
            ly = chord_l * cos_p - thick_l * sin_p
            lt = chord_l * sin_p + thick_l * cos_p
            px = cx0 + cos_a * r + (-sin_a) * lt
            py = cy + ly
            pz = cz0 + sin_a * r + cos_a * lt
            ring.append(bm.verts.new((px, py, pz)))
        stations.append(ring)
    for a, b in zip(stations, stations[1:]):
        for i in range(4):
            j = (i + 1) % 4
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    try:
        bm.faces.new(stations[0])
        bm.faces.new(list(reversed(stations[-1])))
    except ValueError:
        pass


def engine_fan(side):
    """Open-intake fan: hub + 18 wide-chord metallic blades (~LEAP-1C)."""
    bm = bmesh.new()
    x, z = _engine_xz(side)
    y_fan = 2.70
    hub_m = Matrix.Translation((x, y_fan, z)) @ Matrix.Rotation(math.radians(90), 4, "X")
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=28,
        radius1=0.28,
        radius2=0.28,
        depth=0.14,
        matrix=hub_m,
    )
    n_blades = 18
    hub_r = 0.28
    tip_r = 0.96  # ~1.92 m diameter, near 77 in LEAP-1C
    for i in range(n_blades):
        ang = math.tau * i / n_blades
        _add_twisted_blade(bm, x, y_fan, z, ang, hub_r, tip_r)
    return finish(bm)


def engine_lip_ring(side):
    """Thick rounded inlet lip (toroidal LE profile) 鈥?open center for fan view."""
    bm = bmesh.new()
    x, z = _engine_xz(side)
    segs = 40
    # Tube center at intake circle; cross-section sweeps outer鈫扡E鈫抜nner
    r_c = 1.10
    lip_r = 0.12
    y_c = 2.92
    tube_segs = 8
    rings = []
    for ti in range(tube_segs + 1):
        # phi: 0 = outer aft attach, pi/2 = forward LE, pi = inner aft
        phi = math.pi * ti / tube_segs
        rr = r_c + lip_r * math.cos(phi)
        yy = y_c + lip_r * math.sin(phi)
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            ring.append(
                bm.verts.new((x + math.cos(a) * rr, yy, z + math.sin(a) * rr))
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], b[i], b[j], a[j]))
    return finish(bm)


def engine_pylon(side):
    """Wing-to-nacelle pylon with soft chord taper (not a raw box)."""
    bm = bmesh.new()
    # Cross-sections from wing underside down to nacelle crown (loft).
    # Each: (x, y, z, half_chord_y, half_thick_x)
    secs = [
        (side * 4.30, 1.40, -0.40, 0.85, 0.11),
        (side * 4.75, 1.28, -0.75, 0.95, 0.13),
        (side * 5.25, 1.18, -1.10, 1.05, 0.15),
        (side * 5.70, 1.10, -1.40, 1.00, 0.17),
        (side * 6.00, 1.05, -1.65, 0.88, 0.19),
    ]
    rings = []
    for cx, cy, cz, hc, ht in secs:
        # Diamond-ish section in X/Y, extruded along height via loft
        pts = [
            (cx + side * ht, cy, cz),
            (cx, cy + hc, cz),
            (cx - side * ht, cy, cz),
            (cx, cy - hc * 0.85, cz),
        ]
        rings.append([bm.verts.new(p) for p in pts])
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))

    # Soft blend blobs at wing join + nacelle join
    for cx, cy, cz, sx, sy, sz in (
        (side * 4.25, 1.35, -0.35, 0.35, 0.55, 0.28),
        (side * 6.05, 1.05, -1.70, 0.40, 0.50, 0.32),
    ):
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(sx, sy, sz))
        bmesh.ops.translate(bm, verts=created, vec=(cx, cy, cz))
    return finish(bm)


def gear(height, wheels):
    bm = bmesh.new()
    strut = Matrix.Translation((0, 0, -height / 2))
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=10,
        radius1=0.09,
        radius2=0.12,
        depth=height,
        matrix=strut,
    )
    for x in wheels:
        wheel = Matrix.Translation((x, 0, -height)) @ Matrix.Rotation(
            math.radians(90), 4, "Y"
        )
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=16,
            radius1=0.38,
            radius2=0.38,
            depth=0.2,
            matrix=wheel,
        )
    return finish(bm)


def box(size, location):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, verts=list(bm.verts), vec=size)
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=location)
    return finish(bm)


def add_rounded_slab(bm, width, height, depth, corner_r, segs=5, matrix=None):
    """Rounded-rectangle slab: width along Y, height along Z, thickness along X.

    Built as a true filleted panel (not a sharp cube) so cabin windows/doors
    read as airliner ovals rather than Lego bricks.
    """
    hw, hh = width * 0.5, height * 0.5
    r = min(corner_r, hw * 0.48, hh * 0.48)
    # CCW outline in YZ when viewed from +X
    corners = [
        (-hw + r, -hh + r, math.pi, 1.5 * math.pi),       # bottom-left
        (hw - r, -hh + r, 1.5 * math.pi, 2.0 * math.pi),  # bottom-right
        (hw - r, hh - r, 0.0, 0.5 * math.pi),             # top-right
        (-hw + r, hh - r, 0.5 * math.pi, math.pi),        # top-left
    ]
    outline = []
    for cy, cz, a0, a1 in corners:
        for i in range(segs):
            t = i / float(segs)
            a = a0 + (a1 - a0) * t
            outline.append((cy + math.cos(a) * r, cz + math.sin(a) * r))

    hd = depth * 0.5
    front = [bm.verts.new((hd, y, z)) for y, z in outline]
    back = [bm.verts.new((-hd, y, z)) for y, z in outline]
    n = len(outline)
    bm.faces.new(list(reversed(front)))  # +X outward
    bm.faces.new(back)  # -X outward
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((back[i], front[i], front[j], back[j]))

    verts = front + back
    if matrix is not None:
        bmesh.ops.transform(bm, verts=verts, matrix=matrix)
    return verts


def add_rounded_decal(bm, width, height, corner_r, segs=6, matrix=None, x_offset=0.0):
    """Single-sided rounded rect in YZ (no thickness) 鈥?flush cabin glass/frames."""
    hw, hh = width * 0.5, height * 0.5
    r = min(corner_r, hw * 0.48, hh * 0.48)
    corners = [
        (-hw + r, -hh + r, math.pi, 1.5 * math.pi),
        (hw - r, -hh + r, 1.5 * math.pi, 2.0 * math.pi),
        (hw - r, hh - r, 0.0, 0.5 * math.pi),
        (-hw + r, hh - r, 0.5 * math.pi, math.pi),
    ]
    outline = []
    for cy, cz, a0, a1 in corners:
        for i in range(segs):
            t = i / float(segs)
            a = a0 + (a1 - a0) * t
            outline.append(bm.verts.new((x_offset, cy + math.cos(a) * r, cz + math.sin(a) * r)))
    # Backface too so both sides of fuselage read in Three.js
    face = bm.faces.new(list(reversed(outline)))
    # Duplicate flipped for -X viewing when mirrored via matrix
    if matrix is not None:
        bmesh.ops.transform(bm, verts=outline, matrix=matrix)
    return outline


def _fuselage_window_ys():
    """Cabin window stations: skip door gaps (forward / overwing / aft / service)."""
    door_gaps = [
        (12.40, 13.75),   # L1 passenger (clear of pane half-width)
        (13.95, 14.90),   # forward service
        (1.25, 2.35),     # overwing exit (raised / slightly forward)
        (-12.10, -10.85), # aft passenger
    ]
    ys = []
    y = 12.25  # start aft of L1 / service cluster
    step = 0.68
    while y > -10.5:
        if not any(a <= y <= b for a, b in door_gaps):
            ys.append(round(y, 3))
        y -= step
    return ys


# Nose stations: (y, rx, rz). Y toward the nose (+Y).
# rx = lateral half-width, rz = vertical half-height.
# Elongated C919 radome: less spherical mid-bulge, tip stays softly rounded.
# Join at y=14.85 matches the circular fuselage (rx=rz=2.06).
NOSE_PROFILE = [
    # nose-ref: REF_C919 meters taper + mild droop (4th = z_off). Tip kept
    # commercial-blunt (not REF 0.28 missile, not old 0.55 fat ball).
    # Join at y=14.85 still (2.06, 2.06, 0).
    (19.88, 0.40, 0.36, -0.42),
    (19.72, 0.54, 0.50, -0.40),
    (19.55, 0.68, 0.60, -0.37),
    (19.35, 0.82, 0.74, -0.34),
    (19.12, 0.96, 0.88, -0.30),
    (18.88, 1.10, 1.04, -0.27),
    (18.60, 1.24, 1.18, -0.23),
    (18.35, 1.34, 1.30, -0.20),
    (18.10, 1.44, 1.40, -0.17),
    (17.85, 1.52, 1.48, -0.14),  # windshield forward belt
    (17.60, 1.58, 1.55, -0.12),
    (17.35, 1.64, 1.62, -0.10),
    (17.05, 1.70, 1.70, -0.08),
    (16.75, 1.76, 1.78, -0.06),
    (16.45, 1.82, 1.84, -0.05),
    (16.15, 1.87, 1.90, -0.04),  # brow / aft glass
    (15.85, 1.92, 1.94, -0.03),
    (15.55, 1.96, 1.98, -0.02),
    (15.25, 2.00, 2.01, -0.01),
    (15.00, 2.03, 2.04, -0.005),
    (14.85, 2.06, 2.06, 0.0),
]

# fuse1: elliptical stations 鈥?long near-cylindrical cabin with NATURAL
# FWD/AFT curvature (less uniform pipe, no abrupt necking into blunt cut).
# Mid cabin slightly taller crown (rz > rx) for commercial roundness.
FUSELAGE_PROFILE = [
    (14.85, 2.060, 2.060),  # join nose (exact)
    (13.40, 2.070, 2.078),
    (11.50, 2.080, 2.090),
    (9.00, 2.086, 2.098),
    (6.00, 2.088, 2.102),
    (3.00, 2.088, 2.102),
    (0.00, 2.088, 2.102),
    (-3.00, 2.088, 2.100),
    (-6.00, 2.084, 2.096),
    (-9.00, 2.072, 2.082),
    (-11.50, 2.050, 2.058),
    (-13.40, 2.010, 2.015),
    (-14.80, 1.940, 1.945),
    (-15.80, 1.820, 1.825),
    (-16.55, 1.660, 1.670),
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
]

RADIUS_STATIONS = NOSE_PROFILE + FUSELAGE_PROFILE[1:]


def _section_at_y(y):
    """(rx, rz) at station y. Nose stations are elliptical; fuselage is circular."""
    rx, rz, _z0 = _section_full_at_y(y)
    return (rx, rz)


def _section_full_at_y(y):
    """(rx, rz, z_off) — z_off is nose droop (0 on fuselage)."""
    stations = RADIUS_STATIONS

    def unpack(s):
        rx = s[1]
        rz = s[2] if len(s) > 2 else s[1]
        z0 = s[3] if len(s) > 3 else 0.0
        return rx, rz, z0

    if y >= stations[0][0]:
        return unpack(stations[0])
    if y <= stations[-1][0]:
        return unpack(stations[-1])
    for s0, s1 in zip(stations, stations[1:]):
        y0, y1 = s0[0], s1[0]
        if y1 <= y <= y0:
            t = (y0 - y) / (y0 - y1 + 1e-9)
            rx0, rz0, z00 = unpack(s0)
            rx1, rz1, z01 = unpack(s1)
            return (
                rx0 + (rx1 - rx0) * t,
                rz0 + (rz1 - rz0) * t,
                z00 + (z01 - z00) * t,
            )
    return (2.08, 2.08, 0.0)


def _radius_at_y(y):
    """Mean radius (legacy callers: panel rings, antennas, gear doors)."""
    rx, rz = _section_at_y(y)
    return 0.5 * (rx + rz)


def add_rounded_frame(bm, width, height, depth, corner_r, border, segs=6, matrix=None):
    """Hollow picture-frame rim (outer rounded rect bridged to inner)."""
    hw, hh = width * 0.5, height * 0.5
    r = min(corner_r, hw * 0.48, hh * 0.48)
    bi = border
    hw_i, hh_i = hw - bi, hh - bi
    r_i = max(0.01, r - bi * 0.5)

    def outline(hww, hhh, rr):
        corners = [
            (-hww + rr, -hhh + rr, math.pi, 1.5 * math.pi),
            (hww - rr, -hhh + rr, 1.5 * math.pi, 2.0 * math.pi),
            (hww - rr, hhh - rr, 0.0, 0.5 * math.pi),
            (-hww + rr, hhh - rr, 0.5 * math.pi, math.pi),
        ]
        pts = []
        for cy, cz, a0, a1 in corners:
            for i in range(segs):
                t = i / float(segs)
                a = a0 + (a1 - a0) * t
                pts.append((cy + math.cos(a) * rr, cz + math.sin(a) * rr))
        return pts

    outer = outline(hw, hh, r)
    inner = outline(hw_i, hh_i, r_i)
    hd = depth * 0.5
    n = len(outer)
    # Front rim (+X)
    fo = [bm.verts.new((hd, y, z)) for y, z in outer]
    fi = [bm.verts.new((hd, y, z)) for y, z in inner]
    bo = [bm.verts.new((-hd, y, z)) for y, z in outer]
    bi_v = [bm.verts.new((-hd, y, z)) for y, z in inner]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((fo[i], fo[j], fi[j], fi[i]))          # front rim
        bm.faces.new((bo[j], bo[i], bi_v[i], bi_v[j]))      # back rim
        bm.faces.new((bo[i], bo[j], fo[j], fo[i]))          # outer wall
        bm.faces.new((fi[i], fi[j], bi_v[j], bi_v[i]))      # inner wall
    verts = fo + fi + bo + bi_v
    if matrix is not None:
        bmesh.ops.transform(bm, verts=verts, matrix=matrix)
    return verts


def cabin_windows():
    """Rounded-rect cabin panes recessed into skin 鈥?transparent glass (axis-aligned)."""
    bm = bmesh.new()
    pane_w, pane_h = 0.27, 0.33
    corner = 0.082
    z = 0.56
    for y in _fuselage_window_ys():
        rx, _rz = _section_at_y(y)
        x_off = rx - 0.022  # recess into skin
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_slab(bm, pane_w, pane_h, 0.014, corner, segs=6, matrix=m)
    return finish(bm)


def cabin_window_frames():
    """Thin restrained bezels around each pane."""
    bm = bmesh.new()
    z = 0.56
    for y in _fuselage_window_ys():
        rx, _rz = _section_at_y(y)
        x_off = rx + 0.002  # hair proud for readable lip
        for side in (1, -1):
            m = Matrix.Translation((side * x_off, y, z))
            if side < 0:
                m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
            add_rounded_frame(
                bm, 0.31, 0.37, 0.008, 0.086, border=0.018, segs=6, matrix=m
            )
    return finish(bm)


def _lerp(a, b, t):
    return a + (b - a) * t


def _canopy_point(a, y, r_off):
    """Point on the elliptical nose section. a=0 is crown (+Z).

    Offset is along the section normal so glass/frames hug the skin
    instead of inflating into a larger circle. Honors nose droop z_off.
    """
    rx, rz, z0 = _section_full_at_y(y)
    # Unit ellipse param (a measured from +Z): x = rx*sin(a), z = rz*cos(a)
    sx, sz = math.sin(a), math.cos(a)
    # Outward normal of ellipse x^2/rx^2 + z^2/rz^2 = 1
    nx, nz = sx / max(rx, 1e-6), sz / max(rz, 1e-6)
    nlen = math.hypot(nx, nz) or 1.0
    nx, nz = nx / nlen, nz / nlen
    return (sx * rx + nx * r_off, y, sz * rz + nz * r_off + z0)


def _cockpit_pane_defs(expand=0.0):
    """nose-ref: 4 panes on REF windshield belt (narrow Z, front+side).

    Layout: WS_L/WS_R forward, SW_L/SW_R aft cheeks. Soft Y from REF loops /
    dark-belt blend: forward ~17.85, brow ~15.9. Actual openings still via
    knife_project (ws4); these shells are flush Transmission placeholders.
    Angle 0 = crown (+Z). expand ignored.
    """
    _ = expand

    def _sm(t):
        t = min(1.0, max(0.0, t))
        return t * t * (3.0 - 2.0 * t)

    def fwd_y_fwd(a):
        # center slightly ahead of corners (smooth top silhouette)
        t = abs(a) / math.radians(42)
        return _lerp(17.85, 17.68, _sm(t))

    def fwd_y_aft(a):
        t = abs(a) / math.radians(42)
        return _lerp(16.95, 16.72, _sm(t))

    def side_y_fwd(a):
        t = (abs(a) - math.radians(55)) / (math.radians(100) - math.radians(55))
        return _lerp(16.90, 16.45, _sm(t))

    def side_y_aft(a):
        t = (abs(a) - math.radians(55)) / (math.radians(100) - math.radians(55))
        return _lerp(16.15, 15.70, _sm(t))

    gap = math.radians(1.2)
    return [
        {
            "name": "SW_L",
            "a0": -math.radians(100),
            "a1": -math.radians(52),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 16,
            "segs_y": 10,
        },
        {
            "name": "WS_L",
            "a0": -math.radians(46),
            "a1": -gap,
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 14,
            "segs_y": 10,
        },
        {
            "name": "WS_R",
            "a0": gap,
            "a1": math.radians(46),
            "y_fwd": fwd_y_fwd,
            "y_aft": fwd_y_aft,
            "segs_a": 14,
            "segs_y": 10,
        },
        {
            "name": "SW_R",
            "a0": math.radians(52),
            "a1": math.radians(100),
            "y_fwd": side_y_fwd,
            "y_aft": side_y_aft,
            "segs_a": 16,
            "segs_y": 10,
        },
    ]



def _add_canopy_pane(bm, pane, r_off):
    """Dense curved shell sector; Y span may vary with azimuth (trapezoid)."""
    a0, a1 = pane["a0"], pane["a1"]
    segs_a, segs_y = pane["segs_a"], pane["segs_y"]
    grid = []
    for j in range(segs_y + 1):
        ty = j / segs_y
        row = []
        for i in range(segs_a + 1):
            ta = i / segs_a
            a = _lerp(a0, a1, ta)
            y = _lerp(pane["y_fwd"](a), pane["y_aft"](a), ty)
            row.append(bm.verts.new(_canopy_point(a, y, r_off)))
        grid.append(row)
    for j in range(segs_y):
        for i in range(segs_a):
            bm.faces.new(
                (grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1])
            )


def _add_shell_sector(bm, ys, a0, a1, r_off, segs_a):
    """Partial lathe shell (single-sided) on the nose surface."""
    rings = []
    for y in ys:
        ring = []
        for i in range(segs_a + 1):
            t = i / segs_a
            a = a0 + (a1 - a0) * t
            ring.append(bm.verts.new(_canopy_point(a, y, r_off)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(segs_a):
            bm.faces.new((ra[i], rb[i], rb[i + 1], ra[i + 1]))


def _add_raised_strip(bm, ys, a0, a1, r_in, r_out, segs_a=3):
    """Raised frame ribbon with real radial thickness (no floating cubes)."""
    _add_shell_sector(bm, ys, a0, a1, r_out, segs_a)
    for a in (a0, a1):
        prev = None
        for y in ys:
            v0 = bm.verts.new(_canopy_point(a, y, r_in))
            v1 = bm.verts.new(_canopy_point(a, y, r_out))
            if prev is not None:
                bm.faces.new((prev[0], prev[1], v1, v0))
            prev = (v0, v1)


def _add_curve_ribbon(bm, a_list, y_fn, half_y, r_in, r_out):
    """One continuous raised ribbon following y(a) 鈥?no stepped beads."""
    n = len(a_list)
    if n < 2:
        return
    ou, ol, iu, il = [], [], [], []
    for a in a_list:
        y = y_fn(a)
        ou.append(bm.verts.new(_canopy_point(a, y + half_y, r_out)))
        ol.append(bm.verts.new(_canopy_point(a, y - half_y, r_out)))
        iu.append(bm.verts.new(_canopy_point(a, y + half_y, r_in)))
        il.append(bm.verts.new(_canopy_point(a, y - half_y, r_in)))
    for i in range(n - 1):
        bm.faces.new((ou[i], ou[i + 1], ol[i + 1], ol[i]))
        bm.faces.new((iu[i + 1], iu[i], il[i], il[i + 1]))
        bm.faces.new((ou[i], iu[i], iu[i + 1], ou[i + 1]))
        bm.faces.new((ol[i + 1], il[i + 1], il[i], ol[i]))



def _add_canopy_pane_solid(bm, pane, r_out, r_in):
    """Double shell (~1–2 cm) so glass has thickness for glTF/EEVEE."""
    a0, a1 = pane["a0"], pane["a1"]
    segs_a, segs_y = pane["segs_a"], pane["segs_y"]
    outer, inner = [], []
    for j in range(segs_y + 1):
        ty = j / segs_y
        ro, ri = [], []
        for i in range(segs_a + 1):
            ta = i / segs_a
            a = _lerp(a0, a1, ta)
            y = _lerp(pane["y_fwd"](a), pane["y_aft"](a), ty)
            ro.append(bm.verts.new(_canopy_point(a, y, r_out)))
            ri.append(bm.verts.new(_canopy_point(a, y, r_in)))
        outer.append(ro)
        inner.append(ri)
    for j in range(segs_y):
        for i in range(segs_a):
            bm.faces.new(
                (outer[j][i], outer[j + 1][i], outer[j + 1][i + 1], outer[j][i + 1])
            )
            # inward face (reverse winding)
            bm.faces.new(
                (inner[j][i + 1], inner[j + 1][i + 1], inner[j + 1][i], inner[j][i])
            )
    # rim between outer/inner
    for j in range(segs_y + 1):
        for i, border in (
            (0, True),
            (segs_a, True),
        ):
            pass
    for i in range(segs_a):
        # fwd rim j=0, aft rim j=segs_y
        for j in (0, segs_y):
            o0, o1 = outer[j][i], outer[j][i + 1]
            i0, i1 = inner[j][i], inner[j][i + 1]
            if j == 0:
                bm.faces.new((o0, i0, i1, o1))
            else:
                bm.faces.new((o1, i1, i0, o0))
    for j in range(segs_y):
        for i in (0, segs_a):
            o0, o1 = outer[j][i], outer[j + 1][i]
            i0, i1 = inner[j][i], inner[j + 1][i]
            if i == 0:
                bm.faces.new((o0, o1, i1, i0))
            else:
                bm.faces.new((o1, o0, i0, i1))


def cockpit_pane_mesh(pane_name):
    """One named pane mesh (WS_L / WS_R / SW_L / SW_R)."""
    bm = bmesh.new()
    pane = None
    for p in _cockpit_pane_defs():
        if p["name"] == pane_name:
            pane = dict(p)
            break
    if pane is None:
        raise ValueError(pane_name)
    pane["segs_a"] = max(pane["segs_a"], 24)
    pane["segs_y"] = max(pane["segs_y"], 16)
    # flush: outer ~6 mm proud, inner ~10 mm inset → ~1.6 cm thick
    _add_canopy_pane_solid(bm, pane, r_out=0.004, r_in=-0.008)  # ws4 flush placeholder
    return finish(bm)


def cockpit_windshield():
    """ws3: combined four panes (legacy single object; prefer cockpit_pane_mesh)."""
    bm = bmesh.new()
    for pane in _cockpit_pane_defs():
        pane = dict(pane)
        pane["segs_a"] = max(pane["segs_a"], 24)
        pane["segs_y"] = max(pane["segs_y"], 16)
        _add_canopy_pane_solid(bm, pane, r_out=0.004, r_in=-0.008)  # ws4 flush placeholder
    return finish(bm)


def cockpit_mask():
    """ws3: removed — return empty mesh so any stale call is harmless."""
    bm = bmesh.new()
    return finish(bm)


def cockpit_frames():
    """ws3: narrow black seals 3–6 cm + thin center/corner pillars (no faceplate)."""
    bm = bmesh.new()
    r_off = 0.011  # just outside glass outer

    # Center pillar ~4 cm arc ≈ 1.1°
    _add_shell_sector(
        bm,
        [17.90, 17.45, 17.00, 16.55, 16.20],
        -math.radians(0.55),
        math.radians(0.55),
        r_off,
        segs_a=2,
    )
    # Corner posts front/side
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(46.9)
        a1 = sign * math.radians(48.3)
        lo, hi = (a0, a1) if a0 < a1 else (a1, a0)
        _add_shell_sector(
            bm,
            [17.75, 17.20, 16.70, 16.25],
            lo,
            hi,
            r_off,
            segs_a=2,
        )
    # Side aft posts
    for sign in (-1.0, 1.0):
        a0 = sign * math.radians(104.2)
        a1 = sign * math.radians(105.8)
        lo, hi = (a0, a1) if a0 < a1 else (a1, a0)
        _add_shell_sector(
            bm,
            [16.85, 16.35, 15.95, 15.65],
            lo,
            hi,
            r_off,
            segs_a=2,
        )

    def sill_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(17.88, 17.70, t * t * (3 - 2 * t))
        t = (aa - math.radians(50)) / (math.radians(100) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.95, 16.50, t * t * (3 - 2 * t))

    def brow_y(a):
        aa = abs(a)
        if aa <= math.radians(47.5):
            t = aa / math.radians(47.5)
            return _lerp(16.92, 16.70, t * t * (3 - 2 * t))
        t = (aa - math.radians(50)) / (math.radians(100) - math.radians(50) + 1e-9)
        t = min(1.0, max(0.0, t))
        return _lerp(16.10, 15.75, t * t * (3 - 2 * t))

    def _seal_strip(a0, a1, y_fn, half_y=0.022, n=28):
        """~4.4 cm seal half-width along Y on canopy."""
        a_list = [_lerp(a0, a1, i / float(n)) for i in range(n + 1)]
        ou, ol = [], []
        for a in a_list:
            y = y_fn(a)
            ou.append(bm.verts.new(_canopy_point(a, y + half_y, r_off)))
            ol.append(bm.verts.new(_canopy_point(a, y - half_y, r_off)))
        for i in range(n):
            bm.faces.new((ou[i], ou[i + 1], ol[i + 1], ol[i]))

    spans = [
        (-math.radians(100), -math.radians(50)),
        (-math.radians(47.5), -math.radians(1.2)),
        (math.radians(1.2), math.radians(47.5)),
        (math.radians(50), math.radians(100)),
    ]
    for a0, a1 in spans:
        _seal_strip(a0, a1, sill_y, 0.022)
        _seal_strip(a0, a1, brow_y, 0.022)

    return finish(bm)


def cockpit_cabin_shell():
    """ws3: simple dark cabin tube + dash silhouette visible through glass."""
    bm = bmesh.new()
    # Inner tube under windshield belt
    ys = [17.95, 17.40, 16.85, 16.30, 15.80, 15.30]
    segs = 28
    scale = 0.82
    rings = []
    for y in ys:
        rx, rz, z0 = _section_full_at_y(y)
        ring = []
        for i in range(segs):
            a = math.tau * i / segs
            # a_canopy uses 0=crown from +Z; here full circle from +X
            x = math.cos(a) * rx * scale
            z = math.sin(a) * rz * scale + z0
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    # Dash shelf under sill (dark board)
    dash_y = 17.35
    dash_z = 0.55
    dash_x = 0.95
    dash_depth = 0.55
    corners = [
        (-dash_x, dash_y, dash_z),
        (dash_x, dash_y, dash_z),
        (dash_x, dash_y - dash_depth, dash_z),
        (-dash_x, dash_y - dash_depth, dash_z),
        (-dash_x, dash_y, dash_z - 0.08),
        (dash_x, dash_y, dash_z - 0.08),
        (dash_x, dash_y - dash_depth, dash_z - 0.08),
        (-dash_x, dash_y - dash_depth, dash_z - 0.08),
    ]
    vs = [bm.verts.new(c) for c in corners]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 3, 7, 4),
        (1, 5, 6, 2),
        (0, 4, 5, 1),
        (3, 2, 6, 7),
    ]
    for f in faces:
        bm.faces.new(tuple(vs[i] for i in f))
    return finish(bm)



def punch_windshield_openings(nose_obj):
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
    # nose2d: kill inset (hole) vs flange inset (cover) — flange MUST be larger
    # so opaque rim hides jagged lathe-boundary seen through glass in top-down.
    A_INSET_KILL = math.radians(1.55)
    Y_INSET_KILL = 0.062
    A_INSET = A_INSET_KILL  # used by _in_inset_pane for kill
    Y_INSET = Y_INSET_KILL

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
        if y < 15.35 or y > 17.85:
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
    short = [e for e in bm.edges if e.is_boundary and e.calc_length() < 0.038]
    if short:
        try:
            bmesh.ops.dissolve_edges(bm, edges=short, use_verts=True)
        except Exception:
            pass

    # Perimeter-only reveal flange: outline path → outer/inner loft
    FLANGE_DEPTH = 0.016  # nose2b: shallower reveal, less cliff
    SEGS_A = 28
    SEGS_Y = 16

    def _outline(pane, a_ins, y_ins):
        """CCW outline in (a,y): fwd → right → aft → left."""
        a0, a1 = pane["a0"], pane["a1"]
        lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
        a_lo, a_hi = lo + a_ins, hi - a_ins
        pts = []
        for i in range(SEGS_A + 1):
            a = _lerp(a_lo, a_hi, i / float(SEGS_A))
            pts.append((a, pane["y_fwd"](a) - y_ins))
        for j in range(1, SEGS_Y + 1):
            tt = j / float(SEGS_Y)
            a = a_hi
            y = _lerp(pane["y_fwd"](a) - y_ins, pane["y_aft"](a) + y_ins, tt)
            pts.append((a, y))
        for i in range(1, SEGS_A + 1):
            a = _lerp(a_hi, a_lo, i / float(SEGS_A))
            pts.append((a, pane["y_aft"](a) + y_ins))
        for j in range(1, SEGS_Y):
            tt = j / float(SEGS_Y)
            a = a_lo
            y = _lerp(pane["y_aft"](a) + y_ins, pane["y_fwd"](a) - y_ins, tt)
            pts.append((a, y))
        return pts

    # nose2d: COVER ring near pane edge (hides jagged kill), inner at kill size
    A_COVER, Y_COVER = math.radians(0.35), 0.014
    for pane in panes:
        cover = _outline(pane, A_COVER, Y_COVER)
        kill_o = _outline(pane, A_INSET_KILL, Y_INSET_KILL)
        n = len(cover)
        if n < 8 or len(kill_o) != n:
            continue
        # Outer opaque lip on skin — covers stairstep hole edge under glass
        outer = [bm.verts.new(_canopy_point(a, y, 0.0008)) for a, y in cover]
        mid = [bm.verts.new(_canopy_point(a, y, -0.002)) for a, y in cover]
        inner = [bm.verts.new(_canopy_point(a, y, -FLANGE_DEPTH)) for a, y in kill_o]
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((outer[i], outer[j], mid[j], mid[i]))
                bm.faces.new((mid[i], mid[j], inner[j], inner[i]))
            except ValueError:
                pass

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    print("C919_NOTE punched_ws_faces", len(kill), "(inside1b perimeter-flange)")


def pitot_probes():
    """Pitot/AOA probes + flush static ports on nose cheeks."""
    bm = bmesh.new()
    # Place on skin via canopy sampler; fuller tip 鈫?cheek stations
    specs = [
        (18.05, 78.0, 0.030, 0.18),  # y, cheek_a_deg, radius, length
        (18.45, 82.0, 0.024, 0.15),
    ]
    for y, a_deg, r, length in specs:
        for side in (1, -1):
            a = math.radians(a_deg) * side
            x, yy, z = _canopy_point(a, y, 0.01)
            tip = bm.verts.new((0, 0, 0))
            ring0, ring1 = [], []
            for i in range(8):
                ang = math.tau * i / 8
                ring0.append(bm.verts.new((0.0, math.cos(ang) * r, math.sin(ang) * r)))
                ring1.append(
                    bm.verts.new((length, math.cos(ang) * r * 0.7, math.sin(ang) * r * 0.7))
                )
            for i in range(8):
                j = (i + 1) % 8
                bm.faces.new((tip, ring0[j], ring0[i]))
                bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
            n_new = 1 + 8 + 8
            verts = list(bm.verts)[-n_new:]
            rot = Matrix.Rotation(math.radians(8), 4, "Z") @ Matrix.Rotation(
                math.radians(-6), 4, "Y"
            )
            if side < 0:
                rot = Matrix.Rotation(math.pi, 4, "Z") @ rot
            bmesh.ops.transform(bm, verts=verts, matrix=rot)
            bmesh.ops.transform(bm, verts=verts, matrix=Matrix.Translation((x, yy, z)))

    # Static ports: small flush discs on cheeks (use canopy sampler)
    for y, a_deg, r_disk in (
        (17.85, 70.0, 0.028),
        (17.55, 75.0, 0.024),
        (17.25, 68.0, 0.022),
    ):
        for sign in (1.0, -1.0):
            a = math.radians(a_deg) * sign
            cx, cy, cz = _canopy_point(a, y, 0.006)
            before = set(bm.verts)
            segs = 10
            center = bm.verts.new((0, 0, 0))
            ring = []
            for i in range(segs):
                ang = math.tau * i / segs
                ring.append(
                    bm.verts.new((0.003, math.cos(ang) * r_disk, math.sin(ang) * r_disk))
                )
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((center, ring[i], ring[j]))
            created = [v for v in bm.verts if v not in before]
            # local +X 鈫?roughly outward (卤X on cheeks)
            rot = Matrix.Rotation(a, 4, "Y")
            bmesh.ops.transform(bm, verts=created, matrix=rot)
            bmesh.ops.transform(
                bm, verts=created, matrix=Matrix.Translation((cx, cy, cz))
            )
    return finish(bm)



def windshield_wipers():
    """Thin flat arms parked vertically along center post (real C919).

    ws1: low-profile disc hubs (not ball spheres), slim elbow near base,
    blade tucked against center mullion. No fat cylinders / end-cap blobs.
    """
    bm = bmesh.new()

    for side in (-1.0, 1.0):
        # Hub just below sill glass, close to center post
        a_hub = side * math.radians(4.2)
        p_hub = Vector(_canopy_point(a_hub, 17.52, 0.018))

        # Low-profile disc hub (flat cylinder), NOT a UV sphere ball
        before = set(bm.verts)
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=12,
            radius1=0.011,
            radius2=0.011,
            depth=0.007,
        )
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.rotate(
            bm,
            verts=created,
            cent=(0, 0, 0),
            matrix=Matrix.Rotation(math.radians(90), 4, "X"),
        )
        bmesh.ops.translate(bm, verts=created, vec=p_hub)

        # Thin arm: hub 鈫?up along center post (toward brow / smaller Y)
        a_tip = side * math.radians(3.0)
        p_elbow = Vector(_canopy_point(a_hub + side * math.radians(1.5), 17.28, 0.020))
        p_tip = Vector(_canopy_point(a_tip, 16.40, 0.020))

        def _flat_bar(p0, p1, width, thick):
            d = p1 - p0
            length = max(d.length, 1e-4)
            mid = (p0 + p1) * 0.5
            before_local = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created_local = [v for v in bm.verts if v not in before_local]
            bmesh.ops.scale(
                bm, verts=created_local, vec=(width, length * 0.5, thick)
            )
            quat = d.normalized().to_track_quat("Y", "Z")
            bmesh.ops.transform(
                bm,
                verts=created_local,
                matrix=Matrix.Translation(mid) @ quat.to_matrix().to_4x4(),
            )

        # Lower arm segment (hub 鈫?elbow)
        _flat_bar(p_hub, p_elbow, 0.007, 0.004)
        # Upper arm (elbow 鈫?tip along pillar)
        _flat_bar(p_elbow, p_tip, 0.006, 0.0035)

        # Slim blade along arm (slightly longer, flatter)
        blade_lo = Vector(
            _canopy_point(a_hub + side * math.radians(0.5), 17.20, 0.021)
        )
        blade_hi = Vector(
            _canopy_point(a_tip + side * math.radians(0.8), 16.48, 0.021)
        )
        _flat_bar(blade_lo, blade_hi, 0.010, 0.003)

        # Tiny washer nozzle (optional, very small 鈥?not a blob)
        nozzle = Vector(
            _canopy_point(a_hub + side * math.radians(10.0), 17.55, 0.014)
        )
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.0045)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=nozzle)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def cockpit_glare_shield():
    """Dark glare shelf + crude instrument panel under windshield.

    cockpit3: tapered brow, side cheeks, center pedestal hint, and a few
    dark display rectangles (not full PFD fidelity).
    """
    bm = bmesh.new()

    # Main glare shelf (wide, thin, pitched)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.62, 0.42, 0.055))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 17.05, 0.88))
    bmesh.ops.rotate(
        bm,
        verts=created,
        cent=(0.0, 17.05, 0.88),
        matrix=Matrix.Rotation(math.radians(-16.0), 4, "X"),
    )
    # Front lip drop (anti-glare brow)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.55, 0.08, 0.09))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 17.28, 0.82))

    # Soft side cheeks
    for sx in (-1.05, 1.05):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.20, 0.38, 0.14))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.94, 0.74))

    # Instrument panel shelf (aft of lip, lower)
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(1.35, 0.22, 0.10))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.84, 0.72))
    bmesh.ops.rotate(
        bm,
        verts=created,
        cent=(0.0, 16.84, 0.72),
        matrix=Matrix.Rotation(math.radians(-8.0), 4, "X"),
    )

    # Display rectangles (dark glass look) 鈥?4 across
    for i, sx in enumerate((-0.78, -0.28, 0.28, 0.78)):
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        w = 0.34 if i in (1, 2) else 0.28
        bmesh.ops.scale(bm, verts=created, vec=(w, 0.04, 0.18))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.94, 0.82))

    # Center pedestal stub between seats
    before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    created = [v for v in bm.verts if v not in before]
    bmesh.ops.scale(bm, verts=created, vec=(0.22, 0.55, 0.12))
    bmesh.ops.translate(bm, verts=created, vec=(0.0, 16.45, 0.28))

    return finish(bm)


def cockpit_pilot_seats():
    """Dual airline-style pilot seats (red) with rails / pedestals.

    cockpit3: cushion + reclined back + headrest silhouette; less boxy;
    simple seat rails so they read as chairs not crates.
    """
    bm = bmesh.new()
    for sx in (-0.50, 0.50):
        # Pedestal / base
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.22, 0.28, 0.10))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.58, 0.08))

        # Seat rails (fore-aft)
        for rx in (-0.12, 0.12):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.035, 0.42, 0.025))
            bmesh.ops.translate(bm, verts=created, vec=(sx + rx, 16.60, 0.01))

        # Cushion (slightly trapezoid via two slabs)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.40, 0.40, 0.10))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.55, 0.24))
        # Front cushion lip (thicker lip = less box)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.38, 0.10, 0.08))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.62, 0.22))

        # Backrest (reclined ~12 deg)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.38, 0.10, 0.58))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.48, 0.72))
        bmesh.ops.rotate(
            bm,
            verts=created,
            cent=(sx, 16.48, 0.40),
            matrix=Matrix.Rotation(math.radians(-12.0), 4, "X"),
        )
        # Lumbar bulge
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.34, 0.06, 0.16))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.52, 0.50))

        # Headrest (narrower, above glare line)
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.26, 0.09, 0.14))
        bmesh.ops.translate(bm, verts=created, vec=(sx, 16.40, 1.28))
        # Side wings of headrest
        for hx in (-0.14, 0.14):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.05, 0.07, 0.12))
            bmesh.ops.translate(bm, verts=created, vec=(sx + hx, 16.40, 1.26))

        # Armrests (slightly sculpted length)
        for ax in (-0.26, 0.26):
            before = set(bm.verts)
            bmesh.ops.create_cube(bm, size=1.0)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.scale(bm, verts=created, vec=(0.06, 0.32, 0.05))
            bmesh.ops.translate(bm, verts=created, vec=(sx + ax, 16.55, 0.45))

    return finish(bm)


def _orient_faces_outward(bm):
    """Flip faces so normals point away from fuselage centerline (mostly 卤X)."""
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        c = f.calc_center_median()
        outward = Vector((c.x, 0.0, c.z))
        if outward.length < 1e-9:
            continue
        outward.normalize()
        if f.normal.dot(outward) < 0.0:
            f.normal_flip()


def _door_specs():
    # y, z, w, h, corner, kind
    # door2: skin-only seals (no planar add_rounded_frame)
    # overwing: sill ABOVE wing upper (~z0.15 after pose) + fairing 鈥?
    # raised to window-belt so exit is clearly visible in 3/4 views.
    return [
        (13.05, 0.05, 0.84, 1.78, 0.12, "passenger"),
        (14.42, 0.12, 0.58, 1.38, 0.10, "service"),
        (1.80, 0.95, 0.56, 0.88, 0.10, "overwing"),
        (-11.45, 0.05, 0.84, 1.78, 0.12, "passenger"),
    ]


def _side_skin_point(y, z, side, r_off=0.0):
    """Project (y, z) onto elliptical fuselage skin on 卤X side."""
    rx, rz = _section_at_y(y)
    zc = max(-rz * 0.96, min(rz * 0.96, z))
    a = math.asin(max(-1.0, min(1.0, zc / max(rz, 1e-6))))
    sx, sz = math.cos(a), math.sin(a)
    x0 = side * rx * sx
    z0 = rz * sz
    nx = side * sx / max(rx, 1e-6)
    nz = sz / max(rz, 1e-6)
    nlen = math.hypot(nx, nz) or 1.0
    nx, nz = nx / nlen, nz / nlen
    return (x0 + nx * r_off, y, z0 + nz * r_off)


def _in_rounded_rect(dy, dz, hw, hh, r):
    ax, az = abs(dy), abs(dz)
    if ax > hw or az > hh:
        return False
    if ax <= hw - r or az <= hh - r:
        return True
    return (ax - (hw - r)) ** 2 + (az - (hh - r)) ** 2 <= r * r + 1e-9


def _rounded_rect_outline(hw, hh, r, segs=8, edge_samples=6):
    """Rounded-rect outline with corner arcs AND sampled straight edges."""
    r = min(r, hw * 0.48, hh * 0.48)
    pts = []
    # bottom edge left鈫抮ight
    for i in range(edge_samples):
        t = i / float(edge_samples)
        pts.append((-hw + r + (2 * (hw - r)) * t, -hh))
    # bottom-right corner
    cy, cz = hw - r, -hh + r
    for i in range(segs):
        t = i / float(segs)
        a = 1.5 * math.pi + 0.5 * math.pi * t
        pts.append((cy + math.cos(a) * r, cz + math.sin(a) * r))
    # right edge bottom鈫抰op
    for i in range(edge_samples):
        t = i / float(edge_samples)
        pts.append((hw, -hh + r + (2 * (hh - r)) * t))
    # top-right corner
    cy, cz = hw - r, hh - r
    for i in range(segs):
        t = i / float(segs)
        a = 0.0 + 0.5 * math.pi * t
        pts.append((cy + math.cos(a) * r, cz + math.sin(a) * r))
    # top edge right鈫抣eft
    for i in range(edge_samples):
        t = i / float(edge_samples)
        pts.append((hw - r - (2 * (hw - r)) * t, hh))
    # top-left corner
    cy, cz = -hw + r, hh - r
    for i in range(segs):
        t = i / float(segs)
        a = 0.5 * math.pi + 0.5 * math.pi * t
        pts.append((cy + math.cos(a) * r, cz + math.sin(a) * r))
    # left edge top鈫抌ottom
    for i in range(edge_samples):
        t = i / float(edge_samples)
        pts.append((-hw, hh - r - (2 * (hh - r)) * t))
    # bottom-left corner
    cy, cz = -hw + r, -hh + r
    for i in range(segs):
        t = i / float(segs)
        a = math.pi + 0.5 * math.pi * t
        pts.append((cy + math.cos(a) * r, cz + math.sin(a) * r))
    return pts


def _add_skin_shell_grid(bm, y0, z0, w, h, corner, side, r_off, ny=12, nz=16):
    hw, hh = w * 0.5, h * 0.5
    r = min(corner, hw * 0.48, hh * 0.48)
    grid = [[None] * (ny + 1) for _ in range(nz + 1)]
    for j in range(nz + 1):
        for i in range(ny + 1):
            dy = -hw + w * i / float(ny)
            dz = -hh + h * j / float(nz)
            if not _in_rounded_rect(dy, dz, hw, hh, r):
                continue
            grid[j][i] = bm.verts.new(_side_skin_point(y0 + dy, z0 + dz, side, r_off))
    for j in range(nz):
        for i in range(ny):
            v00, v10 = grid[j][i], grid[j][i + 1]
            v01, v11 = grid[j + 1][i], grid[j + 1][i + 1]
            if None not in (v00, v10, v01, v11):
                if side > 0:
                    bm.faces.new((v00, v10, v11, v01))
                else:
                    bm.faces.new((v00, v01, v11, v10))
                continue
            tri = [v for v in (v00, v10, v11, v01) if v is not None]
            if len(tri) == 3:
                if side > 0:
                    bm.faces.new(tri)
                else:
                    bm.faces.new(list(reversed(tri)))


def _add_skin_seal_loft(bm, y0, z0, w, h, corner, side, border=0.048, r_off=0.013, segs=10, rings=4):
    """Concentric rounded-rect loft on skin 鈥?continuous seal on all sides."""
    hw, hh = w * 0.5, h * 0.5
    r = min(corner, hw * 0.48, hh * 0.48)
    outlines = []
    for k in range(rings):
        t = k / float(rings - 1) if rings > 1 else 0.0
        shrink = border * t
        hw_k = max(0.05, hw - shrink)
        hh_k = max(0.05, hh - shrink)
        r_k = max(0.012, r - shrink * 0.55)
        outlines.append(_rounded_rect_outline(hw_k, hh_k, r_k, segs=segs, edge_samples=8))
    projected = []
    for outline in outlines:
        projected.append([
            bm.verts.new(_side_skin_point(y0 + dy, z0 + dz, side, r_off))
            for dy, dz in outline
        ])
    n = len(projected[0])
    for a, b in zip(projected, projected[1:]):
        for i in range(n):
            j = (i + 1) % n
            if side > 0:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            else:
                bm.faces.new((a[j], a[i], b[i], b[j]))


def cabin_doors():
    """Plug panels slightly PROUD of skin (must stay outside fuselage shell)."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            # Fill seal throat: outer=w+0.030, border~0.027 → inner≈w+0.003
            pw = (w + 0.030) - 2 * 0.027 - 0.008
            ph = (h + 0.030) - 2 * 0.027 - 0.008
            pc = max(0.045, corner - 0.015)
            _add_skin_shell_grid(
                bm, y, z, pw, ph, pc, side,
                r_off=0.005, ny=14, nz=18,
            )
    _orient_faces_outward(bm)
    return finish(bm)







def cabin_door_frames():
    """Thin dark seal on skin — continuous rounded rectangle.

    door2: never planar add_rounded_frame (floated as thick hollow frames).
    door2e: thin near-skin seal; panel is slightly PROUD so it stays visible
    (negative r_off hides the panel inside the fuselage shell).
    """
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        for side in (1, -1):
            ow, oh = w + 0.030, h + 0.030
            cr = corner + 0.010
            border = 0.028 if kind == "overwing" else 0.026
            _add_skin_seal_loft(
                bm, y, z, ow, oh, cr, side,
                border=border, r_off=0.009, segs=10, rings=4,
            )
    _orient_faces_outward(bm)
    return finish(bm)







def cabin_door_windows():
    """Small porthole glass on main passenger doors only."""
    bm = bmesh.new()
    for y, z, w, h, corner, kind in _door_specs():
        if kind != "passenger":
            continue
        for side in (1, -1):
            z_p = z + h * 0.22
            _add_skin_shell_grid(
                bm, y, z_p, w * 0.28, 0.22, 0.05, side, r_off=0.008, ny=6, nz=6
            )
    _orient_faces_outward(bm)
    return finish(bm)


def panel_join_lines():
    """Subtle plausible panel cues only 鈥?keep radome parting, drop pipe-joint rings.

    fuse1: remove loud longitudinal dark slots and most circumferential cabin rings.
    Retain radome parting + two fine cabin access rings (window belt skipped).
    """
    bm = bmesh.new()
    segs = 72
    rings = [
        (18.48, 0.008, 0.005),  # nose2c: hairline radome parting
    ]
    skip = (math.radians(50), math.radians(100))

    def ang_ok(a):
        aa = abs(((a + math.pi) % math.tau) - math.pi)
        return not (skip[0] <= aa <= skip[1])

    for y, half_w, r_extra in rings:
        rx, rz = _section_at_y(y)
        rx += r_extra
        rz += r_extra
        ring_f, ring_a = [], []
        for i in range(segs):
            a = math.tau * i / segs
            xf, zf = math.cos(a) * rx, math.sin(a) * rz
            ring_f.append(bm.verts.new((xf, y + half_w, zf)))
            ring_a.append(bm.verts.new((xf, y - half_w, zf)))
        full_ring = y > 17.5
        for i in range(segs):
            a = math.tau * i / segs
            canopy_a = a - math.pi / 2
            if (not full_ring) and (not ang_ok(canopy_a)):
                continue
            j = (i + 1) % segs
            a2 = math.tau * j / segs
            if (not full_ring) and (not ang_ok(a2 - math.pi / 2)):
                continue
            bm.faces.new((ring_f[i], ring_f[j], ring_a[j], ring_a[i]))
    return finish(bm)


def fuselage_paint_stripe(side):
    """Livery cheatline as thin surface shell (graphics, not protruding rod)."""
    bm = bmesh.new()
    door_y_gaps = [
        (12.55, 13.55),   # L1
        (14.05, 14.80),   # forward service
        (1.35, 2.25),     # overwing
        (-11.95, -10.95), # aft
    ]
    ys_all = [13.0 + (-11.2 - 13.0) * t / 80.0 for t in range(81)]
    ys = [y for y in ys_all if not any(a <= y <= b for a, b in door_y_gaps)]
    rings = []
    for y in ys:
        rx, rz = _section_at_y(y)
        z_mid = -0.55
        a_mid = math.asin(max(-1.0, min(1.0, z_mid / max(rz, 1e-6))))
        half = 0.028
        row = []
        for t in (0.0, 0.5, 1.0):
            a = a_mid - half + 2 * half * t
            sx, sz = math.cos(a), math.sin(a)
            nx = side * sx / max(rx, 1e-6)
            nz = sz / max(rz, 1e-6)
            nlen = math.hypot(nx, nz) or 1.0
            nx, nz = nx / nlen, nz / nlen
            row.append(
                bm.verts.new(
                    (
                        side * rx * sx + nx * 0.006,
                        y,
                        rz * sz + nz * 0.006,
                    )
                )
            )
        rings.append(row)
    # Bridge neighbors; skip only real door gaps (~0.8m+)
    for idx in range(len(rings) - 1):
        if abs(ys[idx + 1] - ys[idx]) > 0.75:
            continue
        ra, rb = rings[idx], rings[idx + 1]
        for i in range(2):
            try:
                if side > 0:
                    bm.faces.new((ra[i], ra[i + 1], rb[i + 1], rb[i]))
                else:
                    bm.faces.new((ra[i + 1], ra[i], rb[i], rb[i + 1]))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def wing_body_fairing(side):
    """Smooth belly / wing-root fairing loft (C919-style bulge)."""
    bm = bmesh.new()
    # Tighter to fuselage, longer fore-aft blend, softer silhouette
    secs = [
        (2.50, side * 1.15, -1.72, 0.42, 0.38),
        (1.70, side * 1.45, -1.58, 0.65, 0.52),
        (0.95, side * 1.80, -1.42, 0.88, 0.64),
        (0.20, side * 2.05, -1.30, 1.00, 0.70),
        (-0.55, side * 2.12, -1.26, 0.95, 0.60),
        (-1.30, side * 1.90, -1.28, 0.72, 0.46),
        (-2.00, side * 1.55, -1.38, 0.48, 0.32),
        (-2.60, side * 1.20, -1.48, 0.28, 0.20),
    ]
    n_rad = 20
    rings = []
    for y, cx, cz, rx, rz in secs:
        ring = []
        for i in range(n_rad):
            a = math.tau * i / n_rad
            ring.append(
                bm.verts.new(
                    (cx + math.cos(a) * rx, y, cz + math.sin(a) * rz)
                )
            )
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(n_rad):
            j = (i + 1) % n_rad
            try:
                if side > 0:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
                else:
                    bm.faces.new((a[j], a[i], b[i], b[j]))
            except ValueError:
                pass
    try:
        if side > 0:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        else:
            bm.faces.new(rings[0])
            bm.faces.new(list(reversed(rings[-1])))
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)


def gear_bay_doors():
    """Thin rectangular belly doors near nose + main gear (preview-readable)."""
    bm = bmesh.new()
    nose = [
        (0.28, 13.55, -2.02, 0.42, 1.05, 0.03),
        (-0.28, 13.55, -2.02, 0.42, 1.05, 0.03),
    ]
    main = [
        (1.55, -0.15, -2.00, 0.55, 1.25, 0.03),
        (-1.55, -0.15, -2.00, 0.55, 1.25, 0.03),
        (2.15, -0.15, -1.85, 0.45, 1.10, 0.03),
        (-2.15, -0.15, -1.85, 0.45, 1.10, 0.03),
    ]
    for x, y, z, w, length, thick in nose + main:
        bmesh.ops.create_cube(bm, size=1)
        created = bm.verts[-8:]
        bmesh.ops.scale(bm, verts=created, vec=(w, length, thick))
        bmesh.ops.translate(bm, verts=created, vec=(x, y, z))
    return finish(bm)


def antennas_and_apu():
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


def build():
    skin = material("Skin", (0.96, 0.97, 0.98), 0.34, 0.04)
    navy = material("Navy", (0.02, 0.15, 0.42), 0.4, 0.02)
    stripe = material("Stripe", (0.78, 0.08, 0.12), 0.36, 0.02)
    engine_mat = material("Engine", (0.88, 0.90, 0.92), 0.28, 0.22)
    lip = material("EngineLip", (0.08, 0.1, 0.12), 0.28, 0.45)
    glass = glass_material("Glass")
    rubber = material("Rubber", (0.07, 0.07, 0.08), 0.82, 0.0)
    spinner = material("Spinner", (0.75, 0.78, 0.82), 0.25, 0.35)
    flag = flag_material()
    title = image_material("Title", text_image("C919", (0.02, 0.16, 0.45, 1)))
    tail_mark = image_material(
        "TailMark",
        text_image("MU", (1, 1, 1, 1), (0.02, 0.13, 0.38, 1), 10),
        clip_alpha=False,
    )

    # Soft blunt ogive radome (closed tip) fused into fuselage 鈥?real C919 front photo
    link(
        "Nose",
        nose_with_cap(list(NOSE_PROFILE), segments=120),
        "nose",
        skin,
        "skin",
    )
    # ws4: NO face-delete punch — continuous skin; openings via knife_project in
    # scripts/ws4_knife_project_windshield.py (GUI). Do not call punch_windshield_openings.
    # punch_windshield_openings(bpy.data.objects.get("Nose"))  # DISABLED ws4

    link(
        "Fuselage",
        fuselage_body(list(FUSELAGE_PROFILE), segments=128),
        "fuselage",
        skin,
        "skin",
    )
    # No navy cheatline through the window row 鈥?panes sit on white skin only.
    # Red stripe kept well below the window belt (z鈮?0.35).
    link("Stripe_R", fuselage_paint_stripe(1), "fuselage", stripe, "stripe")
    link("Stripe_L", fuselage_paint_stripe(-1), "fuselage", stripe, "stripe")

    frame_mat = material("WindowFrame", (0.12, 0.13, 0.14), 0.48, 0.05)
    door_frame_mat = material("DoorFrame", (0.08, 0.08, 0.09), 0.60, 0.03)
    # Metallic fan: high metal / low roughness (not plastic gray)
    fan_mat = material("FanBlade", (0.78, 0.80, 0.84), 0.14, 0.92)

    win_obj = link("Windows", cabin_windows(), "fuselage", glass, "glass")
    wf_obj = link("WindowFrames", cabin_window_frames(), "fuselage", frame_mat, "glass")

    cockpit_glass = cockpit_glass_material("CockpitGlass")
    seal_mat = material("CockpitSeal", (0.02, 0.02, 0.025), 0.55, 0.0)
    pane_objs = []
    for pname in ("WS_L", "WS_R", "SW_L", "SW_R"):
        ob = link(pname, cockpit_pane_mesh(pname), "avionics", cockpit_glass, "glass")
        pane_objs.append(ob)
    # ws3: no aggregate Windshield mesh (four named panes only)
    cf_obj = link("CockpitFrames", cockpit_frames(), "avionics", seal_mat, "navy")
    cabin_mat = material("CockpitCabin", (0.04, 0.045, 0.05), 0.75, 0.0)
    cabin_obj = link("CockpitCabin", cockpit_cabin_shell(), "avionics", cabin_mat, "navy")
    for ob in (win_obj, wf_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = False
    for ob in pane_objs + [cf_obj, cabin_obj]:
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True

    link("Wing_R", wing(1), "wing", skin, "skin")
    link("Wing_L", wing(-1), "wing", skin, "skin")
    # Winglets must be WHITE like the physical model (not navy)
    link("Winglet_R", winglet(1), "wing", skin, "skin")
    link("Winglet_L", winglet(-1), "wing", skin, "skin")
    link("WingFairing_R", wing_flap_fairings(1), "wing", skin, "skin")
    link("WingFairing_L", wing_flap_fairings(-1), "wing", skin, "skin")
    link("WingLE_R", wing_le_strip(1), "wing", skin, "skin")
    link("WingLE_L", wing_le_strip(-1), "wing", skin, "skin")

    door_skin = material("DoorSkin", (0.58, 0.60, 0.62), 0.52, 0.05)
    door_obj = link("Doors", cabin_doors(), "fuselage", door_skin, "skin")
    df_obj = link("DoorFrames", cabin_door_frames(), "fuselage", door_frame_mat, "panel")
    dw_obj = link("DoorWindows", cabin_door_windows(), "fuselage", glass, "glass")
    for ob in (door_obj, df_obj, dw_obj):
        for poly in ob.data.polygons:
            poly.use_smooth = True

    for side, suffix in ((1, "R"), (-1, "L")):
        link(f"Engine_{suffix}", engine(side), "engine", engine_mat, "engine")
        link(f"EngineLip_{suffix}", engine_lip_ring(side), "engine", lip, "engineLip")
        link(f"Fan_{suffix}", engine_fan(side), "engine", fan_mat, "engine")
        link(f"Pylon_{suffix}", engine_pylon(side), "engine", skin, "skin")

    link("Stab_R", stab(1), "tail", skin, "skin")
    link("Stab_L", stab(-1), "tail", skin, "skin")
    link("VerticalTail", vertical_tail(), "tail", navy, "navy")
    link("Rudder", rudder(), "tail", stripe, "stripe")
    # Dark metallic aft cone + APU exhaust lip (real C919 photo cue)
    cone_mat = material("TailConeMetal", (0.22, 0.23, 0.25), 0.32, 0.55)
    link("TailCone", tail_cone_cap(), "tail", cone_mat, "engine")

    for side in (1, -1):
        mark = link(
            "TailMark" if side > 0 else "TailMark_L",
            quad(1.5, 1.15),
            "tail",
            tail_mark,
            "decal",
        )
        mark.location = (side * 0.14, -16.85, 5.6)
        mark.rotation_euler = (
            math.radians(90),
            math.radians(90 if side > 0 else -90),
            0,
        )
        title_obj = link(
            "Title" if side > 0 else "Title_L",
            quad(3.2, 0.7),
            "fuselage",
            title,
            "decal",
        )
        title_obj.location = (side * 2.095, 5.0, 0.95)
        title_obj.rotation_euler = (
            math.radians(90),
            math.radians(90 if side > 0 else -90),
            0,
        )

    pitot_mat = material("Pitot", (0.12, 0.13, 0.15), 0.35, 0.55)
    link("PitotProbes", pitot_probes(), "avionics", pitot_mat, "navy")

    # ws3: glass already assigned; show dark glare + dark seat silhouettes through openings
    wiper_mat = material("Wiper", (0.05, 0.05, 0.06), 0.45, 0.15)
    wp_obj = link("WindshieldWipers", windshield_wipers(), "avionics", wiper_mat, "navy")
    for poly in wp_obj.data.polygons:
        poly.use_smooth = True

    glare_mat = material("GlareShield", (0.05, 0.055, 0.06), 0.60, 0.05)
    seat_mat = material("PilotSeat", (0.08, 0.08, 0.09), 0.70, 0.02)  # dark, not red
    gs_obj = link("GlareShield", cockpit_glare_shield(), "avionics", glare_mat, "navy")
    seat_obj = link("PilotSeats", cockpit_pilot_seats(), "avionics", seat_mat, "navy")
    for ob in (gs_obj, seat_obj):
        if ob is None:
            continue
        for poly in ob.data.polygons:
            poly.use_smooth = True

    # --- Fine detail pass (panel lines / fairings / gear doors / antennas) ---
    panel_mat = material("PanelLine", (0.55, 0.56, 0.58), 0.62, 0.04)
    fairing_mat = material("WingBodyFairing", (0.90, 0.91, 0.93), 0.40, 0.05)
    gear_door_mat = material("GearDoor", (0.78, 0.80, 0.82), 0.48, 0.06)
    antenna_mat = material("Antenna", (0.10, 0.11, 0.12), 0.40, 0.35)

    pl_obj = link("PanelLines", panel_join_lines(), "fuselage", panel_mat, "navy")
    for poly in pl_obj.data.polygons:
        poly.use_smooth = True

    link("WingBodyFairing_R", wing_body_fairing(1), "wing", fairing_mat, "skin")
    link("WingBodyFairing_L", wing_body_fairing(-1), "wing", fairing_mat, "skin")

    gd_obj = link("GearBayDoors", gear_bay_doors(), "landingGear", gear_door_mat, "skin")
    for poly in gd_obj.data.polygons:
        poly.use_smooth = False

    ant_obj = link("AntennasAPU", antennas_and_apu(), "avionics", antenna_mat, "navy")
    for poly in ant_obj.data.polygons:
        poly.use_smooth = True

    nose_gear = link("Gear_Nose", gear(2.05, [0]), "landingGear", rubber, "rubber")
    nose_gear.location = (0, 13.5, -1.75)
    main_r = link("Gear_R", gear(2.45, [-0.2, 0.2]), "landingGear", rubber, "rubber")
    main_r.location = (2.5, -0.2, -1.6)
    main_l = link("Gear_L", gear(2.45, [-0.2, 0.2]), "landingGear", rubber, "rubber")
    main_l.location = (-2.5, -0.2, -1.6)

    # Flags with proper UVs so five stars are visible
    for side, name in ((1, "Flag_R"), (-1, "Flag_L")):
        flag_obj = link(name, flag_plane(1.5, 1.0, 0.035), "flag", flag, "flag")
        flag_obj.location = (side * 2.105, -8.2, 0.65)
        # Left side: flip X so outward face still shows hoist-forward texture
        if side < 0:
            flag_obj.scale.x = -1

    empty = bpy.data.objects.new("C919", None)
    bpy.context.scene.collection.objects.link(empty)
    for obj in list(bpy.context.scene.objects):
        if obj is not empty:
            obj.parent = empty


def export_flag_preview():
    """Write PRC flag texture to disk for audit (浜旀槦绾㈡棗 proportions)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    img = bpy.data.images.get("PRC_Flag")
    if img is None:
        print("FLAG_PREVIEW_SKIP no image")
        return
    out = os.path.join(OUT_DIR, "c919-flag-audit.png")
    # Ensure pixels are flushed then save
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    print("FLAG_AUDIT", out)


def export_glb():
    os.makedirs(OUT_DIR, exist_ok=True)
    addon = "io_scene_gltf2"
    if addon not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon)
    # ws3: keep dark glare/seats for see-through cabin
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


def save_blend():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)


def apply_subdivision(level=1):
    skip_prefix = (
        "Fuselage",
        "Stripe",
        "Windows",
        "Flag",
        "Title",
        "TailMark",
        "Rudder",
        "Gear",
        "EngineLip",
        "Brow",
        "Windshield",
        "CockpitFrames",
        "WS_L",
        "WS_R",
        "SW_L",
        "SW_R",
        "CockpitCabin",
        "WindowFrames",
        "Fan",
        "Pylon",
        "Door",
        "DoorWindows",
        "Nose",
        "PanelLines",
        "GearBayDoors",
        "AntennasAPU",
        "WingBodyFairing",
        "WindshieldWipers",
        "GlareShield",
        "PilotSeats",
        # Thin extruded surfaces: subdiv opens gaps / shards the fin
        "Wing",
        "Winglet",
        "Stab",
        "VerticalTail",
        "TailCone",
        "Engine",
    )
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        if any(obj.name.startswith(p) for p in skip_prefix):
            continue
        mod = obj.modifiers.new(name="Smooth", type="SUBSURF")
        mod.levels = level
        mod.render_levels = level
        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as exc:  # pragma: no cover
            print("SUBDIV_SKIP", obj.name, exc)


def try_enable_bool_tool():
    """Optional: enable free Bool Tool if present. Never required for this build."""
    import addon_utils
    loaded = {mod.__name__ for mod in addon_utils.modules()}
    candidates = (
        "object_boolean_tools",
        "bool_tool",
        "bl_ext.blender_org.bool_tool",
    )
    for mod in candidates:
        if mod not in loaded:
            continue
        try:
            bpy.ops.preferences.addon_enable(module=mod)
            print("BOOL_TOOL_ENABLED", mod)
            return mod
        except Exception as exc:
            print("BOOL_TOOL_FAIL", mod, exc)
    print("BOOL_TOOL_SKIP not installed (using pure bmesh rounded slabs)")
    return None


def main():
    reset_scene()
    try_enable_bool_tool()
    build()
    apply_subdivision(level=1)
    export_flag_preview()
    export_glb()
    save_blend()
    print("C919_GLB", GLB_PATH)
    print("C919_BLEND", BLEND_PATH)
    print("C919_NOTE tail1b=rounded-fin-tip+flush-apu+mark-nudge")


if __name__ == "__main__":
    main()

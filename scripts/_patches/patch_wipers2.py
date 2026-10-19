# -*- coding: utf-8 -*-
from pathlib import Path

path = Path(r"C:\Users\希儿\Projects\c919-autonomy\scripts\build_c919.py")
text = path.read_text(encoding="utf-8")

NEW_WIPERS = '''def windshield_wipers():
    """Two parked dark wiper arms: solid hub + arm + blade (L/R).

    cockpit3: thick hub/arm/blade parked at windshield BASE near center
    pillar; rubber lip + mount pad + washer nozzles. Reads clearly outside.
    """
    bm = bmesh.new()

    for side in (-1.0, 1.0):
        # Hub at sill, close to center mullion
        a_hub = side * math.radians(5.5)
        p_hub = Vector(_canopy_point(a_hub, 17.46, 0.040))

        # Mount pad under hub
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.070, 0.050, 0.018))
        bmesh.ops.translate(bm, verts=created, vec=p_hub + Vector((0.0, 0.01, -0.012)))

        # Solid hub
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.055)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=p_hub)

        # Short arm: from hub slightly up-aft and outboard (parked low)
        a_arm = a_hub + side * math.radians(4.0)
        p_arm_end = Vector(_canopy_point(a_arm, 17.18, 0.042))
        arm_dir = p_arm_end - p_hub
        arm_len = max(arm_dir.length, 1e-4)
        arm_mid = (p_hub + p_arm_end) * 0.5
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(0.048, arm_len * 0.5, 0.034))
        quat = arm_dir.normalized().to_track_quat("Y", "Z")
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(arm_mid) @ quat.to_matrix().to_4x4(),
        )

        # Blade parked low across lower forward pane (near sill)
        a_lo = a_hub + side * math.radians(-2.0)
        a_hi = a_hub + side * math.radians(20.0)
        p_lo = Vector(_canopy_point(a_lo, 17.28, 0.044))
        p_hi = Vector(_canopy_point(a_hi, 17.10, 0.044))
        blade_mid = (p_lo + p_hi) * 0.5
        blade_dir = p_hi - p_lo
        blade_len = max(blade_dir.length, 1e-4)
        quat_b = blade_dir.normalized().to_track_quat("X", "Z")

        # Metal channel
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(blade_len * 0.5, 0.022, 0.016))
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(blade_mid) @ quat_b.to_matrix().to_4x4(),
        )
        # Rubber lip
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.scale(bm, verts=created, vec=(blade_len * 0.48, 0.010, 0.008))
        bmesh.ops.transform(
            bm,
            verts=created,
            matrix=Matrix.Translation(blade_mid + Vector((0, 0, -0.008)))
            @ quat_b.to_matrix().to_4x4(),
        )

        # Blade end caps (read as solid bar, not a wire)
        for end in (p_lo, p_hi):
            before = set(bm.verts)
            bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.014)
            created = [v for v in bm.verts if v not in before]
            bmesh.ops.translate(bm, verts=created, vec=end)

        # Washer nozzle outboard of hub on sill
        nozzle = Vector(_canopy_point(a_hub + side * math.radians(12.0), 17.50, 0.032))
        before = set(bm.verts)
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.014)
        created = [v for v in bm.verts if v not in before]
        bmesh.ops.translate(bm, verts=created, vec=nozzle)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return finish(bm)
'''

start = text.find("def windshield_wipers(")
nxt = text.find("\ndef ", start + 4)
if start < 0 or nxt < 0:
    raise SystemExit("wipers markers missing")
text = text[:start] + NEW_WIPERS.rstrip() + "\n\n\n" + text[nxt + 1 :]
path.write_text(text, encoding="utf-8")
print("wipers rewritten OK")

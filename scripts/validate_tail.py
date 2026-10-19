import bpy
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\希儿\Projects\c919-autonomy\public\models\c919.blend")

stations = [
    (14.85, 2.04), (10.0, 2.08), (0.0, 2.08), (-10.0, 2.08),
    (-14.2, 2.0), (-16.2, 1.72), (-17.4, 1.35), (-18.3, 0.95),
    (-19.0, 0.55), (-19.55, 0.18),
]

def radius_at(y):
    if y >= stations[0][0]: return stations[0][1]
    if y <= stations[-1][0]: return stations[-1][1]
    for (y0, r0), (y1, r1) in zip(stations, stations[1:]):
        if y1 <= y <= y0:
            t = (y - y0) / (y1 - y0 + 1e-9)
            return r0 + t * (r1 - r0)
    return 2.08

vt = bpy.data.objects["VerticalTail"]
mw = vt.matrix_world
# Collect lowest z verts per rounded y
by_y = {}
for v in vt.data.vertices:
    w = mw @ v.co
    key = round(w.y, 2)
    by_y.setdefault(key, []).append(w.z)

ok = True
for y in sorted(by_y):
    zmin = min(by_y[y])
    # only check near-root verts (bottom 30% of local height band)
    if zmin > 3.0:
        continue
    r = radius_at(y)
    planted = zmin < r - 0.05
    print(f"y={y:7.2f} zmin={zmin:5.2f} crown={r:5.2f} planted={planted}")
    if not planted:
        ok = False

# Overall proportions
bbox = [mw @ Vector(c) for c in vt.bound_box]
zs = [v.z for v in bbox]; ys = [v.y for v in bbox]
print(f"FIN height tip={max(zs):.2f} root_span_y=[{min(ys):.2f},{max(ys):.2f}]")
print(f"LENGTH nose_to_tail ~ {(19.85 - (-19.55)):.2f}")
print("PASS" if ok else "FAIL")

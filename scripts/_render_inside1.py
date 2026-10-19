"""INSIDE1 audit renders: overview + windshield front/side + interior peek."""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "models")
GLB = os.path.join(OUT, "c919.glb")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb():
    bpy.ops.import_scene.gltf(filepath=GLB)


def setup_world():
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.68, 0.75, 1)
    bg.inputs[1].default_value = 1.2


def cam_at(name, loc, target, lens=50):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_shot(path, res=(1280, 720)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)


def main():
    reset()
    import_glb()
    setup_world()
    # light
    light_data = bpy.data.lights.new("Key", "AREA")
    light_data.energy = 800
    light_data.size = 8
    light = bpy.data.objects.new("Key", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (6, 12, 8)

    shots = [
        ("c919-preview-inside1.png", (7.5, 22.0, 3.2), (0, 16.5, 0.9), 45),
        ("c919-detail-windshield-front.png", (0.2, 24.5, 1.6), (0, 16.8, 1.15), 55),
        ("c919-detail-windshield-side.png", (5.2, 20.5, 1.5), (0, 16.9, 1.1), 50),
        ("c919-detail-cockpit-interior.png", (0.15, 21.8, 1.35), (0, 16.55, 0.85), 60),
    ]
    for fname, loc, tgt, lens in shots:
        cam_at("Cam", loc, tgt, lens)
        render_shot(os.path.join(OUT, fname))
    print("INSIDE1_RENDER_DONE")


if __name__ == "__main__":
    main()

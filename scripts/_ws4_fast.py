import bpy, sys, os
# Load and exec main pieces with skip render
sys.path.insert(0, os.path.dirname(__file__))
# Monkeypatch after import by rewriting timer callback
path = os.path.join(os.path.dirname(__file__), "ws4_knife_project_windshield.py")
# Just run by importing functions — exec the file but replace render call
src = open(path, encoding="utf-8").read()
src = src.replace("bpy.app.timers.register(run, first_interval=0.9)", "# timer disabled")
src = src.replace(
    """    try:
        render_previews()
    except Exception as e:
        log("render_fail", e)
""",
    """    log("skip_render_fast")
""",
)
ns = {}
exec(compile(src, path, "exec"), ns)
# register our run
bpy.app.timers.register(ns["run"], first_interval=1.0)

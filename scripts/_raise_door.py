from pathlib import Path
p = Path("scripts/build_c919.py")
t = p.read_text(encoding="utf-8")
old = '(1.65, 0.78, 0.58, 0.95, 0.10, "overwing"),'
new = '(1.80, 0.95, 0.56, 0.88, 0.10, "overwing"),'
if old not in t:
    # maybe already patched or different
    import re
    m = re.search(r'\([^)]+"overwing"\),', t)
    print("CURRENT", m.group(0) if m else "NONE")
    raise SystemExit("target not found")
t = t.replace(old, new, 1)
t = t.replace(
    "(1.10, 2.20),     # overwing exit (raised / slightly forward)",
    "(1.25, 2.35),     # overwing exit (raised / slightly forward)",
    1,
)
t = t.replace(
    "(1.20, 2.10),     # overwing",
    "(1.35, 2.25),     # overwing",
    1,
)
p.write_text(t, encoding="utf-8")
print("OK", new)

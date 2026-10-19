"""Splice wing1 helpers into build_c919.py (from.bak-wing1 base)."""
from pathlib import Path
import shutil

ROOT = Path(r"C:\Users\希儿\Projects\c919-autonomy")
BUILD = ROOT / "scripts" / "build_c919.py"
BAK = ROOT / "scripts" / "build_c919.py.bak-wing1"
HERE = Path(__file__).resolve().parent
FUNCS = HERE / "_wing1_funcs.py"
FAIR = HERE / "_wing1_fairing.py"


def replace_between(text: str, start_marker: str, end_marker: str, new_body: str) -> str:
    i0 = text.find(start_marker)
    if i0 < 0:
        raise SystemExit(f"START not found: {start_marker!r}")
    i1 = text.find(end_marker, i0 + 1)
    if i1 < 0:
        raise SystemExit(f"END not found after start: {end_marker!r}")
    return text[:i0] + new_body.rstrip() + "\n\n\n" + text[i1:]


def main():
    # Always start from pre-wing backup so re-patch is idempotent
    if not BAK.exists():
        raise SystemExit(f"missing backup {BAK}")
    text = BAK.read_text(encoding="utf-8")
    funcs = FUNCS.read_text(encoding="utf-8")
    lines = funcs.splitlines()
    while lines and (lines[0].startswith("#") or not lines[0].strip()):
        lines.pop(0)
    funcs_body = "\n".join(lines).rstrip() + "\n"
    fair = FAIR.read_text(encoding="utf-8").rstrip() + "\n"

    text2 = replace_between(text, "def pose_wing(bm, side):", "def stab(side):", funcs_body)
    text3 = replace_between(
        text2,
        "def wing_body_fairing(side):",
        "def gear_bay_doors():",
        fair,
    )
    old_note = 'print("C919_NOTE nose4=blunt-radome+parting+soft-ws+door-window")'
    new_note = 'print("C919_NOTE wing1=airfoil-loft+blended-winglet+canoe-fairings+root-blend")'
    if old_note in text3:
        text3 = text3.replace(old_note, new_note)
    elif "wing1=" not in text3:
        raise SystemExit("NOTE line not found")

    BUILD.write_text(text3, encoding="utf-8")
    print("PATCHED", BUILD, "BYTES", BUILD.stat().st_size)


if __name__ == "__main__":
    main()

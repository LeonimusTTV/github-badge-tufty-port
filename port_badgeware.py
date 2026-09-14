#!/usr/bin/env python3
"""
port_badgeware.py

Ports a MicroPython app written for the old "badgeware" API of the
GitHub Universe 2025 badge (brushes / shapes / Image / PixelFont /
io.*) to the current Tufty 2350 firmware API (color / shape / image /
font / badge.*).

Usage:
    python3 port_badgeware.py path/to/__init__.py [other_file.py ...]
    python3 port_badgeware.py path/to/app_folder/     # recurses through all .py files

Each file is rewritten in place. A .bak copy is kept alongside it
before modification. The script also completely strips any
`from badgeware import ...` / `import badgeware` line — once an app
is launched via run(), everything is already ambient (screen, badge,
font, run, etc.), so there's no need to import anything from
badgeware anymore. Anything the script can't safely convert (a bare
io.held, SpriteSheet, a scale_blit call with arguments too complex
for the regex, etc.) is left untouched and listed at the end of the
run under "needs manual review" — check those lines by hand.
"""

import re
import sys
from pathlib import Path

SIMPLE_REPLACEMENTS = [
    (r"\bscreen\.brush\b", "screen.pen"),
    (r"\bshapes\.", "shape."),
    (r"\bMatrix\(", "mat3("),
    (r"\bImage\.load\b", "image.load"),
    (r"\bPixelFont\.load\b", "font.load"),
    (r"\bscreen\.draw\(", "screen.shape("),
    (r"\bio\.ticks\b", "badge.ticks"),
    (r"\bbrushes\.color\(", "color.rgb("),
]

BUTTON_STATES = ["pressed", "held", "released", "changed"]
BUTTON_PATTERNS = [
    (re.compile(rf"io\.(BUTTON_\w+)\s+in\s+io\.{state}\b"), rf"badge.{state}(\1)")
    for state in BUTTON_STATES
]

IMPORT_LINE = re.compile(r"^(from badgeware import .+|import badgeware)\n?", re.MULTILINE)


def filter_badgeware_import(text):
    def repl(m):
        print(f"    (import removed: {m.group(1).strip()})")
        return ""
    return IMPORT_LINE.sub(repl, text)


# --- scale_blit(img, x, y, w, h) -> blit(img, rect(x, y, w, h)) ---------
SCALE_BLIT = re.compile(
    r"screen\.scale_blit\(\s*"
    r"([^,]+?),\s*([^,]+?),\s*([^,]+?),\s*([^,]+?),\s*([^,()]+?),?\s*\)",
    re.DOTALL,
)


def convert_scale_blit(text):
    def repl(m):
        img, x, y, w, h = (g.strip() for g in m.groups())
        return f"screen.blit({img}, rect({x}, {y}, {w}, {h}))"
    return SCALE_BLIT.sub(repl, text)


# --- strips the `if __name__ == "__main__":` guard ----------------------
MAIN_GUARD = re.compile(
    r'^if __name__ == ["\']__main__["\']:\n((?:[ \t]+.*\n?)+)',
    re.MULTILINE,
)


def strip_main_guard(text):
    def repl(m):
        block = m.group(1)
        dedented = []
        for line in block.splitlines():
            if line.startswith("    "):
                dedented.append(line[4:])
            elif line.startswith("\t"):
                dedented.append(line[1:])
            else:
                dedented.append(line)
        return "\n".join(dedented) + "\n"
    return MAIN_GUARD.sub(repl, text)


REMAINING_MARKERS = [
    "io.BUTTON", "io.pressed", "io.held", "io.released", "io.changed",
    "io.poll", "io.ticks", "brushes.", "shapes.", "Matrix(",
    "Image.load", "PixelFont.load", "screen.draw(", "screen.brush",
    "screen.scale_blit(", '__name__ == "__main__"', "__name__ == '__main__'",
    "SpriteSheet(", "AnimatedSprite(",
]


def port_file(path: Path):
    original = path.read_text()
    text = original

    for pattern, replacement in SIMPLE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    for pattern, replacement in BUTTON_PATTERNS:
        text = pattern.sub(replacement, text)

    text = convert_scale_blit(text)
    text = strip_main_guard(text)
    text = filter_badgeware_import(text)

    if text == original:
        print(f"  (nothing to change)  {path}")
        return

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_text(original)
    path.write_text(text)
    print(f"  ported             {path}  (backup: {backup.name})")

    leftovers = [m for m in REMAINING_MARKERS if m in text]
    if leftovers:
        print(f"    !! needs manual review in {path.name}: {', '.join(leftovers)}")


def collect_files(args):
    files = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  !! not found: {arg}")
    return files


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    files = collect_files(sys.argv[1:])
    if not files:
        print("No .py files found.")
        sys.exit(1)

    print(f"Porting {len(files)} file(s)...\n")
    for f in files:
        port_file(f)


if __name__ == "__main__":
    main()
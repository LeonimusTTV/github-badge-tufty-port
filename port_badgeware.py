#!/usr/bin/env python3
"""
port_badgeware.py

Porte une app MicroPython écrite pour l'ancienne API "badgeware" du
badge GitHub Universe 2025 (brushes / shapes / Image / PixelFont /
io.*) vers l'API actuelle du firmware Tufty 2350 (color / shape /
image / pixel_font / badge.*).

Usage :
    python3 port_badgeware.py chemin/vers/__init__.py [autre_fichier.py ...]
    python3 port_badgeware.py chemin/vers/dossier_app/     # traite tous les .py récursivement

Chaque fichier est réécrit sur place. Une copie .bak est gardée à
côté avant modification. Tout ce que le script ne peut pas convertir
sans risque (io.held tout seul, scale_blit avec des arguments trop
complexes, etc.) est laissé tel quel et listé en fin d'exécution
sous "needs manual review" — check ces lignes à la main.
"""

import re
import sys
from pathlib import Path

# --- remplacements simples, 1 pour 1 ------------------------------------
SIMPLE_REPLACEMENTS = [
    (r"\bscreen\.brush\b", "screen.pen"),
    (r"\bshapes\.", "shape."),
    (r"\bMatrix\(", "mat3("),
    (r"\bImage\.load\b", "image.load"),
    (r"\bPixelFont\.load\b", "pixel_font.load"),
    (r"\bscreen\.draw\(", "screen.shape("),
    (r"\bio\.ticks\b", "badge.ticks"),
    (r"\bbrushes\.color\(", "color.rgb("),
]

# --- boutons : `io.BUTTON_X in io.pressed` -> `badge.pressed(BUTTON_X)` --
BUTTON_STATES = ["pressed", "held", "released", "changed"]
BUTTON_PATTERNS = [
    (re.compile(rf"io\.(BUTTON_\w+)\s+in\s+io\.{state}\b"), rf"badge.{state}(\1)")
    for state in BUTTON_STATES
]

# --- nettoie `from badgeware import ...` : ne garde que les noms qui  --
# --- existent encore vraiment comme attributs du module aujourd'hui   --
KNOWN_GOOD_BADGEWARE_EXPORTS = {
    "run", "clamp", "is_dir", "file_exists",
    "get_battery_level", "is_charging", "fatal_error",
}
IMPORT_LINE = re.compile(r"^from badgeware import (.+)$", re.MULTILINE)


def filter_badgeware_import(text):
    def repl(m):
        names = [n.strip() for n in m.group(1).split(",")]
        kept = [n for n in names if n in KNOWN_GOOD_BADGEWARE_EXPORTS]
        dropped = [n for n in names if n not in KNOWN_GOOD_BADGEWARE_EXPORTS]
        if dropped:
            print(f"    (import nettoye, retire : {', '.join(dropped)})")
        if not kept:
            return ""  # plus rien a importer, on vire la ligne entiere
        return f"from badgeware import {', '.join(kept)}"
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


# --- vire le garde `if __name__ == "__main__":` -------------------------
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
        print(f"  (rien a changer)  {path}")
        return

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_text(original)
    path.write_text(text)
    print(f"  porte             {path}  (backup: {backup.name})")

    leftovers = [m for m in REMAINING_MARKERS if m in text]
    if leftovers:
        print(f"    !! a verifier a la main dans {path.name}: {', '.join(leftovers)}")


def collect_files(args):
    files = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  !! introuvable : {arg}")
    return files


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    files = collect_files(sys.argv[1:])
    if not files:
        print("Aucun fichier .py trouve.")
        sys.exit(1)

    print(f"Portage de {len(files)} fichier(s)...\n")
    for f in files:
        port_file(f)


if __name__ == "__main__":
    main()
# Porting GitHub Universe 2025 apps → Pimoroni Tufty 2350

The GitHub Universe 2025 badge apps (`badger/home` repo) are written
against an older version of Pimoroni's "badgeware" API. Since then, the
Tufty 2350 firmware has gone through a major API overhaul (v2.0.0+), and
quite a few names have changed. This repo contains the files ported to
the current API, plus the script that automates the conversion.

## Table of contents

- [Installing the firmware](#installing-the-firmware)
- [Installing an app](#installing-an-app)
- [API mapping table](#api-mapping-table)
- [The porting script](#the-porting-script)
- [Debugging a crash](#debugging-a-crash)

## Installing the firmware

1. Download the `.uf2` from [github.com/pimoroni/tufty2350/releases](https://github.com/pimoroni/tufty2350/releases)
   — grab the one marked **`-with-filesystem`** if you want to start
   fresh with the default apps.
2. Hold **BOOT**, tap **RESET**, release **BOOT** — an `RP2350` drive
   shows up.
3. Drag the `.uf2` onto it. The badge reboots into it on its own.

Stick to a known-working version (note the exact tag somewhere) rather
than reflashing "latest" out of habit: the API has moved more than once,
and the apps and firmware need to be from the same generation to match.

## Installing an app

1. Double-tap **RESET** to enter disk mode (Mass Storage).
2. Copy the app's folder into `/system/apps/` on the volume that shows
   up.
3. Eject the volume properly, then reset the badge normally.

On Mac, run `export COPYFILE_DISABLE=1` before copying — otherwise
Finder scatters invisible `._xxx` files across the badge's FAT32/exFAT
volume.

To test without going through disk mode every time:
```bash
mpremote connect "$PORT" run ./my_app/__init__.py
```
This runs straight from your computer, handy while developing — but it
skips `main.py`, so some ambient globals (`io`/`badge`, depending on the
version) won't be available in this mode. For a test that matches real
usage, install the app and launch it from the menu with the real buttons
while `mpremote connect "$PORT" repl` is listening on the serial port.

## API mapping table

| Old (GitHub Universe 2025) | New (current firmware) |
|---|---|
| `brushes.color(r,g,b[,a])` | `color.rgb(r,g,b[,a])` |
| `screen.brush = X` | `screen.pen = X` |
| `shapes.rectangle/squircle/...` | `shape.rectangle/squircle/...` |
| `screen.draw(x)` | `screen.shape(x)` |
| `Matrix()` | `mat3()` |
| `Image.load(...)` | `image.load(...)` |
| `PixelFont.load(...)` | `font.load(...)` |
| `screen.scale_blit(img, x, y, w, h)` | `screen.blit(img, rect(x, y, w, h))` |
| `SpriteSheet(path, cols, rows)` then `.sprite(i, 0)` | `image.load(path).spritesheet(cols, rows)` then `.sprite(i, 0)` |
| `io.BUTTON_X in io.pressed` | `badge.pressed(BUTTON_X)` |
| `io.BUTTON_X in io.held` | `badge.held(BUTTON_X)` |
| `io.BUTTON_X in io.released` | `badge.released(BUTTON_X)` |
| `io.BUTTON_X in io.changed` | `badge.changed(BUTTON_X)` |
| `io.ticks` | `badge.ticks` |
| `from badgeware import screen, color, ...` | nothing — everything is ambient once the app is launched via `run()` |
| `if __name__ == "__main__": run(update)` | `run(update)` unconditionally, as the last line of the file |

`screen`, `color`, `shape`, `image`, `font`, `mat3`, `vec2`, `rect`,
`badge`, the `BUTTON_*` constants, and `run` are all **ambient** inside
an app launched normally (from the menu, via `main.py`) — no `import`
needed to access them. The only place `from badgeware import run,
fatal_error` is a genuinely necessary import is in `main.py` itself
(the very first call in the chain, before anything has been injected
yet).

No confirmed mapping yet for `AnimatedSprite` or a few rarely-used
functions — if the script spots one, it flags it instead of guessing.

## The porting script

`port_badgeware.py` automatically applies the table above to a single
file or a whole folder:

```bash
python3 port_badgeware.py my_app/__init__.py
python3 port_badgeware.py my_app/              # every .py file in the folder
```

What it does:
- applies all the simple renames from the table (`brushes.color`,
  `shapes.`, `Matrix(`, `Image.load`, `PixelFont.load`, `screen.draw(`,
  `io.ticks`)
- converts `io.BUTTON_X in io.<state>` into `badge.<state>(BUTTON_X)`
  for all 4 states (pressed/held/released/changed)
- converts `screen.scale_blit(img, x, y, w, h)` into
  `screen.blit(img, rect(x, y, w, h))`
- completely strips any `from badgeware import ...` or
  `import badgeware` line
- unwraps the `if __name__ == "__main__": run(update)` guard

Every modified file keeps a `.bak` copy alongside it. What the script
does **not** touch, and lists at the end of the run under
`needs manual review`:
- a bare `io.held`/`io.poll()` used without a specific button — this
  pattern has never been confirmed on the current firmware
- `SpriteSheet(`/`AnimatedSprite(` — check the mapping in the table
  above, the script won't do this one for you
- a `scale_blit` call with arguments too complex for the regex
  (a multi-line call with nested expressions)

## Debugging a crash

- **Clean Python error with a traceback** → stay connected via
  `mpremote connect "$PORT" repl` while launching the app with the
  real buttons from the menu; the traceback shows up in the terminal.
- **Silent reboot, no traceback at all** → this is almost never an API
  naming issue (a Python error would show up). Usual suspects: `run(update)`
  being called twice (check there's no leftover `__main__` guard), an
  import failing further down the chain, or memory running out while
  loading (too many fonts/images at once). Isolate it by testing a
  minimal `update()` first, then add the rest back in chunks.
- **`AttributeError` on a name that "should" exist** → check `dir(object)`
  live from inside a real, launched app context (not from a bare REPL —
  `screen`, `badge`, `image`, etc. don't exist outside of an app's launch
  context).
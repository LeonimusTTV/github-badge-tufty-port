# Octocat Slots — a GitHub-themed slot machine for the badge.
#
# Controls:
#   B or A   = spin the reels (costs 1 credit)
#   UP       = raise bet (idle)
#   DOWN     = lower bet (idle)
#   C        = refill credits when you hit zero
#   A+B+C    = (held together) toggle the reel theme, saved to conf.py
#
# Config (conf.py, edit on the badge or in-game):
#   RKO = 1  ->  GitHub-themed reels (octocat, RKO'27, star, merge, fork, GitHub mark)
#   RKO = 0  ->  classic casino reels (7, BAR, cherry, GitHub, bell, lemon)
#   WIN = 1  ->  boosted payouts (credits trend upward over a long session)
#   WIN = 0  ->  original, tighter payouts
#
# Features:
#   - Two swappable reel themes sharing one payout table
#   - Weighted outcomes: ~4% jackpot / ~16% pair / ~80% loss
#   - Persistent credits + best-win high score
#   - Live theme toggle written back to conf.py (A+B+C Easter egg)

import json
import os
import random
import sys

sys.path.insert(0, "/system/apps/octoslots")
os.chdir("/system/apps/octoslots")

W = 160
H = 120
STATE_IDLE = 0
STATE_SPINNING = 1
STATE_RESULT = 2

# Two reel themes. Both have 6 symbols so the payout tables (indexed by symbol
# position, best-first) apply to either theme.
THEMES = {
    1: {
        "names": ("OCTO", "RKO27", "STAR", "MERGE", "FORK", "GITHUB"),
        "sheet": "assets/symbols.png",
        "title": "OCTO SLOTS",
        "corner": "RKO'27",
    },
    0: {
        "names": ("SEVEN", "BAR", "CHERRY", "GITHUB", "BELL", "LEMON"),
        "sheet": "assets/symbols_casino.png",
        "title": "MEGA SLOTS",
        "corner": "VEGAS",
    },
}

CONF_TEMPLATE = (
    "# Octocat Slots configuration\n"
    "#\n"
    "# RKO = 1  ->  GitHub / RKO'27 themed reels (octocat, RKO'27, star, merge, fork, GitHub)\n"
    "# RKO = 0  ->  classic casino reels (7, BAR, cherry, GitHub, bell, lemon)\n"
    "#\n"
    "# WIN = 1  ->  boosted payouts (credits trend upward over a long session)\n"
    "# WIN = 0  ->  original, tighter payouts\n"
    "#\n"
    "# You can also switch reel themes live in-game by holding A + B + C together.\n"
    "RKO = %d  # Revenue Kick Off Rulez\n"
    "WIN = %d  # Everyone is a winner\n"
)

# Payout tables (per symbol index, best-first), selected by the WIN config.
#   WIN = 1  boosted: the smallest pair covers the average losing streak, so with
#            the ~20%% win rate credits trend upward over a long session.
#   WIN = 0  original tighter payouts.
PAYOUTS = {
    1: {"triple": (80, 60, 45, 30, 30, 40), "pair": (12, 10, 9, 8, 8, 9)},
    0: {"triple": (50, 35, 25, 18, 18, 22), "pair": (8, 6, 5, 4, 4, 5)},
}
TRIPLE_PAYOUTS = PAYOUTS[1]["triple"]
PAIR_PAYOUTS = PAYOUTS[1]["pair"]

REEL_X = (16, 62, 108)
REEL_Y = 36
REEL_W = 36
REEL_H = 38
SPIN_DURATIONS = (850, 1300, 1780)

SAVE_PATHS = ("/storage/octoslots.json", "octoslots_state.json")

screen.antialias = image.X2
large_font = font.load("/system/assets/fonts/ziplock.ppf")
small_font = font.load("/system/assets/fonts/nope.ppf")
tiny_font = font.load("/system/assets/fonts/ark.ppf")

RKO = 1
WIN = 1
SYMBOL_NAMES = THEMES[RKO]["names"]
TITLE = THEMES[RKO]["title"]
CORNER = THEMES[RKO]["corner"]
symbol_sheet = None
symbol_images = []


def _read_conf_int(name, default):
    try:
        with open("conf.py") as fh:
            for line in fh:
                s = line.strip()
                if s.startswith(name):
                    rest = s[len(name):].lstrip()
                    if rest.startswith("="):
                        val = rest[1:].strip()
                        return 0 if val.startswith("0") else 1
    except Exception:
        pass
    return default


def _write_conf():
    try:
        with open("conf.py", "w") as fh:
            fh.write(CONF_TEMPLATE % (1 if RKO else 0, 1 if WIN else 0))
    except Exception:
        pass


def _apply_payouts(win):
    global WIN, TRIPLE_PAYOUTS, PAIR_PAYOUTS
    WIN = 1 if win else 0
    TRIPLE_PAYOUTS = PAYOUTS[WIN]["triple"]
    PAIR_PAYOUTS = PAYOUTS[WIN]["pair"]


def load_theme(rko):
    global RKO, SYMBOL_NAMES, TITLE, CORNER, symbol_sheet, symbol_images
    RKO = 1 if rko else 0
    theme = THEMES[RKO]
    SYMBOL_NAMES = theme["names"]
    TITLE = theme["title"]
    CORNER = theme["corner"]
    symbol_sheet = image.load(theme["sheet"])
    sheet_view = symbol_sheet.spritesheet(len(SYMBOL_NAMES), 1)
    print(sheet_view)
    print(dir(sheet_view))
    symbol_images = [sheet_view.sprite(i, 0) for i in range(len(SYMBOL_NAMES))]


_apply_payouts(_read_conf_int("WIN", 1))
load_theme(_read_conf_int("RKO", 1))

state = STATE_IDLE
credits = 10
bet = 1
best_win = 0
last_win = 0
result_kind = ""
message = "Press B to pull"

reels = [0, 1, 2]
final_reels = [0, 1, 2]
reel_next_tick = [0, 0, 0]
spin_start = 0
result_start = 0
flash_until = 0
particles = []
forced_outcome = None
_saved_once = False
_combo_latched = False
_rng_state = 0x5EED1234


def _combo_active():
    try:
        return badge.held(BUTTON_A) and badge.held(BUTTON_B) and badge.held(BUTTON_C)
    except Exception:
        return False


def _check_theme_toggle():
    # Hold A + B + C together to flip between RKO and casino reels.
    global _combo_latched, message
    combo = _combo_active()
    if combo and not _combo_latched:
        _combo_latched = True
        load_theme(0 if RKO else 1)
        _write_conf()
        message = "RKO mode!" if RKO else "Casino mode!"
        return True
    if not combo:
        _combo_latched = False
    return False


def _randint(a, b):
    global _rng_state
    try:
        return random.randint(a, b)
    except Exception:
        _rng_state = (1103515245 * (_rng_state + badge.ticks) + 12345) & 0x7fffffff
        return a + (_rng_state % (b - a + 1))


def _choice(seq):
    return seq[_randint(0, len(seq) - 1)]


def _load_state():
    global credits, best_win, bet
    for path in SAVE_PATHS:
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
            credits = max(0, int(data.get("credits", credits)))
            best_win = max(0, int(data.get("best_win", best_win)))
            bet = min(3, max(1, int(data.get("bet", bet))))
            return
        except Exception:
            pass


def _save_state():
    global _saved_once
    payload = {"credits": int(credits), "best_win": int(best_win), "bet": int(bet)}
    for path in SAVE_PATHS:
        try:
            with open(path, "w") as fh:
                json.dump(payload, fh)
            _saved_once = True
            return
        except Exception:
            pass


def _safe_led(zone, r, g, b):
    try:
        if hasattr(io, "set_led"):
            badge.set_led(zone, r, g, b)
            return True
        if hasattr(io, "led"):
            badge.led(zone, r, g, b)
            return True
        if hasattr(io, "set_backlight"):
            badge.set_backlight(zone, r, g, b)
            return True
    except Exception:
        pass
    return False


def _flash_backlight(on):
    # The public docs expose LED zone constants but not the setter yet. Try the
    # obvious badgeware hooks and no-op in the simulator/current firmware docs.
    zones = []
    for name in ("LED_TOP_LEFT", "LED_TOP_RIGHT", "LED_BOTTOM_RIGHT", "LED_BOTTOM_LEFT"):
        try:
            zones.append(getattr(io, name))
        except Exception:
            pass
    if not zones:
        return
    color = (255, 195, 0) if on else (0, 0, 0)
    for zone in zones:
        _safe_led(zone, color[0], color[1], color[2])


def init():
    global state, message, last_win, result_kind, particles, flash_until, reels, final_reels
    _load_state()
    state = STATE_IDLE
    last_win = 0
    result_kind = ""
    particles = []
    flash_until = 0
    reels = [0, 1, 2]
    final_reels = [0, 1, 2]
    message = "Press B to pull" if credits > 0 else "Press C for credits"


def on_exit():
    _flash_backlight(False)
    _save_state()


def debug_force_jackpot(symbol=0):
    global forced_outcome
    forced_outcome = [symbol, symbol, symbol]


def debug_force_out_of_credits():
    global credits, state, message
    credits = 0
    state = STATE_IDLE
    message = "Press C for credits"


def _weighted_outcome():
    # Real-slot odds: mostly losses, occasional pair, rare triple jackpot.
    n = len(SYMBOL_NAMES)
    roll = _randint(1, 100)
    if roll <= 4:
        s = _randint(0, n - 1)
        return [s, s, s]
    if roll <= 20:
        pair = _randint(0, n - 1)
        other = _randint(0, n - 2)
        if other >= pair:
            other += 1
        out = [pair, pair, other]
        for i in range(2, 0, -1):
            j = _randint(0, i)
            out[i], out[j] = out[j], out[i]
        return out
    # Losing spin: three distinct symbols, guaranteed no match.
    a = _randint(0, n - 1)
    b = _randint(0, n - 2)
    if b >= a:
        b += 1
    c = _randint(0, n - 3)
    for v in sorted((a, b)):
        if c >= v:
            c += 1
    out = [a, b, c]
    for i in range(2, 0, -1):
        j = _randint(0, i)
        out[i], out[j] = out[j], out[i]
    return out


def _start_spin(outcome=None):
    global state, credits, final_reels, reel_next_tick, spin_start, last_win, result_kind, message, forced_outcome
    if credits < bet:
        message = "Not enough credits"
        return
    credits -= bet
    if outcome is None:
        if forced_outcome is not None:
            outcome = forced_outcome
            forced_outcome = None
        else:
            outcome = _weighted_outcome()
    final_reels = [int(outcome[0]), int(outcome[1]), int(outcome[2])]
    spin_start = badge.ticks
    reel_next_tick = [spin_start, spin_start + 25, spin_start + 50]
    last_win = 0
    result_kind = ""
    message = "Spinning..."
    state = STATE_SPINNING


def _evaluate_result():
    global state, credits, best_win, last_win, result_kind, message, result_start, flash_until
    counts = {}
    for s in final_reels:
        counts[s] = counts.get(s, 0) + 1
    payout = 0
    kind = "TRY AGAIN"
    for s, c in counts.items():
        if c == 3:
            payout = TRIPLE_PAYOUTS[s] * bet
            kind = "JACKPOT!"
            break
    if payout == 0:
        for s, c in counts.items():
            if c == 2:
                payout = PAIR_PAYOUTS[s] * bet
                kind = "PAIR WIN!"
                break
    credits += payout
    last_win = payout
    best_win = max(best_win, payout)
    result_kind = kind
    if payout > 0:
        message = "+%d credits" % payout
        flash_until = badge.ticks + 2100
        _spawn_particles(28 if kind == "JACKPOT!" else 14)
    else:
        message = "No match"
    result_start = badge.ticks
    state = STATE_RESULT
    _save_state()


def _update_spin():
    stopped = 0
    now = badge.ticks
    for i in range(3):
        elapsed = now - spin_start
        if elapsed >= SPIN_DURATIONS[i]:
            reels[i] = final_reels[i]
            stopped += 1
            continue
        if now >= reel_next_tick[i]:
            reels[i] = (reels[i] + 1 + (i % 2)) % len(SYMBOL_NAMES)
            progress = elapsed / SPIN_DURATIONS[i]
            interval = 36 + int(progress * progress * 130) + (i * 7)
            reel_next_tick[i] = now + interval
    if stopped == 3:
        _evaluate_result()


def _spawn_particles(count):
    global particles
    colors = ((255, 211, 61), (63, 185, 80), (88, 166, 255), (255, 123, 114), (163, 113, 247))
    particles = []
    for _ in range(count):
        particles.append({
            "x": _randint(8, 152),
            "y": _randint(12, 62),
            "dx": _randint(-14, 14) / 10,
            "dy": _randint(-22, -4) / 10,
            "life": _randint(35, 70),
            "c": _choice(colors),
        })


def _update_particles():
    for p in particles[:]:
        p["x"] += p["dx"]
        p["y"] += p["dy"]
        p["dy"] += 0.08
        p["life"] -= 1
        if p["life"] <= 0 or p["y"] > H:
            particles.remove(p)


def _handle_idle_input():
    global bet, credits, message
    if credits <= 0:
        if badge.pressed(BUTTON_C):
            credits = 10
            bet = 1
            message = "Credits refilled!"
            _save_state()
        return
    if badge.pressed(BUTTON_UP):
        bet = min(3, max(1, credits), bet + 1)
        message = "Bet %d" % bet
        _save_state()
    if badge.pressed(BUTTON_DOWN):
        bet = max(1, bet - 1)
        message = "Bet %d" % bet
        _save_state()
    if (badge.pressed(BUTTON_B) or badge.pressed(BUTTON_A)) and not _combo_active():
        _start_spin()


def _handle_result_input():
    global state, message
    if (badge.ticks - result_start) > 2300:
        state = STATE_IDLE
        message = "Press B to pull" if credits > 0 else "Press C for credits"
    elif (badge.pressed(BUTTON_B) or badge.pressed(BUTTON_A)) and (badge.ticks - result_start) > 650 and not _combo_active():
        state = STATE_IDLE
        _start_spin()


def update():
    _draw()
    toggled = _check_theme_toggle()
    if not toggled:
        if state == STATE_IDLE:
            _handle_idle_input()
        elif state == STATE_SPINNING:
            _update_spin()
        elif state == STATE_RESULT:
            _update_particles()
            _handle_result_input()
    elif state == STATE_SPINNING:
        _update_spin()
    if flash_until:
        _flash_backlight((badge.ticks // 120) % 2 == 0 and badge.ticks < flash_until)


def _draw():
    _draw_background()
    _draw_header()
    _draw_reels()
    _draw_status()
    if state == STATE_RESULT:
        _draw_result()
    if credits <= 0 and state == STATE_IDLE:
        _draw_out_of_credits()


def _draw_background():
    pulse = 0
    if state == STATE_RESULT and last_win > 0:
        pulse = 18 if (badge.ticks // 120) % 2 == 0 else 0
    screen.pen = color.rgb(13 + pulse, 17, 23 + pulse)
    screen.clear()
    screen.pen = color.rgb(33, 38, 45)
    for y in (28, 96):
        screen.shape(shape.rectangle(0, y, W, 1))
    # Vegas bulb rails.
    for i in range(0, 160, 12):
        glow = 120 + ((i + badge.ticks // 12) % 80)
        screen.pen = color.rgb(glow, 90, 20)
        screen.shape(shape.circle(i + 4, 30, 2))
        screen.shape(shape.circle(i + 4, 94, 2))


def _draw_header():
    screen.font = small_font
    title = TITLE
    w, _ = screen.measure_text(title)
    screen.pen = color.rgb(0, 0, 0, 120)
    screen.text(title, 81 - w / 2, 5)
    screen.pen = color.rgb(255, 211, 61)
    screen.text(title, 80 - w / 2, 4)
    screen.font = tiny_font
    screen.pen = color.rgb(139, 148, 158)
    screen.text(CORNER, 4, 6)
    screen.text("BEST %d" % best_win, 120, 6)


def _draw_reels():
    for i, x in enumerate(REEL_X):
        # shadow and gold frame
        screen.pen = color.rgb(0, 0, 0, 120)
        screen.shape(shape.rounded_rectangle(x + 2, REEL_Y + 3, REEL_W, REEL_H, 5))
        screen.pen = color.rgb(218, 165, 32)
        screen.shape(shape.rounded_rectangle(x - 2, REEL_Y - 2, REEL_W + 4, REEL_H + 4, 6))
        screen.pen = color.rgb(246, 248, 250)
        screen.shape(shape.rounded_rectangle(x, REEL_Y, REEL_W, REEL_H, 4))
        screen.pen = color.rgb(210, 214, 220)
        screen.shape(shape.rectangle(x + 2, REEL_Y + 2, REEL_W - 4, 2))
        if state == STATE_SPINNING and (badge.ticks - spin_start) < SPIN_DURATIONS[i]:
            # Draw faint previous/next symbols for motion blur.
            prev = (reels[i] - 1) % len(SYMBOL_NAMES)
            nxt = (reels[i] + 1) % len(SYMBOL_NAMES)
            screen.blit(symbol_images[prev], rect(x + 7, REEL_Y - 14, 22, 22))
            screen.blit(symbol_images[nxt], rect(x + 7, REEL_Y + 29, 22, 22))
        screen.blit(symbol_images[reels[i]], rect(x + 2, REEL_Y + 3, 32, 32))


def _draw_status():
    screen.font = small_font
    screen.pen = color.rgb(240, 246, 252)
    screen.text("CR %02d" % credits, 5, 100)
    screen.text("BET %d" % bet, 58, 100)
    screen.text("WIN %02d" % last_win, 106, 100)
    screen.font = tiny_font
    hint = "B SPIN  UP/DN BET" if credits > 0 else "PRESS C TO REFILL"
    w, _ = screen.measure_text(hint)
    screen.pen = color.rgb(139, 148, 158)
    screen.text(hint, 80 - w / 2, 112)
    if message:
        screen.font = tiny_font
        w, _ = screen.measure_text(message)
        screen.pen = color.rgb(255, 255, 255)
        screen.text(message, 80 - w / 2, 22)


def _draw_result():
    for p in particles:
        screen.pen = color.rgb(p["c"][0], p["c"][1], p["c"][2])
        screen.shape(shape.rectangle(p["x"], p["y"], 2, 2))
    if result_kind and (last_win > 0 or (badge.ticks // 220) % 2 == 0):
        screen.font = large_font if result_kind == "JACKPOT!" else small_font
        w, _ = screen.measure_text(result_kind)
        y = 70 if result_kind == "JACKPOT!" else 74
        screen.pen = color.rgb(0, 0, 0, 180)
        screen.shape(shape.rounded_rectangle(22, y - 4, 116, 19, 5))
        screen.pen = color.rgb(255, 211, 61) if last_win > 0 else color.rgb(139, 148, 158)
        screen.text(result_kind, 80 - w / 2, y)


def _draw_out_of_credits():
    screen.pen = color.rgb(0, 0, 0, 190)
    screen.shape(shape.rounded_rectangle(13, 31, 134, 58, 7))
    screen.font = large_font
    text = "NO CREDITS"
    w, _ = screen.measure_text(text)
    screen.pen = color.rgb(255, 123, 114)
    screen.text(text, 80 - w / 2, 41)
    screen.font = small_font
    text = "Press C to refill"
    w, _ = screen.measure_text(text)
    screen.pen = color.rgb(240, 246, 252)
    screen.text(text, 80 - w / 2, 63)


run(update)

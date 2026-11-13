"""Generates the HUD assets (assets/hud/*.png) in the same style as assets/board/board.png.

    python tools/make_hud_assets.py

The colours are taken directly from board.png. All images are at the original (unscaled) resolution; the game scales them
by the same integer as the board. You can freely replace the files with your own drawings of the same structure:

    panel.png    16x16   9-slice, 6 px edges       (big wooden frame, like the board frame)
    inset.png    12x12   9-slice, 4 px edges       (sunken field for numbers and messages)
    button.png   48x12   4 states of 12x12 (normal, hover, pressed, disabled), 9-slice 4 px edges
    icons.png    12x12 per icon, in order: see ICON_ORDER in orderwick/config.py
    divider.png  4x2     a repeating tile (dashed line)
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "hud"

# --- palette from board.png -------------------------------------------------------------
# Colours are ROLES, so another board theme only needs another palette (see set_palette / tools/make_theme.py).
DEFAULT_PALETTE = {
    "WOOD": (90, 78, 68),             # outer frame
    "DARK": (66, 57, 52),             # dark line / icon outline
    "MID": (121, 103, 85),            # mid tone (lane edge, dashed edge)
    "PLANK": (136, 115, 90),          # flat plank (panel interior)
    "PLANK_L": (158, 133, 97),        # lighter plank (button body)
    "TAN": (199, 176, 139),           # light colour of the dashed edge
    "CREAM": (250, 214, 184),         # lightest (hover highlight)
    "BTN_LIGHT": (199, 176, 139),     # top highlight line of a normal button
    "BTN_HOVER_LIGHT": (250, 214, 184),
    "BTN_HOVER_BODY": (181, 156, 116),
    "BTN_DISABLED_BODY": (101, 88, 76),
    "ICON_LIGHT": (250, 214, 184),    # main colour of the icons ("x")
    "ICON_MID": (199, 176, 139),      # secondary icon colour ("o")
}
WOOD = DARK = MID = PLANK = PLANK_L = TAN = CREAM = (0, 0, 0)
BTN_LIGHT = BTN_HOVER_LIGHT = BTN_HOVER_BODY = BTN_DISABLED_BODY = ICON_LIGHT = ICON_MID = (0, 0, 0)
GOLD = (255, 205, 80)      # the game's accent (title)
GOLD_D = (190, 130, 40)
GREEN = (90, 200, 120)
GREEN_D = (40, 110, 60)
RED = (214, 90, 80)
BLUE = (90, 160, 220)
CLEAR = (0, 0, 0, 0)


def set_palette(palette: dict) -> None:
    """Switches every generator below to another palette (missing roles keep the default colour)."""
    full = {**DEFAULT_PALETTE, **{k: tuple(v) for k, v in palette.items() if k in DEFAULT_PALETTE}}
    globals().update(full)
    globals()["COLORS"] = {"x": ICON_LIGHT, "o": ICON_MID, "g": GOLD, "G": GOLD_D, "r": RED, "e": GREEN, "E": GREEN_D,
                           "p": DARK, "b": BLUE}




def surf(w: int, h: int) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


# ---------------------------------------------------------------------------- panel ------
def make_panel() -> pygame.Surface:
    """Wooden frame: 3 px WOOD, 1 px DARK, 2 px dashed checkered edge (MID/TAN), then the plank."""
    s = surf(16, 16)
    for y in range(16):
        for x in range(16):
            d = min(x, y, 15 - x, 15 - y)
            if d <= 2:
                c = WOOD
            elif d == 3:
                c = DARK
            elif d <= 5:
                c = MID if (x + y) % 2 == 0 else TAN
            else:
                c = PLANK
            s.set_at((x, y), c)
    return s


def make_inset() -> pygame.Surface:
    """Sunken field: dark line, shadow at the top/left, lighter edge at the bottom/right."""
    s = surf(12, 12)
    for y in range(12):
        for x in range(12):
            d = min(x, y, 11 - x, 11 - y)
            if d == 0:
                c = DARK
            elif d == 1:
                c = DARK if (y == 1 or x == 1) else MID
            else:
                c = WOOD
            s.set_at((x, y), c)
    for x, y in ((0, 0), (11, 0), (0, 11), (11, 11)):      # zaobljeni uglovi
        s.set_at((x, y), CLEAR)
    return s


def make_button() -> pygame.Surface:
    """Four states of 12x12: bevelled, with a light edge on top and a shadow at the bottom."""
    states = {
        #             body            light    shadow   (top/bottom swapped for 'pressed')
        "normal":   (PLANK_L,           BTN_LIGHT,       MID),
        "hover":    (BTN_HOVER_BODY,    BTN_HOVER_LIGHT, PLANK),
        "pressed":  (PLANK,             MID,             PLANK_L),
        "disabled": (BTN_DISABLED_BODY, MID,             WOOD),
    }
    sheet = surf(12 * len(states), 12)
    for i, (body, light, shade) in enumerate(states.values()):
        x0 = i * 12
        for y in range(12):
            for x in range(12):
                d = min(x, y, 11 - x, 11 - y)
                if d == 0:
                    c = DARK
                elif y == 1:
                    c = light
                elif y == 10:
                    c = shade
                else:
                    c = body
                sheet.set_at((x0 + x, y), c)
        for cx, cy in ((0, 0), (11, 0), (0, 11), (11, 11)):
            sheet.set_at((x0 + cx, cy), CLEAR)
        # 'pressed' looks sunken: the top edge is a shadow
    return sheet


def make_divider() -> pygame.Surface:
    s = surf(4, 2)
    for y in range(2):
        for x in range(4):
            s.set_at((x, y), MID if (x + y) % 2 == 0 else TAN)
    return s


# ---------------------------------------------------------------------------- icons -------
# x = light (cream), o = secondary light (shade), g = gold, G = dark gold, r = red, e = green, E = dark green,
# p = hole/dot (dark). A 1 px dark outline is added automatically around every shape.
ICONS: dict[str, list[str]] = {
    "undo": [
        "...x....",
        "..xx....",
        ".xxxxxxx",
        "xxxxxxxx",
        ".xxxxxxx",
        "..xx....",
        "...x....",
        "........",
    ],
    "rescue": [
        "...ee...",
        "...ee...",
        "...ee...",
        "eeeeeeee",
        "eeeeeeee",
        "...ee...",
        "...ee...",
        "...ee...",
    ],
    "restart": [
        "xxxxxxxx",
        "xpxxxxpx",
        "xxxxxxxx",
        "xxxppxxx",
        "xxxppxxx",
        "xxxxxxxx",
        "xpxxxxpx",
        "xxxxxxxx",
    ],
    "pause": [
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
        ".xx..xx.",
    ],
    "moves": [
        "x..x....",
        "xx.xx...",
        ".xx.xx..",
        "..xx.xx.",
        "..xx.xx.",
        ".xx.xx..",
        "xx.xx...",
        "x..x....",
    ],
    "time": [
        "..xxxx..",
        ".xxppxx.",
        "xxxppxxx",
        "xxxpppxx",
        "xxxxxxxx",
        "xxxxxxxx",
        ".xxxxxx.",
        "..xxxx..",
    ],
    "score": [
        "...gg...",
        "...gg...",
        "gggggggg",
        ".gggggg.",
        "..gggg..",
        ".gggggg.",
        ".gg..gg.",
        "gg....gg",
    ],
    "lock": [
        "..xxxx..",
        ".xx..xx.",
        ".xx..xx.",
        "xxxxxxxx",
        "xxxppxxx",
        "xxxppxxx",
        "xxxxxxxx",
        "xxxxxxxx",
    ],
}
ICON_ORDER = list(ICONS)
COLORS: dict = {}
set_palette(DEFAULT_PALETTE)


def make_icons() -> pygame.Surface:
    sheet = surf(12 * len(ICONS), 12)
    for i, name in enumerate(ICON_ORDER):
        rows = ICONS[name]
        mask = {(x, y): COLORS[ch] for y, row in enumerate(rows) for x, ch in enumerate(row) if ch != "."}
        cell = surf(12, 12)
        for (x, y) in mask:                           # outline: every neighbouring empty cell (8 directions)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n not in mask:
                        cell.set_at((n[0] + 2, n[1] + 2), DARK)
        for (x, y), c in mask.items():
            cell.set_at((x + 2, y + 2), c)
        sheet.blit(cell, (i * 12, 0))
    return sheet


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT))
    from orderwick import config
    assert ICON_ORDER == config.ICON_ORDER, "the icon order must match config.ICON_ORDER"
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, image in (("panel", make_panel()), ("inset", make_inset()), ("button", make_button()),
                        ("icons", make_icons()), ("divider", make_divider())):
        pygame.image.save(image, str(OUT / f"{name}.png"))
        print(f"{name}.png  {image.get_width()}x{image.get_height()}")
    print("icons:", ", ".join(ICON_ORDER))


if __name__ == "__main__":
    main()

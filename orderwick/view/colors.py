"""Text and UI colours that follow the selected board theme.

The values are `pygame.Color` objects that are UPDATED IN PLACE when a theme is applied (see apply()), so every module that
imported them keeps seeing the current colours. Theme palette roles come from assets/themes/<id>/palette.json (see
tools/make_theme.py); a missing role keeps the default (wood) colour.
"""
from __future__ import annotations

import pygame

DEFAULTS = {
    "TEXT": (250, 214, 184),             # main text (cream)
    "TEXT_DIM": (199, 176, 139),         # secondary text (tan)
    "TEXT_SHADOW": (66, 57, 52),         # drop shadow of text / dark lines
    "BTN_TEXT": (250, 214, 184),         # button labels
    "BTN_TEXT_SHADOW": (66, 57, 52),
    "DISABLED_TEXT": (150, 135, 115),
    "UI_DIM": (121, 103, 85),            # unfilled slider blocks, disabled arrows
    "HIGHLIGHT": (88, 72, 40),           # highlighted leaderboard row
    "BTN_VALUE": (255, 205, 80),         # values shown on button-like rows (settings)
    "BTN_GOOD": (110, 220, 140),         # "ON" on a row
    "BTN_BAD": (250, 120, 110),          # "OFF" / locked on a row
}
GOLD = pygame.Color(255, 205, 80)        # accent: titles (same in every theme)
GOOD = pygame.Color(110, 220, 140)
BAD = pygame.Color(250, 120, 110)

CREAM = pygame.Color(*DEFAULTS["TEXT"])
TAN = pygame.Color(*DEFAULTS["TEXT_DIM"])
DARK = pygame.Color(*DEFAULTS["TEXT_SHADOW"])
BTN_TEXT = pygame.Color(*DEFAULTS["BTN_TEXT"])
BTN_SHADOW = pygame.Color(*DEFAULTS["BTN_TEXT_SHADOW"])
DISABLED = pygame.Color(*DEFAULTS["DISABLED_TEXT"])
UI_DIM = pygame.Color(*DEFAULTS["UI_DIM"])
HIGHLIGHT = pygame.Color(*DEFAULTS["HIGHLIGHT"])
BTN_VALUE = pygame.Color(*DEFAULTS["BTN_VALUE"])
BTN_GOOD = pygame.Color(*DEFAULTS["BTN_GOOD"])
BTN_BAD = pygame.Color(*DEFAULTS["BTN_BAD"])

_TARGETS = {"TEXT": CREAM, "TEXT_DIM": TAN, "TEXT_SHADOW": DARK, "BTN_TEXT": BTN_TEXT, "BTN_TEXT_SHADOW": BTN_SHADOW,
            "DISABLED_TEXT": DISABLED, "UI_DIM": UI_DIM, "HIGHLIGHT": HIGHLIGHT, "BTN_VALUE": BTN_VALUE,
            "BTN_GOOD": BTN_GOOD, "BTN_BAD": BTN_BAD}


def apply(palette: dict | None) -> None:
    """Switches all colours to the theme palette (None / missing roles = the defaults)."""
    palette = palette or {}
    for role, color in _TARGETS.items():
        r, g, b = palette.get(role, DEFAULTS[role])[:3]
        color.update(r, g, b)

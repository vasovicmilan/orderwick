"""Shared helper functions for scenes."""
from __future__ import annotations

import pygame

from .. import config


def clear(surface: pygame.Surface) -> None:
    surface.fill(config.COLOR_BG)


def centered(nw: int, nh: int, w: int, h: int) -> pygame.Rect:
    """A w x h rectangle centred in the native surface (not larger than it)."""
    r = pygame.Rect(0, 0, min(w, nw - 8), min(h, nh - 8))
    r.center = (nw // 2, nh // 2)
    return r


def full_panel(nw: int, nh: int, margin: int = 6) -> pygame.Rect:
    return pygame.Rect(margin, margin, nw - 2 * margin, nh - 2 * margin)

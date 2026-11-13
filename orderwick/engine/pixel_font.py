"""Pixel font: always unsmoothed and scaled by an integer factor (nearest neighbour).

The font is drawn on an 8x8 grid, so it is loaded at size 8 (1 font pixel = 1 pixel) and scaled by an
integer factor. The letters stay sharp and use the same "pixel" as the board, cards and HUD.
"""
from __future__ import annotations

import pygame

from .. import config

BASE_SIZE = 8


def _prep(text: str, upper: bool = True) -> str:
    """Public Pixel is drawn for capital letters (lowercase is hard to read at 8 px): the UI is written in CAPITALS.
    The body font (Pixel Operator 8) has readable lowercase, so its text is left unchanged."""
    return text.upper() if (upper and config.UPPERCASE_UI) else text


class PixelFont:
    """Compatible with pygame.font.Font where we need it: render(), size(), get_height()."""

    def __init__(self, path, scale: int = 1, upper: bool = True):
        self._font = pygame.font.Font(str(path), BASE_SIZE)
        self.scale = max(1, int(scale))
        self.upper = upper

    def render(self, text: str, antialias: bool = False, color=(255, 255, 255), background=None):
        surf = self._font.render(_prep(text, self.upper), False, color).convert_alpha()
        if self.scale > 1:
            surf = pygame.transform.scale(surf, (surf.get_width() * self.scale, surf.get_height() * self.scale))
        return surf

    def size(self, text: str) -> tuple[int, int]:
        w, h = self._font.size(_prep(text, self.upper))
        return w * self.scale, h * self.scale

    def get_height(self) -> int:
        return self._font.get_height() * self.scale

    def get_linesize(self) -> int:
        return self._font.get_linesize() * self.scale

    def has_glyphs(self, text: str) -> bool:
        """Does the font have every character (metrics returns None for missing ones)."""
        return all(self._font.metrics(ch)[0] is not None for ch in text)

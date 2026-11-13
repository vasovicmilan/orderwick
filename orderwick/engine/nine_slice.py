"""9-slice: an image with four corners that do not stretch; edges and centre are REPEATED (tiled).

Tiling (instead of stretching) keeps small patterns in pixel art, e.g. the checkered dashed edge. That is why the
edge slices should have an EVEN length.
"""
from __future__ import annotations

import pygame


class NineSlice:
    def __init__(self, image: pygame.Surface, left: int, top: int | None = None,
                 right: int | None = None, bottom: int | None = None):
        self.image = image
        self.left = left
        self.top = left if top is None else top
        self.right = left if right is None else right
        self.bottom = self.top if bottom is None else bottom
        self._cache: dict[tuple[int, int], pygame.Surface] = {}

    @property
    def min_size(self) -> tuple[int, int]:
        return self.left + self.right + 1, self.top + self.bottom + 1

    def render(self, size: tuple[int, int]) -> pygame.Surface:
        w = max(size[0], self.min_size[0])
        h = max(size[1], self.min_size[1])
        key = (w, h)
        out = self._cache.get(key)
        if out is None:
            out = self._cache[key] = self._build(w, h)
        return out

    def _build(self, w: int, h: int) -> pygame.Surface:
        src = self.image
        sw, sh = src.get_size()
        L, T, R, B = self.left, self.top, self.right, self.bottom
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        # uglovi
        out.blit(src, (0, 0), pygame.Rect(0, 0, L, T))
        out.blit(src, (w - R, 0), pygame.Rect(sw - R, 0, R, T))
        out.blit(src, (0, h - B), pygame.Rect(0, sh - B, L, B))
        out.blit(src, (w - R, h - B), pygame.Rect(sw - R, sh - B, R, B))
        # ivice i sredina (ponavljanje)
        cw, ch = sw - L - R, sh - T - B
        iw, ih = w - L - R, h - T - B
        self._tile(out, pygame.Rect(L, 0, cw, T), pygame.Rect(L, 0, iw, T))
        self._tile(out, pygame.Rect(L, sh - B, cw, B), pygame.Rect(L, h - B, iw, B))
        self._tile(out, pygame.Rect(0, T, L, ch), pygame.Rect(0, T, L, ih))
        self._tile(out, pygame.Rect(sw - R, T, R, ch), pygame.Rect(w - R, T, R, ih))
        self._tile(out, pygame.Rect(L, T, cw, ch), pygame.Rect(L, T, iw, ih))
        return out

    def _tile(self, out: pygame.Surface, src_rect: pygame.Rect, dst: pygame.Rect) -> None:
        if src_rect.w <= 0 or src_rect.h <= 0 or dst.w <= 0 or dst.h <= 0:
            return
        y = dst.y
        while y < dst.bottom:
            hh = min(src_rect.h, dst.bottom - y)
            x = dst.x
            while x < dst.right:
                ww = min(src_rect.w, dst.right - x)
                out.blit(self.image, (x, y), pygame.Rect(src_rect.x, src_rect.y, ww, hh))
                x += src_rect.w
            y += src_rect.h

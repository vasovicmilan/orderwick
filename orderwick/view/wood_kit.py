"""Wooden UI kit for ALL screens (menu, level select, ...): draws on a NATIVE surface (1 px = 1 asset px).

It uses the same assets as the HUD (panel, inset, 4-state button) and the same font; the whole screen is then scaled
by an integer factor (see engine/native_scene.py). Arrows are drawn from code (no new asset).
"""
from __future__ import annotations

import pygame

from .. import config
from ..engine.assets import AssetManager
from ..engine.nine_slice import NineSlice
from ..engine.pixel_font import PixelFont

from .colors import BAD, BTN_SHADOW, BTN_TEXT, CREAM, DARK, DISABLED, GOLD, GOOD, TAN, UI_DIM  # live colours that follow the theme
__all__ = ["WoodKit", "CardTicker", "BAD", "BTN_SHADOW", "BTN_TEXT", "CREAM", "DARK", "DISABLED", "GOLD", "GOOD", "TAN", "UI_DIM"]

_ARROW = ["...#", "..##", ".###", "####", ".###", "..##", "...#"]     # strelica ulevo, 4x7
ARROW_W, ARROW_H = 4, 7


class WoodKit:
    PANEL_EDGE = 6
    INSET_EDGE = 4

    def __init__(self, assets: AssetManager):
        self.assets = assets
        self.panel = NineSlice(assets.image(config.HUD_PANEL), self.PANEL_EDGE)
        self.inset = NineSlice(assets.image(config.HUD_INSET), self.INSET_EDGE)
        self.frame_color = tuple(assets.image(config.HUD_PANEL).get_at((1, 1)))[:3]       # outer frame colour of the theme
        sheet = assets.image(config.HUD_BUTTON)
        self.buttons = {name: NineSlice(sheet.subsurface(pygame.Rect(i * 12, 0, 12, 12)), 4)
                        for i, name in enumerate(config.BUTTON_STATES)}
        icons = assets.image(config.HUD_ICONS)
        c = config.ICON_CELL
        self.icons = {name: icons.subsurface(pygame.Rect(i * c, 0, c, c)) for i, name in enumerate(config.ICON_ORDER)}
        aicons = assets.image(config.AUDIO_ICONS)
        self.icons.update({name: aicons.subsurface(pygame.Rect(i * c, 0, c, c))
                           for i, name in enumerate(config.AUDIO_ICON_ORDER)})
        self.f8 = assets.pixel_font(1)
        self.f16 = assets.pixel_font(2)
        self.body = PixelFont(config.BODY_FONT_PATH, 1, upper=False)      # a small, readable font for longer texts

    # ---- tekst ------------------------------------------------------------------------------
    def text(self, surf, text, pos, color=CREAM, anchor="topleft", big=False, shadow=True, body=False,
             shadow_color=None) -> pygame.Rect:
        font = self.body if body else (self.f16 if big else self.f8)
        img = font.render(text, False, color)
        rect = img.get_rect(**{anchor: pos})
        if shadow:
            surf.blit(font.render(text, False, shadow_color or DARK), rect.move(1, 1))
        surf.blit(img, rect)
        return rect

    def width(self, text: str, big: bool = False) -> int:
        return (self.f16 if big else self.f8).size(text)[0]

    def wrap(self, text: str, width: int, body: bool = False) -> list[str]:
        font = self.body if body else self.f8
        lines: list[str] = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split(" "):
                trial = f"{line} {word}".strip()
                if font.size(trial)[0] <= width or not line:
                    line = trial
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    # ---- okviri ----------------------------------------------------------------------------------
    def draw_panel(self, surf, rect: pygame.Rect) -> None:
        surf.blit(self.panel.render(rect.size), rect.topleft)

    def draw_inset(self, surf, rect: pygame.Rect) -> None:
        surf.blit(self.inset.render(rect.size), rect.topleft)

    def fit_label(self, label: str, avail: int, two_lines: bool) -> tuple[list[str], bool]:
        """Splits a label that is too wide: onto two lines (when the button is tall enough), otherwise into the narrower
        body font. Returns (lines, use_body_font). A label that fits is returned as it is."""
        if self.f8.size(label)[0] <= avail:
            return [label], False
        words = label.split(" ")
        if two_lines and len(words) > 1:
            best = None
            for i in range(1, len(words)):
                a, b = " ".join(words[:i]), " ".join(words[i:])
                w = max(self.f8.size(a)[0], self.f8.size(b)[0])
                if best is None or w < best[0]:
                    best = (w, [a, b])
            if best and best[0] <= avail:
                return best[1], False
        if self.body.size(label)[0] <= avail:
            return [label], True
        return [label], True                                   # still wider: drawn clipped by the caller

    def draw_button(self, surf, rect: pygame.Rect, label: str, state: str = "normal",
                    icon: str | None = None, hint: str = "") -> None:
        surf.blit(self.buttons[state].render(rect.size), rect.topleft)
        down = 1 if state == "pressed" else 0
        color = BTN_TEXT if state != "disabled" else DISABLED
        shadow = state != "disabled"
        has_icon = icon in self.icons
        hint_w = self.f8.size(hint)[0] + 6 if hint else 0
        side = max(config.ICON_CELL + 2 if has_icon else 0, hint_w)           # the label is centred: keep room on both sides
        avail = rect.w - 2 * (4 + side)
        lines, body = self.fit_label(label, avail, rect.h >= 19)
        line_h = 9 if len(lines) > 1 else 8
        cy = rect.y + (rect.h - (8 + (len(lines) - 1) * line_h)) // 2 + down
        if has_icon:
            surf.blit(self.icons[icon], (rect.x + 4, rect.y + (rect.h - config.ICON_CELL) // 2 + down))
        old = surf.get_clip()
        surf.set_clip(rect.inflate(-4, 0).clip(old) if old else rect.inflate(-4, 0))
        for i, line in enumerate(lines):
            self.text(surf, line, (rect.centerx, cy + i * line_h), color, "midtop", shadow=shadow, body=body,
                      shadow_color=BTN_SHADOW)
        surf.set_clip(old)
        if hint:
            self.text(surf, hint, (rect.right - 5, rect.y + (rect.h - 8) // 2 + down), BTN_TEXT, "topright", shadow=False)

    def draw_arrow(self, surf, center: tuple[int, int], direction: int, color) -> None:
        """direction: -1 ulevo, +1 udesno."""
        x0, y0 = center[0] - ARROW_W // 2, center[1] - ARROW_H // 2
        for y, row in enumerate(_ARROW):
            for x, c in enumerate(row):
                if c == "#":
                    px = x0 + (x if direction < 0 else ARROW_W - 1 - x)
                    surf.set_at((px, y0 + y), color)

    def fruit_strip(self, surf, names: list[str], center: tuple[int, int]) -> pygame.Rect:
        """A row of cards in a wooden frame (native: 16x16 cards)."""
        cell, gap = config.CELL, 3
        w = len(names) * cell + (len(names) + 1) * gap
        rect = pygame.Rect(0, 0, w, cell + 2 * gap)
        rect.center = center
        surf.fill(self.frame_color, rect)
        for i, name in enumerate(names):
            surf.blit(self.assets.sprite(name), (rect.x + gap + i * (cell + gap), rect.y + gap))
        return rect


class CardTicker:
    """A strip of cards that slides right to left inside a frame; every card in the game comes in random order
    (bag: each card appears once before any card repeats)."""
    SPEED = 11.0                  # native pixels per second
    STEP = config.CELL + 3

    def __init__(self, names: list[str], width: int, rng):
        self.names = list(names)
        self.rng = rng
        self.offset = 0.0
        self.count = width // self.STEP + 3
        self._bag: list[str] = []
        self._last = ""
        self.queue = [self._next() for _ in range(self.count)]

    def _next(self) -> str:
        if not self._bag:
            self._bag = self.names[:]
            self.rng.shuffle(self._bag)
            if self._bag[-1] == self._last and len(self._bag) > 1:      # no two identical cards in a row
                self._bag[0], self._bag[-1] = self._bag[-1], self._bag[0]
        self._last = self._bag.pop()
        return self._last

    def update(self, dt: float) -> None:
        self.offset += self.SPEED * dt
        while self.offset >= self.STEP:
            self.offset -= self.STEP
            self.queue.pop(0)
            self.queue.append(self._next())

    def draw(self, surf, assets, rect: pygame.Rect, unlocked=None, frame_color=None) -> None:
        """Frame (wood) + cards clipped to the frame interior. Locked cards (not in `unlocked`) are question marks."""
        surf.fill(frame_color or config.COLOR_WOOD, rect)
        inner = rect.inflate(-6, -6)
        old = surf.get_clip()
        surf.set_clip(inner)
        x = inner.x - int(self.offset)
        for name in self.queue:
            shown = name if unlocked is None or name in unlocked else config.HIDDEN_SPRITE
            surf.blit(assets.sprite(shown), (x, inner.y))
            x += self.STEP
        surf.set_clip(old)

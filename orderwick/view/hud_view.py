"""HUD at the original pixel-art resolution: the right panel and the win window.

Everything is drawn on a "native" surface (1 pixel = 1 asset pixel), and only then is the WHOLE surface scaled by
the same integer as the board. So the frame, buttons, icons and letters use the same "pixel" as the cards.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .. import config
from ..engine.assets import AssetManager
from ..engine.nine_slice import NineSlice
from ..engine.pixel_font import PixelFont

W = config.HUD_WIDTH
MARGIN = 8
BTN_H = 16
BTN_GAP = 3
ROW_H = 12
INSET_PAD = 4          # thickness of the sunken field edge (9-slice)
from .colors import BAD, BTN_SHADOW, BTN_TEXT, CREAM, DARK, DISABLED as DISABLED_TEXT, GOLD, GOOD, TAN  # live colours
__all__ = ["HudView", "HudButton", "HudData", "WinData", "BAD", "CREAM", "GOLD", "GOOD", "TAN", "MIN_HUD_HEIGHT", "TIERS", "tier_for"]

# The HUD adapts to the available height (height = window height / scale): the less room there is,
# the more compact it gets (smaller title, no board-info row, shorter buttons). Messages get all the rest.
MSG_MIN = 26                      # smallest height of the message field (2 lines of text)
TIERS = {
    #        button height, gap, big title, "info" row, statistics row height
    "full":  dict(btn_h=16, btn_gap=3, big=True, info=True, row_h=12, top=8, bottom=8, min_h=222),
    "mid":   dict(btn_h=16, btn_gap=3, big=False, info=True, row_h=12, top=8, bottom=8, min_h=212),
    "tight": dict(btn_h=14, btn_gap=2, big=False, info=False, row_h=10, top=6, bottom=6, min_h=171),
}


def tier_for(height: int) -> str:
    return "full" if height >= TIERS["full"]["min_h"] else "mid" if height >= TIERS["mid"]["min_h"] else "tight"


MIN_HUD_HEIGHT = TIERS["tight"]["min_h"]


@dataclass
class HudButton:
    label: str
    icon: str
    enabled: bool = True


@dataclass
class HudData:
    mode_title: str
    heading: str
    info: list[str]
    moves: str
    time: str
    score: str
    messages: list[tuple[str, tuple]] = field(default_factory=list)
    buttons: list[HudButton] = field(default_factory=list)


@dataclass
class WinData:
    title: str
    rows: list[tuple[str, str, str]]       # (naziv, koliko, bodovi)
    total: str
    note: str = ""
    buttons: list[HudButton] = field(default_factory=list)


class HudView:
    WIN_WIDTH = 168

    def __init__(self, assets: AssetManager):
        self.assets = assets
        self.panel = NineSlice(assets.image(config.HUD_PANEL), 6)
        self.inset = NineSlice(assets.image(config.HUD_INSET), INSET_PAD)
        sheet = assets.image(config.HUD_BUTTON)
        self.buttons = {
            name: NineSlice(sheet.subsurface(pygame.Rect(i * 12, 0, 12, 12)), 4)
            for i, name in enumerate(config.BUTTON_STATES)
        }
        icons = assets.image(config.HUD_ICONS)
        c = config.ICON_CELL
        self.icons = {name: icons.subsurface(pygame.Rect(i * c, 0, c, c))
                      for i, name in enumerate(config.ICON_ORDER)}
        self.f8 = assets.pixel_font(1)
        self.f16 = assets.pixel_font(2)
        self.body = PixelFont(config.BODY_FONT_PATH, 1, upper=False)      # readable font for messages

    # ---- helpers -------------------------------------------------------------------------
    @staticmethod
    def _text(surf, font, text, color, pos, anchor="topleft", shadow=True, shadow_color=None) -> pygame.Rect:
        img = font.render(text, False, color)
        rect = img.get_rect(**{anchor: pos})
        if shadow:
            surf.blit(font.render(text, False, shadow_color or DARK), rect.move(1, 1))
        surf.blit(img, rect)
        return rect

    def wrap(self, text: str, width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split(" "):
                trial = f"{line} {word}".strip()
                if self.f8.size(trial)[0] <= width or not line:
                    line = trial
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def wrap_body(self, text: str, width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split(" "):
                trial = f"{line} {word}".strip()
                if self.body.size(trial)[0] <= width or not line:
                    line = trial
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def _draw_button(self, surf, rect: pygame.Rect, btn: HudButton, state: str) -> None:
        surf.blit(self.buttons[state].render(rect.size), rect.topleft)
        down = 1 if state == "pressed" else 0
        icon = self.icons.get(btn.icon)
        x = rect.x + 4
        if icon is not None:
            ic = icon if btn.enabled else self._dim_icon(btn.icon)
            surf.blit(ic, (x, rect.y + (rect.h - config.ICON_CELL) // 2 + down))
            x += config.ICON_CELL + 2
        color = BTN_TEXT if btn.enabled else DISABLED_TEXT
        self._text(surf, self.f8, btn.label, color, (x, rect.y + (rect.h - 8) // 2 + down),
                   shadow=btn.enabled, shadow_color=BTN_SHADOW)

    def _dim_icon(self, name: str) -> pygame.Surface:
        key = "dim:" + name
        img = self.assets._sprites.get(key)
        if img is None:
            img = self.icons[name].copy()
            img.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
            self.assets._sprites[key] = img
        return img

    # ---- button layout -----------------------------------------------------------------
    @staticmethod
    def button_rects(height: int, count: int) -> list[pygame.Rect]:
        t = TIERS[tier_for(height)]
        bh, gap = t["btn_h"], t["btn_gap"]
        total = count * bh + (count - 1) * gap
        top = height - t["bottom"] - total
        return [pygame.Rect(MARGIN, top + i * (bh + gap), W - 2 * MARGIN, bh) for i in range(count)]

    def hit_test(self, pos: tuple[int, int], height: int, count: int) -> int | None:
        for i, r in enumerate(self.button_rects(height, count)):
            if r.collidepoint(pos):
                return i
        return None

    # ---- desni panel ------------------------------------------------------------------------
    def render(self, data: HudData, height: int, hover: int | None = None,
               pressed: int | None = None) -> pygame.Surface:
        t = TIERS[tier_for(height)]
        surf = self.panel.render((W, height)).copy()
        y = t["top"]
        self._text(surf, self.f8, data.mode_title, TAN, (MARGIN, y))
        y += 11
        if t["big"]:
            if self.f16.size(data.heading)[0] <= W - 2 * MARGIN:        # the big title only if it fits the width
                self._text(surf, self.f16, data.heading, GOLD, (MARGIN, y))
            else:
                self._text(surf, self.f8, data.heading, GOLD, (MARGIN, y + 6))
            y += 21
        else:
            self._text(surf, self.f8, data.heading, GOLD, (MARGIN, y))
            y += 11
        if t["info"]:
            for line in data.info:
                self._text(surf, self.f8, line, CREAM, (MARGIN, y))
                y += 10
            y += 3
        else:
            y += 2

        # brojke
        row_h = t["row_h"]
        box = pygame.Rect(MARGIN, y, W - 2 * MARGIN, 3 * row_h + 2 * INSET_PAD)
        surf.blit(self.inset.render(box.size), box.topleft)
        rows = (("moves", "MOVES", data.moves), ("time", "TIME", data.time), ("score", "SCORE", data.score))
        for i, (icon, label, value) in enumerate(rows):
            ry = box.y + INSET_PAD + i * row_h
            icon_y = ry + (row_h - config.ICON_CELL) // 2
            surf.blit(self.icons[icon], (box.x + INSET_PAD, icon_y))
            text_y = ry + (row_h - 8) // 2 + (1 if row_h >= 12 else 0)
            self._text(surf, self.f8, label, TAN, (box.x + INSET_PAD + config.ICON_CELL + 2, text_y))
            self._text(surf, self.f8, value, CREAM, (box.right - INSET_PAD - 1, text_y), "topright")
        y = box.bottom + 4

        # buttons (from the bottom) and messages (everything in between)
        rects = self.button_rects(height, len(data.buttons))
        msg_bottom = (rects[0].y - 4) if rects else height - t["bottom"]
        if msg_bottom - y >= MSG_MIN:
            mbox = pygame.Rect(MARGIN, y, W - 2 * MARGIN, msg_bottom - y)
            surf.blit(self.inset.render(mbox.size), mbox.topleft)
            ty = mbox.y + INSET_PAD + 1
            inner_w = mbox.w - 2 * INSET_PAD - 2
            for text, color in data.messages:
                for line in self.wrap_body(text, inner_w):
                    if ty + 8 > mbox.bottom - INSET_PAD:
                        break
                    self._text(surf, self.body, line, color, (mbox.x + INSET_PAD + 1, ty), shadow=False)
                    ty += 9
                ty += 3
        for i, (rect, btn) in enumerate(zip(rects, data.buttons)):
            state = ("disabled" if not btn.enabled else "pressed" if pressed == i
                     else "hover" if hover == i else "normal")
            self._draw_button(surf, rect, btn, state)
        return surf

    # ---- win window ---------------------------------------------------------------------------
    def render_win(self, data: WinData, hover: int | None = None,
                   pressed: int | None = None) -> tuple[pygame.Surface, list[pygame.Rect]]:
        ww = self.WIN_WIDTH
        inner_w = ww - 2 * MARGIN
        note_lines = self.wrap(data.note, inner_w) if data.note else []
        rows_h = len(data.rows) * 10 + 2 * INSET_PAD + 2
        height = (MARGIN + 12 + rows_h + 4 + 12 + (len(note_lines) * 9 + 4 if note_lines else 0)
                  + len(data.buttons) * BTN_H + (len(data.buttons) - 1) * BTN_GAP + MARGIN)
        surf = self.panel.render((ww, height)).copy()
        y = MARGIN
        self._text(surf, self.f8, data.title, GOOD, (ww // 2, y), "midtop")
        y += 12
        box = pygame.Rect(MARGIN, y, inner_w, rows_h)
        surf.blit(self.inset.render(box.size), box.topleft)
        ry = box.y + INSET_PAD + 1
        for name, count, points in data.rows:
            self._text(surf, self.f8, name, TAN, (box.x + INSET_PAD + 1, ry))
            self._text(surf, self.f8, count, CREAM, (box.x + INSET_PAD + 98, ry), "topright")
            self._text(surf, self.f8, points, GOLD, (box.right - INSET_PAD - 1, ry), "topright")
            ry += 10
        y = box.bottom + 4
        self._text(surf, self.f8, data.total, GOLD, (ww // 2, y), "midtop")
        y += 12
        for line in note_lines:
            self._text(surf, self.f8, line, GOOD, (ww // 2, y), "midtop")
            y += 9
        if note_lines:
            y += 4
        rects = []
        for i, btn in enumerate(data.buttons):
            rect = pygame.Rect(MARGIN, y + i * (BTN_H + BTN_GAP), inner_w, BTN_H)
            rects.append(rect)
            state = ("disabled" if not btn.enabled else "pressed" if pressed == i
                     else "hover" if hover == i else "normal")
            self._draw_button(surf, rect, btn, state)
        return surf, rects

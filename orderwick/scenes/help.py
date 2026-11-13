"""Help / rules."""
from __future__ import annotations

import pygame

from ..engine.native_scene import NativeScene
from ..view.wood_kit import CREAM, GOLD, TAN
from .common import full_panel

SECTIONS = [
    ("Goal",
      "Sort the cards until every column holds one type only and the free slots are empty. "
      "You only see revealed cards. A ? card is revealed when you remove the card above it."),
    ("Moving",
      "Pick a source, then a target (mouse, or the keys under the columns and above the free slots). "
      "The top card, with the run of equal cards below it, moves to an empty column or onto a column "
      "whose top is the same type. A free slot holds one card. Slots marked ! are locked."),
    ("Scoring",
      "Level x 100, plus a bonus for few moves and a bonus for speed. Undo counts as a move."),
    ("Progress",
      "The campaign goes from easy to hard: more columns first, then fewer free slots, then taller "
      "columns, up to the 10 x 13 finale with one free slot. Hard mode starts at the finale. "
      "In a custom game you pick the size yourself."),
    ("Rescue (X)",
      "When you are stuck (or no solution is left) you get one more free slot, but drop one level. "
      "After you win that board, you return to the level you were on before the rescue."),
    ("Keys",
      "1-9, 0 columns   A S D F... free slots   Arrows + Enter   U undo ONE move   X rescue   "
      "R new board (-50)   Esc pause   Q end run   F11 full screen"),
]


class HelpScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.page = 0

    def _pages(self, width: int, height: int) -> list[list[tuple[str, list[str]]]]:
        """Sections wrapped to `width` and packed into pages that fit `height` (native px)."""
        kit = self.kit
        pages: list[list[tuple[str, list[str]]]] = [[]]
        used = 0
        for title, text in SECTIONS:
            lines = kit.wrap(text, width, body=True)
            need = 12 + len(lines) * 9 + 6
            if used and used + need > height:
                pages.append([])
                used = 0
            pages[-1].append((title, lines))
            used += need
        return pages

    def _box(self) -> pygame.Rect:
        nw, nh = self.native_size
        panel = full_panel(nw, nh)
        return pygame.Rect(panel.x + 8, 32, panel.w - 16, panel.bottom - 32 - 24)

    def _count(self) -> int:
        box = self._box()
        return len(self._pages(box.w - 14, box.h - 10))

    def _next(self) -> None:
        if self.page + 1 < self._count():
            self.page += 1
        else:
            self.app.scenes.pop()

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.scenes.pop()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_RIGHT):
                self._next()
            elif event.key == pygame.K_LEFT and self.page > 0:
                self.page -= 1
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._next()

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "Help", (nw // 2, 12), GOLD, "midtop", big=True)
        box = self._box()
        kit.draw_inset(canvas, box)
        pages = self._pages(box.w - 14, box.h - 10)
        self.page = min(self.page, len(pages) - 1)
        y = box.y + 7
        for title, lines in pages[self.page]:
            kit.text(canvas, title, (box.x + 7, y), GOLD)
            y += 12
            for line in lines:
                kit.text(canvas, line, (box.x + 7, y), CREAM, shadow=False, body=True)
                y += 9
            y += 6
        last = self.page + 1 == len(pages)
        kit.text(canvas, f"Page {self.page + 1}/{len(pages)}  Enter = {'close' if last else 'next'}  Esc = close",
                 (nw // 2, panel.bottom - 8), TAN, "midbottom", shadow=False)

"""Leaderboard (per mode)."""
from __future__ import annotations

import pygame

from .. import config
from ..core.scoring import format_time
from ..engine.native_scene import NativeScene
from ..view.colors import HIGHLIGHT
from ..view.wood_kit import CREAM, GOLD, TAN
from .common import full_panel

TABS = [("campaign", "Campaign"), ("hard", "Hard mode")]
CH = 8                                   # width of one font character


class LeaderboardScene(NativeScene):
    title = "Leaderboard"
    tabs = TABS                                 # the online screen reuses this scene with its own tabs and rows
    footer = "Left/right = mode   Esc = back"

    def __init__(self, app, mode_id: str = "campaign", highlight: int | None = None):
        super().__init__(app)
        self.tab = next((i for i, (m, _) in enumerate(self.tabs) if m == mode_id), 0)
        self.highlight = highlight if mode_id == self.tabs[self.tab][0] else None
        self.tab_rects: list[pygame.Rect] = []

    def entries(self) -> list[dict]:
        return self.app.leaderboard.top(self.tabs[self.tab][0])

    def empty_text(self) -> str:
        return "No scores yet. Be the first!"

    def subtitle(self) -> str:
        return ""

    def _switch(self, step: int) -> None:
        self.tab = (self.tab + step) % len(self.tabs)
        self.highlight = None

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.app.scenes.pop()
            elif event.key in (pygame.K_RIGHT, pygame.K_TAB):
                self._switch(1)
            elif event.key == pygame.K_LEFT:
                self._switch(-1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(event.pos) and i != self.tab:
                    self.tab = i
                    self.highlight = None

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, self.title, (nw // 2, 12), GOLD, "midtop", big=True)

        self.tab_rects = []
        tw = 84
        x = nw // 2 - (len(self.tabs) * (tw + 4) - 4) // 2
        for i, (_mode, title) in enumerate(self.tabs):
            r = pygame.Rect(x + i * (tw + 4), 30, tw, 16)
            self.tab_rects.append(r)
            kit.draw_button(canvas, r, title, "hover" if i == self.tab else "normal")

        top = 50
        if self.subtitle():                                     # e.g. the online filter: its own line, never over the title
            kit.text(canvas, self.subtitle(), (nw // 2, 49), TAN, "midtop", shadow=False)
            top = 60
        box = pygame.Rect(panel.x + 8, top, panel.w - 16, panel.bottom - top - 22)
        kit.draw_inset(canvas, box)
        rows_n = config.LEADERBOARD_SIZE
        row_h = max(9, min(11, (box.h - 8 - 14) // rows_n))
        entries = self.entries()
        # columns: width = the longest text (header or value); spacing is distributed over the free width
        table = [("#", "L", [str(i + 1) for i in range(len(entries))]),
                 ("NAME", "L", [e["name"] for e in entries]),
                 ("SCORE", "R", [str(e["score"]) for e in entries]),
                 ("LVL", "R", [str(e["level"]) for e in entries]),
                 ("TIME", "R", [format_time(e["time"]) for e in entries]),
                 ("MOVES", "R", [str(e["moves"]) for e in entries])]
        inner_w = box.w - 12

        def widths(cols):
            return [max(len(h), *(len(v) for v in vals), 1) * CH for h, _a, vals in cols]

        while len(table) > 3 and sum(widths(table)) + 4 * (len(table) - 1) > inner_w:
            table.pop()                                           # window too narrow: drop the last column
        ws = widths(table)
        free = max(0, inner_w - sum(ws))
        gaps = [free // (len(ws) - 1) + (1 if i < free % (len(ws) - 1) else 0) for i in range(len(ws) - 1)]
        xs, x = [], box.x + 6
        for i, w in enumerate(ws):
            xs.append(x)
            x += w + (gaps[i] if i < len(gaps) else 0)
        y = box.y + 5
        for (head, align, _v), x0, w in zip(table, xs, ws):
            kit.text(canvas, head, (x0 if align == "L" else x0 + w, y), TAN,
                     "topleft" if align == "L" else "topright", shadow=False)
        y += 12
        if not entries:
            kit.text(canvas, self.empty_text(), box.center, TAN, "center", shadow=False)
        for i, e in enumerate(entries):
            hl = self.highlight == i + 1
            if hl:
                canvas.fill(HIGHLIGHT, (box.x + 3, y - 1, box.w - 6, row_h))
            color = GOLD if hl else CREAM
            for (_h, align, vals), x0, w in zip(table, xs, ws):
                kit.text(canvas, vals[i], (x0 if align == "L" else x0 + w, y), color,
                         "topleft" if align == "L" else "topright", shadow=False)
            y += row_h
        kit.text(canvas, self.footer, (nw // 2, panel.bottom - 8), TAN,
                 "midbottom", shadow=False)

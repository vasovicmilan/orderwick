"""Daily challenges: today's three tasks, progress, the countdown to the next set and the streak."""
from __future__ import annotations

import time

import pygame

from ..core.challenges import TIER_NAMES
from ..core.daily_board import DailyBoardMode
from ..core.levels import HardMode
from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup
from ..view.wood_kit import CREAM, DISABLED, GOLD, GOOD, TAN
from .common import full_panel

ROW_H = 30
TIER_COLOURS = {1: GOOD, 2: GOLD, 3: (250, 120, 110)}


def seconds_to_midnight(now: time.struct_time | None = None) -> int:
    t = now or time.localtime()
    return 86400 - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec)


class DailyScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        app.daily.refresh()
        self._since = 0.0
        self.board_button = Button("Daily board", self._board)
        self.group = FocusGroup([self.board_button, Button("Play Campaign", self._campaign),
                                 Button("Play Hard mode", self._hard)])

    def _board(self) -> None:
        """Today's board (one per day, the same for everyone). Solved once = locked until tomorrow."""
        from .game import GameScene
        if not self.app.daily.board_open():
            return
        mode = DailyBoardMode(self.app.daily.state.date)
        self.app.scenes.replace(GameScene(self.app, self.app.new_session(mode)))

    # The tasks count while you play Campaign or Hard mode; these buttons just start a run from here.
    def _campaign(self) -> None:
        from .level_select import LevelSelectScene
        self.app.scenes.replace(LevelSelectScene(self.app))

    def _hard(self) -> None:
        from .game import GameScene
        self.app.scenes.replace(GameScene(self.app, self.app.new_session(HardMode())))

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.app.scenes.pop()
            return
        self.group.handle_event(event)

    def update(self, dt: float) -> None:
        self._since += dt
        if self._since >= 1.0:                           # the next day may start while this screen is open
            self._since = 0.0
            self.app.daily.refresh()

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        daily = self.app.daily
        state = daily.state
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "Daily challenges", (nw // 2, 12), GOLD, "midtop", big=True)
        left = seconds_to_midnight()
        kit.text(canvas, f"{state.date}   New in {left // 3600:02d}:{left % 3600 // 60:02d}:{left % 60:02d}",
                 (nw // 2, 29), TAN, "midtop", shadow=False)
        spare = max(0, panel.bottom - 40 - 22 - (3 * ROW_H + 6 + 36))          # tall windows: centre the block
        top = 40 + spare // 2
        box = pygame.Rect(panel.x + 8, top, panel.w - 16, min(3 * ROW_H + 6, panel.bottom - top - 22))
        kit.draw_inset(canvas, box)
        y = box.y + 4
        for ch in state.today:
            done = ch.id in state.done
            tag = TIER_NAMES[ch.tier]
            kit.text(canvas, tag, (box.x + 7, y + 2), TIER_COLOURS[ch.tier] if not done else DISABLED, shadow=False)
            label = "DONE" if done else f"{state.value(ch)}/{ch.target}"
            kit.text(canvas, label, (box.right - 8, y + 2), GOOD if done else TAN, "topright", shadow=False)
            lines = kit.wrap(ch.text, box.w - 16, body=True)[:2]
            for i, line in enumerate(lines):
                kit.text(canvas, line, (box.x + 7, y + 12 + i * 8), CREAM if not done else TAN, shadow=False, body=True)
            bar = pygame.Rect(box.x + 7, y + ROW_H - 7, box.w - 14, 4)
            canvas.fill((66, 57, 52), bar)
            frac = 1.0 if done else min(1.0, state.value(ch) / ch.target)
            if frac > 0:
                canvas.fill(GOOD if done else GOLD, pygame.Rect(bar.x, bar.y, max(1, int(bar.w * frac)), bar.h))
            y += ROW_H
        bw, bh = 120, 14
        solved = state.board_solved()
        self.board_button.enabled = not solved
        self.board_button.text = (f"Board solved  {state.board_score}" if solved else "Play today's board")
        by = box.bottom + 6
        self.group.widgets[0].rect = pygame.Rect(nw // 2 - bw - 2, by, 2 * bw + 4, bh)
        self.group.widgets[1].rect = pygame.Rect(nw // 2 - bw - 2, by + bh + 1, bw, bh)
        self.group.widgets[2].rect = pygame.Rect(nw // 2 + 2, by + bh + 1, bw, bh)
        self.group.draw(canvas, kit)
        streak = state.current_streak(state.date)
        kit.text(canvas, f"Streak {streak}  Best {state.best_streak}  Done {state.total_done}",
                 (panel.x + 10, panel.bottom - 8), TAN, "bottomleft", shadow=False)
        kit.text(canvas, "Esc = back", (panel.right - 10, panel.bottom - 8), TAN, "bottomright", shadow=False)

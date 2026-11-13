"""Custom game: choose width, free slots and cards per type."""
from __future__ import annotations

import pygame

from ..core.levels import CustomMode
from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup, Spinner
from ..view.wood_kit import GOLD, TAN
from .common import full_panel


class CustomScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.width = Spinner("Columns", 8, 5, 10, self._changed)
        self.free = Spinner("Free slots", 3, 1, 8, self._changed)
        self.height = Spinner("Cards per type", 6, 4, 12, self._changed)
        self.group = FocusGroup([
            self.width, self.free, self.height,
            Button("Start", self._start),
            Button("Back", self.app.scenes.pop),
        ])
        self._changed(0)

    def _changed(self, _value: int) -> None:
        self.free.set_range(1, self.width.value)

    def _start(self) -> None:
        from .game import GameScene
        mode = CustomMode(self.width.value, self.free.value, self.height.value)
        self.app.scenes.replace(GameScene(self.app, self.app.new_session(mode)))

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.scenes.pop()
            return
        self.group.handle_event(event)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "Custom game", (nw // 2, 13), GOLD, "midtop", big=True)
        self.group.layout_column(nw // 2, 38, min(240, nw - 40), 16, 3)
        self.group.draw(canvas, kit)
        cols, k = self.width.value, self.height.value
        last = self.group.widgets[-1].rect
        box = pygame.Rect(last.x, last.bottom + 6, last.w, 4 + 3 * 9 + 6)
        if box.bottom <= panel.bottom - 4:
            kit.draw_inset(canvas, box)
            lines = [f"Board {cols}x{k + 1} Types {cols - 1} Cards {(cols - 1) * k}",
                     "One column is always empty.", "Not on the leaderboard."]
            for i, line in enumerate(lines):
                kit.text(canvas, line, (box.x + 6, box.y + 6 + i * 9), TAN, shadow=False)

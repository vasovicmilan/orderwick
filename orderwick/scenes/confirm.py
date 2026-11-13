"""Confirmation (Yes / No) before an irreversible action, e.g. ending a run."""
from __future__ import annotations

from typing import Callable

import pygame

from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup
from ..view.wood_kit import GOLD, TAN
from .common import centered


class ConfirmScene(NativeScene):
    def __init__(self, app, question: str, detail: str, yes_text: str,
                 on_yes: Callable[[], None], no_text: str = "No, go back"):
        super().__init__(app)
        self.question = question
        self.detail = detail
        self.on_yes = on_yes
        self.group = FocusGroup([Button(no_text, self._no), Button(yes_text, self._yes)])

    def _no(self) -> None:
        self.app.scenes.pop()

    def _yes(self) -> None:
        self.app.scenes.pop()
        self.on_yes()

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._no()
            return
        self.group.handle_event(event)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = centered(nw, nh, 280, 110)
        kit.draw_panel(canvas, panel)
        cx, y = panel.centerx, panel.y + 10
        inner = panel.w - 24
        big = kit.width(self.question, True) <= inner
        kit.text(canvas, self.question, (cx, y), GOLD, "midtop", big=big)
        y += 22
        for line in kit.wrap(self.detail, inner, body=True):
            kit.text(canvas, line, (cx, y), TAN, "midtop", shadow=False, body=True)
            y += 9
        self.group.layout_column(cx, panel.bottom - 8 - 2 * 16 - 2, 128, 16, 2)
        self.group.draw(canvas, kit)

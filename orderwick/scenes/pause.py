"""Pause: time stops, the board is hidden."""
from __future__ import annotations

import pygame

from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup
from ..view.wood_kit import GOLD, TAN
from .common import centered


class PauseScene(NativeScene):
    def __init__(self, app, game_scene):
        super().__init__(app)
        self.game = game_scene
        self.group = FocusGroup([
            Button("Resume", self._resume),
            Button("Help", self._help),
            Button("End game", self._finish),
            Button("Quit game", self._quit_game),
        ])

    def _resume(self) -> None:
        self.app.scenes.pop()

    def _help(self) -> None:
        from .help import HelpScene
        self.app.scenes.push(HelpScene(self.app))

    def _finish(self) -> None:
        self.app.scenes.pop()          # back to the game, which then finishes the run
        self.game._finish()

    def _quit_game(self) -> None:
        from .confirm import ConfirmScene
        self.app.scenes.push(ConfirmScene(
            self.app, "Quit the game?", "Your score is saved.", "Yes, quit", self.app.quit))

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
            self._resume()
            return
        self.group.handle_event(event)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = centered(nw, nh, 184, 130)
        kit.draw_panel(canvas, panel)
        cx, y = panel.centerx, panel.y + 10
        kit.text(canvas, "Paused", (cx, y), GOLD, "midtop", big=True)
        s = self.game.session
        kit.text(canvas, f"Score {s.score}  {s.mode.short_title}", (cx, y + 20), TAN, "midtop", shadow=False)
        self.group.layout_column(cx, y + 34, 112, 16, 2)
        self.group.draw(canvas, kit)

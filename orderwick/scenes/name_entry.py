"""Name entry when a score makes the leaderboard."""
from __future__ import annotations

import pygame

from .. import config
from ..engine.native_scene import NativeScene
from ..view.wood_kit import CREAM, GOLD, TAN
from .common import centered

DEFAULT_NAME = "PLAYER"


class NameEntryScene(NativeScene):
    def __init__(self, app, session):
        super().__init__(app)
        self.session = session
        self.name = ""
        self.t = 0.0

    def _confirm(self) -> None:
        from .leaderboard import LeaderboardScene
        res = self.session.result()
        mode_id = self.session.mode.id
        rank = self.app.leaderboard.add(mode_id, self.name or DEFAULT_NAME, res)
        self.app.scenes.replace(LeaderboardScene(self.app, mode_id, highlight=rank))

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._confirm()
        elif event.key == pygame.K_ESCAPE:
            self.app.scenes.pop()
        elif event.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.name) < config.NAME_MAX_LEN:
            self.name += event.unicode

    def update(self, dt: float) -> None:
        self.t += dt

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        res = self.session.result()
        panel = centered(nw, nh, 260, 108)
        kit.draw_panel(canvas, panel)
        cx, y = panel.centerx, panel.y + 10
        kit.text(canvas, "High score!", (cx, y), GOLD, "midtop", big=True)
        kit.text(canvas, f"Score {res['score']}   Level {res['level']}", (cx, y + 22), CREAM, "midtop")
        kit.text(canvas, "Type your name, Enter to save", (cx, y + 36), TAN, "midtop", shadow=False)
        box = pygame.Rect(0, 0, 124, 18)
        box.midtop = (cx, y + 50)
        kit.draw_inset(canvas, box)
        cursor = "_" if int(self.t * 2) % 2 == 0 else " "
        kit.text(canvas, self.name + cursor, (box.x + 6, box.y + 5), CREAM, shadow=False)
        kit.text(canvas, "Esc = skip", (cx, panel.bottom - 8), TAN, "midbottom", shadow=False)

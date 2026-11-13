"""Campaign: pick the level to start from."""
from __future__ import annotations

import pygame

from ..core.levels import CampaignMode, LevelCatalog
from ..engine.native_scene import NativeScene
from ..view.wood_kit import BAD, CREAM, GOLD, TAN
from .common import full_panel

PER_ROW = 5
TILE_W, GAP = 52, 4


class LevelSelectScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.selected = 0
        self.hover: int | None = None
        self.rects: list[pygame.Rect] = []
        self.tile_h = 42

    def _start(self, index: int) -> None:
        from .game import GameScene
        session = self.app.new_session(CampaignMode(index + 1))
        self.app.scenes.replace(GameScene(self.app, session))

    def _layout(self) -> None:
        nw, nh = self.native_size
        n = LevelCatalog.count()
        rows = (n + PER_ROW - 1) // PER_ROW
        self.tile_h = max(30, min(46, (nh - 12 - 44 - 22 - GAP * (rows - 1)) // rows))
        total_w = PER_ROW * TILE_W + (PER_ROW - 1) * GAP
        x0, y0 = (nw - total_w) // 2, 46
        self.rects = [pygame.Rect(x0 + (i % PER_ROW) * (TILE_W + GAP), y0 + (i // PER_ROW) * (self.tile_h + GAP),
                                  TILE_W, self.tile_h) for i in range(n)]

    def on_event(self, event: pygame.event.Event) -> None:
        self._layout()
        n = LevelCatalog.count()
        if event.type == pygame.MOUSEMOTION:
            self.hover = next((i for i, r in enumerate(self.rects) if r.collidepoint(event.pos)), None)
            if self.hover is not None:
                self.selected = self.hover
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(event.pos):
                    self._start(i)
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.scenes.pop()
            elif event.key == pygame.K_RIGHT:
                self.selected = (self.selected + 1) % n
            elif event.key == pygame.K_LEFT:
                self.selected = (self.selected - 1) % n
            elif event.key == pygame.K_DOWN:
                self.selected = min(n - 1, self.selected + PER_ROW)
            elif event.key == pygame.K_UP:
                self.selected = max(0, self.selected - PER_ROW)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._start(self.selected)

    def paint(self, canvas: pygame.Surface) -> None:
        self._layout()
        nw, nh = self.native_size
        kit = self.kit
        kit.draw_panel(canvas, full_panel(nw, nh))
        kit.text(canvas, "Campaign", (nw // 2, 13), GOLD, "midtop", big=True)
        kit.text(canvas, "Pick a level, easy to hard", (nw // 2, 32), TAN, "midtop", shadow=False)
        best = self.app.leaderboard.data["stats"]["best_level"]
        from ..core.levels import LevelCatalog as LC
        for i, r in enumerate(self.rects):
            spec = LC.spec(i + 1)
            focused = i == self.selected
            canvas.blit(kit.buttons["hover" if focused else "normal"].render(r.size), r.topleft)
            final = i + 1 == LC.final_level()
            kit.text(canvas, str(i + 1), (r.centerx, r.y + 5), GOLD if focused else (BAD if final else CREAM),
                     "midtop", big=True)
            kit.text(canvas, f"{spec.cols}x{spec.rows}", (r.centerx, r.y + 23), CREAM, "midtop", shadow=False)
            if self.tile_h >= 44:
                kit.text(canvas, f"FREE {spec.free}", (r.centerx, r.y + 32), TAN, "midtop", shadow=False)
            if best and i + 1 == best:
                canvas.blit(kit.icons["score"], (r.right - 15, r.y + 4))
        kit.text(canvas, "Enter or click = start   Esc = back", (nw // 2, nh - 15), TAN, "midbottom",
                 shadow=False)

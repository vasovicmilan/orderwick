"""Main menu."""
from __future__ import annotations

import random

import pygame

from .. import config
from ..core.levels import HardMode
from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup
from ..view.wood_kit import GOLD, TAN, CardTicker
from .common import centered

BTN_W, BTN_H, BTN_GAP = 156, 14, 1
TICKER_W = 176            # width of the card strip frame (native px)


class MenuScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.daily_button = Button("Daily", self._daily, icon="trophy")
        self.online_button = Button("Online", self._online, icon="score")
        self.group = FocusGroup([
            Button("Campaign", self._campaign),
            Button("Hard mode", self._hard),
            self.daily_button,
            Button("Custom game", self._custom),
            Button("Trophies", self._trophies, icon="trophy"),
            Button("Leaderboard", self._leaderboard, icon="score"),
            self.online_button,
            Button("Settings", self._settings),
            Button("Help", self._help),
            Button("About", self._about),
            Button("Quit", app.quit),
        ])
        names = [n for members in config.CARD_FAMILIES.values() for n in members]
        self.ticker = CardTicker(names, TICKER_W, random.Random())

    # ---- actions ----------------------------------------------------------------
    def _campaign(self) -> None:
        from .level_select import LevelSelectScene
        self.app.scenes.push(LevelSelectScene(self.app))

    def _hard(self) -> None:
        from .game import GameScene
        self.app.scenes.push(GameScene(self.app, self.app.new_session(HardMode())))

    def _custom(self) -> None:
        from .custom import CustomScene
        self.app.scenes.push(CustomScene(self.app))

    def _daily(self) -> None:
        from .daily import DailyScene
        self.app.scenes.push(DailyScene(self.app))

    def _trophies(self) -> None:
        from .achievements import AchievementsScene
        self.app.scenes.push(AchievementsScene(self.app))

    def _settings(self) -> None:
        from .settings import SettingsScene
        self.app.scenes.push(SettingsScene(self.app))

    def _about(self) -> None:
        from .about import AboutScene
        self.app.scenes.push(AboutScene(self.app))

    def _leaderboard(self) -> None:
        from .leaderboard import LeaderboardScene
        self.app.scenes.push(LeaderboardScene(self.app))

    def _online(self) -> None:
        from .online import OnlineScene
        self.app.scenes.push(OnlineScene(self.app))

    def _help(self) -> None:
        from .help import HelpScene
        self.app.scenes.push(HelpScene(self.app))

    # ---- scene ------------------------------------------------------------------
    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
            return
        self.group.handle_event(event)

    def update(self, dt: float) -> None:
        self.ticker.update(dt)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = centered(nw, nh, 200, 222)
        kit.draw_panel(canvas, panel)
        cx, y = panel.centerx, panel.y + 9
        kit.text(canvas, config.APP_NAME, (cx, y), GOLD, "midtop", big=True)
        strip = pygame.Rect(0, 0, TICKER_W, config.CELL + 6)
        strip.center = (cx, y + 31)
        self.ticker.draw(canvas, self.app.assets, strip, self.app.progress.collection.unlocked,
                         frame_color=kit.frame_color)
        self.online_button.text = "Online  ON" if self.app.online.enabled else "Online"
        done = self.app.daily.done_count()
        self.daily_button.text = "Daily  DONE" if done >= 3 else f"Daily  {done}/3"
        self.group.layout_column(cx, strip.bottom + 6, BTN_W, BTN_H, BTN_GAP)
        w = self.group.widgets                                      # last four share two rows: Settings|Help, About|Quit
        half = (BTN_W - BTN_GAP) // 2
        left = cx - BTN_W // 2
        row_a, row_b = w[-4].rect.y, w[-3].rect.y
        for widget, x, row in ((w[-4], left, row_a), (w[-3], left + half + BTN_GAP, row_a),
                               (w[-2], left, row_b), (w[-1], left + half + BTN_GAP, row_b)):
            widget.rect = pygame.Rect(x, row, half, BTN_H)
        self.group.draw(canvas, kit)
        stats = self.app.leaderboard.data["stats"]
        if stats["games"] and panel.bottom - 17 >= self.group.widgets[-1].rect.bottom + 1:
            kit.text(canvas, f"Best level {stats['best_level']}  Games {stats['games']}",
                     (cx, panel.bottom - 9), TAN, "midbottom", shadow=False)

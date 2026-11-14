"""The Season: a limited-time event with its own leaderboard and prizes (hardest board, no rescue, as far as you get)."""
from __future__ import annotations

import time

import pygame

from ..core.levels import SeasonMode
from ..engine.native_scene import NativeScene
from ..engine.tasks import BackgroundTask
from ..engine.ui import Button, FocusGroup
from ..online.client import OnlineError
from ..view.wood_kit import CREAM, GOLD, GOOD, TAN
from .common import full_panel


def format_left(seconds: int) -> str:
    days, rest = divmod(max(0, seconds), 86400)
    hours, rest = divmod(rest, 3600)
    return f"{days}d {hours:02d}h {rest // 60:02d}m" if days else f"{hours:02d}h {rest // 60:02d}m {rest % 60:02d}s"


def prize_line(prize: dict) -> str:
    first, last = prize["rankFrom"], prize["rankTo"]
    rank = f"#{first}" if first == last else f"#{first}-{last}"
    parts = []
    coins = prize.get("coins") or {}
    if coins.get("from") or coins.get("to"):
        parts.append(f"{coins['from']} coins" if coins["from"] == coins["to"] else f"{coins['from']}>{coins['to']} coins")
    parts += [i["name"] for i in prize.get("items", [])]
    return f"{rank}  {', '.join(parts)}"


class SeasonScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.info: dict | None = None
        self.board: list[dict] = []
        self.error = ""
        self.task: BackgroundTask | None = None
        self.fetched_at = time.monotonic()
        self.reward_shown = False
        self.play_button = Button("Play the Season", self._play)
        self.board_button = Button("Season leaderboard", self._board)
        self.group = FocusGroup([self.play_button, self.board_button])
        self._fetch()

    def _fetch(self) -> None:
        def work():
            info = self.app.online.season_info()
            rows = []
            if info.get("active"):
                try:
                    rows = self.app.online.client.leaderboard("season", "human")["entries"][:8]
                except OnlineError:
                    rows = []
            return info, rows
        self.task = BackgroundTask(work)

    def on_resume(self) -> None:                      # back from a run: the rank may have changed
        self.app.content.sync_async()
        self._fetch()

    def _play(self) -> None:
        from .game import GameScene
        if self.info and self.info.get("active") and self.app.online.enabled:
            self.app.scenes.push(GameScene(self.app, self.app.new_session(SeasonMode())))

    def _board(self) -> None:
        from .online_leaderboard import OnlineLeaderboardScene
        self.app.scenes.push(OnlineLeaderboardScene(self.app, "season"))

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self._close()
            return
        if self.info and self.info.get("rewards") and not self.reward_shown:
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.reward_shown = True
                self.app.online.season_rewards_seen()
                self.app.events.emit("server_items")        # the prizes may include a theme, an avatar or a song: fetch them now
            return
        self.group.handle_event(event)

    def _close(self) -> None:
        if self.info and self.info.get("rewards") and not self.reward_shown:
            self.app.online.season_rewards_seen()
        self.app.scenes.pop()

    def update(self, dt: float) -> None:
        if self.task is not None and self.task.done:
            task, self.task = self.task, None
            if task.error is not None:
                self.error = task.error.message if isinstance(task.error, OnlineError) else "Something went wrong."
            else:
                self.info, self.board = task.result
                self.error = ""
                self.fetched_at = time.monotonic()
                self.reward_shown = not self.info.get("rewards")

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        popup = bool(self.info and self.info.get("rewards") and not self.reward_shown)
        if not popup:
            kit.text(canvas, "Season", (nw // 2, 12), GOLD, "midtop", big=True)
        kit.text(canvas, "Esc = back", (panel.right - 10, panel.bottom - 8), TAN, "bottomright", shadow=False)
        info = self.info
        if info is None:
            kit.text(canvas, self.error or "Loading...", (nw // 2, nh // 2), TAN, "center", shadow=False)
            return
        if info.get("rewards") and not self.reward_shown:
            self._paint_rewards(canvas, panel, info["rewards"])
            return
        active = info.get("active")
        nxt = info.get("upcoming")
        if not active:
            text = (f"{nxt['name']} starts soon." if nxt else "No season is running right now.")
            kit.text(canvas, text, (nw // 2, nh // 2 - 8), CREAM, "center", shadow=False)
            kit.text(canvas, "Check back later: prizes are waiting for the best players.", (nw // 2, nh // 2 + 6), TAN, "center", shadow=False)
            self.play_button.enabled = False
            return
        kit.text(canvas, active["name"], (nw // 2, 29), CREAM, "midtop", shadow=False)
        left = max(0, active["remainingSeconds"] - int(time.monotonic() - self.fetched_at))
        kit.text(canvas, f"Ends in {format_left(left)}", (nw // 2, 39), TAN, "midtop", shadow=False)
        me = active.get("me")
        line = f"Your best {me['best']}  Rank #{me['rank']}" if me else "No score yet. Play to get on the board."
        kit.text(canvas, line, (nw // 2, 49), GOOD if me else TAN, "midtop", shadow=False)
        top = 62
        box = pygame.Rect(panel.x + 8, top, panel.w - 16, max(40, panel.bottom - top - 54))
        kit.draw_inset(canvas, box)
        y = box.y + 4
        kit.text(canvas, "Prizes", (box.x + 6, y), GOLD, shadow=False)
        y += 10
        for prize in active["prizes"]:
            if y > box.bottom - 18:
                break
            kit.text(canvas, prize_line(prize)[:46], (box.x + 6, y), CREAM, shadow=False, body=True)
            y += 8
        y += 3
        kit.text(canvas, "Top players", (box.x + 6, y), GOLD, shadow=False)
        y += 10
        for i, row in enumerate(self.board):
            if y > box.bottom - 8:
                break
            kit.text(canvas, f"{i + 1}. {row['name']}", (box.x + 6, y), CREAM, shadow=False, body=True)
            kit.text(canvas, str(row["score"]), (box.right - 6, y), TAN, "topright", shadow=False, body=True)
            y += 8
        bw, bh = 120, 14
        self.play_button.enabled = self.app.online.enabled
        self.play_button.text = "Play the Season" if self.app.online.enabled else "Turn on Online to play"
        self.play_button.rect = pygame.Rect(nw // 2 - bw - 2, box.bottom + 5, 2 * bw + 4, bh)
        self.board_button.rect = pygame.Rect(nw // 2 - bw - 2, box.bottom + 6 + bh, 2 * bw + 4, bh)
        self.group.draw(canvas, kit)

    def _paint_rewards(self, canvas, panel, rewards) -> None:
        nw, _ = self.native_size
        kit = self.kit
        y = 24
        kit.text(canvas, "Season prizes!", (nw // 2, y), GOLD, "midtop", big=True)
        y += 20
        for reward in rewards:
            kit.text(canvas, f"{reward['season']['name']}: you finished #{reward['rank']}", (nw // 2, y), CREAM, "midtop", shadow=False)
            y += 11
            if reward["coins"]:
                kit.text(canvas, f"+{reward['coins']} coins", (nw // 2, y), GOOD, "midtop", shadow=False)
                y += 10
            for item in reward["items"]:
                kit.text(canvas, f"New: {item['name']}", (nw // 2, y), GOOD, "midtop", shadow=False)
                y += 10
            y += 6
        kit.text(canvas, "Press any key", (nw // 2, panel.bottom - 22), TAN, "midbottom", shadow=False)

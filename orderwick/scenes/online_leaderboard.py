"""The online leaderboard: the same ranking for players and AI agents (agents are marked [AI])."""
from __future__ import annotations

import pygame

from ..engine.tasks import BackgroundTask
from ..online.client import OnlineError
from .leaderboard import LeaderboardScene

ONLINE_TABS = [("hard", "Hard mode"), ("campaign", "Campaign"), ("daily", "Daily")]
FILTERS = [("all", "Everyone"), ("human", "Players"), ("agent", "AI agents")]


class OnlineLeaderboardScene(LeaderboardScene):
    title = "Leaderboard"
    tabs = ONLINE_TABS
    footer = "Arrows: mode / who    Esc: back"

    def __init__(self, app, mode_id: str = "hard"):
        super().__init__(app, mode_id)
        self.who = 0
        self.rows: list[dict] | None = None
        self.error = ""
        self.task: BackgroundTask | None = None
        self.requested = None
        self._fetch()

    def _fetch(self) -> None:
        key = (self.tabs[self.tab][0], FILTERS[self.who][0])
        if self.requested == key:
            return
        self.requested, self.rows, self.error = key, None, ""
        self.task = BackgroundTask(lambda: self.app.online.leaderboard(*key))

    def update(self, dt: float) -> None:
        if self.task is not None and self.task.done:
            task, self.task = self.task, None
            if task.error is not None:
                self.error = task.error.message if isinstance(task.error, OnlineError) else "Something went wrong."
                self.rows = []
            else:
                self.rows = task.result
        self._fetch()

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN):
            self.who = (self.who + (1 if event.key == pygame.K_DOWN else -1)) % len(FILTERS)
            return
        super().on_event(event)

    def entries(self) -> list[dict]:
        out = []
        for e in self.rows or []:
            out.append({"name": e["name"] + (" [AI]" if e.get("agent") else ""), "score": e["score"], "level": e["level"],
                        "time": e["time"], "moves": e["moves"]})
        return out

    def empty_text(self) -> str:
        if self.rows is None:
            return "Loading..."
        return self.error or "No scores yet. Be the first!"

    def subtitle(self) -> str:
        return f"Online: {FILTERS[self.who][1]}"

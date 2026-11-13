"""Daily challenges at run time: draws the day's tasks, follows game events and saves to daily.json.

Only ranked modes (Campaign, Hard) count; Custom games do not. Completing tasks feeds the trophies
(daily_done, daily_full, daily_streak) through `Progress`.
"""
from __future__ import annotations

import time

from ..core.challenges import DailyState
from .storage import JsonStore


def today_string() -> str:
    return time.strftime("%Y-%m-%d")


class DailyChallenges:
    def __init__(self, events, progress, store: JsonStore | None = None, today=today_string):
        self.events = events
        self.progress = progress
        self.store = store or JsonStore("daily.json")
        self._today = today
        self.state = DailyState(self.store.load({}))
        self._seen_columns: dict[int, set[int]] = {}      # id(round) -> kinds already counted as completed
        self._seen_reveals: dict[int, dict[int, int]] = {}
        self._undo = False
        self._ranked = True                                # of the board being played (the chain event carries no session)
        self.refresh()
        for name, handler in (("move", self._on_move), ("round_won", self._on_won), ("chain", self._on_chain),
                              ("rescue", self._on_rescue), ("undo", self._on_undo),
                              ("round_started", self._on_started)):
            events.subscribe(name, handler)

    # ---- day handling -----------------------------------------------------------------------------
    def refresh(self) -> bool:
        """Call before showing / counting: starts a new day when the date changed."""
        new = self.state.ensure_today(self._today(), self.progress.collection.unlocked)
        if new:
            self.save()
        return new

    def save(self) -> None:
        self.store.save(self.state.to_dict())

    def board_open(self) -> bool:
        """Can today's daily board be played (not solved yet)?"""
        self.refresh()
        return not self.state.board_solved()

    def done_count(self) -> int:
        return len(self.state.done)

    # ---- recording ----------------------------------------------------------------------------------
    def _record(self, metric: str, amount: int = 1, card: str = "", value: int = 0) -> None:
        self.refresh()
        finished = self.state.record(metric, amount, card, value)
        for ch in finished:
            self.events.emit("challenge_done", id=ch.id, text=ch.text, done=len(self.state.done))
        if finished:
            self._sync_trophies()
            self.save()

    def _sync_trophies(self) -> None:
        t = self.progress.tracker
        t.at_least("daily_done", self.state.total_done)
        t.at_least("daily_full", self.state.full_days)
        t.at_least("daily_streak", self.state.best_streak)
        self.progress.refresh_trophies()

    @staticmethod
    def _counts(session) -> bool:
        return session is not None and (session.mode.ranked or session.mode.id == "daily")

    # ---- events ------------------------------------------------------------------------------------------
    def _on_started(self, session=None, **_):
        self._ranked = bool(session is None or session.mode.ranked)
        self._seen_columns.clear()
        self._seen_reveals.clear()
        self._undo = False

    def _on_undo(self, **_):
        self._undo = True

    def _on_move(self, session=None, round=None, revealed=(), paired=False, completed=0, **_):
        if not self._counts(session) or round is None:
            return
        self._record("moves")
        if paired:
            self._record("pairs")
        seen = self._seen_columns.setdefault(id(round), set())
        board = round.board
        for i in range(board.n_cols):                              # newly completed columns (once per card type per board)
            if board.is_complete(i):
                kind = board.columns[i][0].kind
                if kind not in seen:
                    seen.add(kind)
                    self._record("cols", 1, round.palette[kind])
        given = self._seen_reveals.setdefault(id(round), {})
        for kind in revealed:                                       # at most k per type per board (no undo farming)
            if given.get(kind, 0) < round.spec.k:
                given[kind] = given.get(kind, 0) + 1
                self._record("reveal", 1, round.palette[kind])

    def _on_won(self, session=None, round=None, **_):
        if not self._counts(session) or round is None:
            return
        if session.mode.id == "daily" and not self.state.board_solved():
            self.refresh()
            self.state.solve_board(int(session.score), int(round.moves), float(round.elapsed))
            self.save()
            self.events.emit("daily_board_solved", score=int(session.score))
        self._record("boards")
        if session.mode.id == "hard":
            self._record("win_hard")
        if not self._undo:
            self._record("win_clean")
        if round.rescued:
            self._record("win_rescued")
        self._record("win_fast", 1, value=int(round.elapsed))
        self._record("win_wide", 1, value=round.spec.cols)
        if session.mode.id == "campaign":
            self._record("win_level", 1, value=round.level)
        self._record("score", value=int(session.score))
        self._undo = False

    def _on_chain(self, length=0, **_):
        if self._ranked:
            self._record("chain", value=int(length))

    def _on_rescue(self, session=None, **_):
        if self._counts(session):
            self._record("rescues")

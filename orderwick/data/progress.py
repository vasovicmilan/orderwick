"""Player progress: card collection + achievements. Follows game events (EventBus) and saves to JSON."""
from __future__ import annotations

import time

from .. import config
from ..core.achievements import BY_ID, FAST_SECONDS, MIN_SKILL_LEVEL, AchievementTracker
from ..core import cosmetics
from ..core.collection import Collection
from ..core.levels import LevelCatalog
from .storage import JsonStore


class Progress:
    def __init__(self, events, store: JsonStore | None = None):
        self.events = events
        self.store = store or JsonStore("progress.json")
        data = self.store.load({"collection": {}, "tracker": {}, "cosmetics": []})
        self.collection = Collection(data["collection"])
        self.tracker = AchievementTracker(data["tracker"])
        self.cosmetics_seen: set[str] = set(data["cosmetics"])          # "board:emerald" ... already announced
        self._play_seconds = float(data.get("play_seconds", 0.0))
        self._revealed: dict[int, dict[int, int]] = {}
        self._cols_given: dict[int, int] = {}      # id(board) -> columns already counted
        if config.DEV:
            self._unlock_everything()
        self._sync_collection_stats()
        events.subscribe("move", self._on_move)
        events.subscribe("undo", self._on_undo)
        events.subscribe("rescue", self._on_rescue)
        events.subscribe("round_won", self._on_won)
        events.subscribe("run_finished", self._on_run_finished)
        events.subscribe("round_started", self._on_started)
        events.subscribe("chain", self._on_chain)
        events.subscribe("server_progress", self._on_server_progress)
        self._undo_flag = False

    def _unlock_everything(self) -> None:
        """Developer mode only: every card, premium card, trophy and look is available (nothing here is a cheat for players)."""
        from ..core.achievements import ACHIEVEMENTS
        for family in config.CARD_FAMILIES:
            self.collection.add_points(family, 10 ** 9)
        for card in config.PREMIUM_CARDS:
            self.collection.grant(card)
        today = time.strftime("%Y-%m-%d")
        for a in ACHIEVEMENTS:
            self.tracker.unlocked.setdefault(a.id, today)

    # ---- helpers ---------------------------------------------------------------------
    def save(self) -> None:
        self.store.save({"version": 1, "collection": self.collection.to_dict(), "tracker": self.tracker.to_dict(),
                         "play_seconds": self._play_seconds,
                         "cosmetics": sorted(self.cosmetics_seen)})

    def _sync_collection_stats(self) -> None:
        unlocked = self.collection.unlocked
        regular = unlocked - self.collection.granted
        self.tracker.at_least("new_cards", len(regular) - len(config.CARD_FAMILIES))
        done = sum(1 for names in config.CARD_FAMILIES.values()
                   if len(names) > 1 and all(n in unlocked for n in names))
        self.tracker.at_least("families_done", done)

    def _add_points(self, family: str, amount: int) -> None:
        for name in self.collection.add_points(family, amount):
            self.events.emit("card_unlocked", name=name, family=family)
        self._sync_collection_stats()

    def _on_server_progress(self, progress=None, **_) -> None:
        """The server counts achievements from the boards it verified; its answer replaces the local state of every
        achievement it knows. Trophies the server has no entry for (and the card collection) stay local."""
        items = (progress or {}).get("achievements") or []
        if not items:
            return
        today = time.strftime("%Y-%m-%d")
        for item in items:
            code = item["code"]
            if item.get("unlocked"):
                if code not in self.tracker.unlocked:
                    self.tracker.unlocked[code] = (item.get("unlockedAt") or today)[:10]
                    if code in BY_ID:
                        self.events.emit("achievement_unlocked", id=code)
            else:
                self.tracker.unlocked.pop(code, None)
        self.save()

    def grant_server_cards(self, names) -> None:
        """Cards the player owns on the server join the collection like any other premium card."""
        changed = False
        for name in names:
            if self.collection.grant(name):
                changed = True
                self.events.emit("card_unlocked", name=name, family="premium")
        if changed:
            self.save()

    def refresh_trophies(self) -> None:
        """Checks trophies after something outside the board changed the counters (e.g. a daily challenge)."""
        self._finish_event()

    def _finish_event(self) -> None:
        for a in self.tracker.check(time.strftime("%Y-%m-%d")):
            self.events.emit("achievement_unlocked", id=a.id)
            for card, ach_id in config.PREMIUM_CARDS.items():       # reward: premium card
                if ach_id == a.id and self.collection.grant(card):
                    self.events.emit("card_unlocked", name=card, family="premium")
        for kind in (cosmetics.BOARD, cosmetics.CARDS):                 # new board themes / card styles
            for look in cosmetics.looks(kind):
                key = f"{kind}:{look.id}"
                if key not in self.cosmetics_seen and look.rule and cosmetics.is_unlocked(look.rule, self.tracker.unlocked):
                    self.cosmetics_seen.add(key)
                    self.events.emit("cosmetic_unlocked", kind=kind, id=look.id, name=look.name)
        self.save()

    # ---- events ----------------------------------------------------------------------
    def _on_move(self, round=None, revealed=(), completed=0, **_):
        if completed and round is not None:
            room = max(0, round.board.n_cols - 1 - self._cols_given.get(id(round), 0))      # at most one column per type per board
            counted = min(completed, room)
            self._cols_given[id(round)] = self._cols_given.get(id(round), 0) + counted
            if counted:
                self.tracker.bump("columns_done", counted)
        if round is None or not revealed:
            if completed:
                self._finish_event()
            return
        given = self._revealed.setdefault(id(round), {})
        for kind in revealed:
            if given.get(kind, 0) >= round.spec.k:               # no more than k per type: no "farming" with undo
                continue
            given[kind] = given.get(kind, 0) + 1
            self.tracker.bump("cards_revealed")
            self._add_points(self._family(round, kind), config.POINTS_PER_REVEAL)
        self._finish_event()

    def _on_chain(self, length=0, **_):
        if length > self.tracker.stats["best_chain"]:
            self.tracker.at_least("best_chain", length)
            self._finish_event()

    def _on_started(self, **_):
        self._undo_flag = False
        self._revealed.clear()                                 # old boards are no longer needed (no leak)
        self._cols_given.clear()

    def _on_undo(self, **_):
        self._undo_flag = True

    def _on_rescue(self, **_):
        self.tracker.bump("rescues")
        self._finish_event()

    def _on_won(self, round=None, session=None, **_):
        if round is None or session is None:
            return
        for kind in range(len(round.palette)):
            self._add_points(self._family(round, kind), config.POINTS_PER_SET)
        t = self.tracker
        t.bump("boards_won")
        if session.mode.id == "hard":
            t.bump("hard_wins")
        if session.mode.ranked and session.mode.id == "campaign":
            t.at_least("best_level", round.level)
            if round.level >= LevelCatalog.final_level():
                t.bump("campaign_clears")
        skilled = round.level >= MIN_SKILL_LEVEL if session.mode.ranked else round.spec.cols >= 8
        if round.rescued:
            t.bump("rescued_wins")
        if skilled and not getattr(self, "_undo_flag", False):
            t.bump("clean_wins")
        if skilled and round.elapsed < FAST_SECONDS:
            t.bump("fast_wins")
        self._undo_flag = False
        t.at_least("best_score", session.score)
        self._finish_event()

    def _on_run_finished(self, session=None, **_):
        self.tracker.bump("runs")
        if session is not None:
            self.tracker.bump("total_points", session.score)
            self._play_seconds += session.total_time
            minutes = int(self._play_seconds // 60)
            self._play_seconds -= minutes * 60
            self.tracker.bump("play_minutes", minutes)
        self._finish_event()

    @staticmethod
    def _family(round, kind: int) -> str:
        return Collection.family_of(round.palette[kind]) or ""

    # ---- looks -----------------------------------------------------------------------------
    def look_unlocked(self, kind: str, look_id: str) -> bool:
        return any(look.id == look_id and cosmetics.is_unlocked(look.rule, self.tracker.unlocked)
                   for look in cosmetics.looks(kind))

"""Daily challenges: the catalogue (100+ tasks), the daily pick and the per-day progress. No pygame dependency.

* `CATALOGUE` is built from templates, so it is easy to extend (add a metric or a target and it just appears).
* `pick_daily(date, unlocked)` is deterministic for a calendar day (same date -> same three tasks, on every
  device), one EASY + one MEDIUM + one HARD task, never two of the same kind, and only tasks that are possible with
  the cards the player has already unlocked.
* `DailyState` holds today's three tasks and their progress; when the date changes it draws a new set.

Metrics (what is counted; only ranked modes - Campaign and Hard - count, Custom games do not):
  cols      completed columns            (optionally of a colour / a card type / one exact card)
  reveal    revealed hidden cards        (same filters)
  pairs     cards placed onto a card of the same type
  moves     moves made
  boards    boards solved
  win_hard  boards solved in Hard mode
  win_clean boards solved without using undo
  win_fast  boards solved in at most `param` seconds
  win_wide  boards solved that are at least `param` columns wide
  win_level campaign boards solved on level `param` or higher
  rescues   rescues used            win_rescued  boards solved after a rescue
  chain     longest quick pairing chain today (a best value, not a sum)
  score     highest run score today (a best value, not a sum)
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from .. import config

EASY, MEDIUM, HARD = 1, 2, 3
TIER_NAMES = {EASY: "EASY", MEDIUM: "MEDIUM", HARD: "HARD"}
PER_DAY = 3
BEST_METRICS = {"chain", "score"}                      # progress = the best value reached, not a running sum
THRESHOLD_METRICS = {"win_fast": "max", "win_wide": "min", "win_level": "min"}   # event value vs `param`

COLOURS = ["red", "green", "blue", "yellow", "purple", "orange", "white", "brown", "tan"]


def colour_of(card: str) -> str:
    return card.split("_", 1)[0]


def type_of(card: str) -> str:
    return card.split("_", 1)[1] if "_" in card else card


def _all_cards() -> list[str]:
    return [n for names in config.CARD_FAMILIES.values() for n in names]


def card_label(card: str) -> str:
    return card.replace("_", " ")


@dataclass(frozen=True)
class Challenge:
    id: str
    metric: str
    target: int
    tier: int
    text: str
    filt: str = ""                  # "", "colour", "type" or "card"
    value: str = ""                 # the colour / type / card name for `filt`
    param: int = 0                  # threshold for win_fast / win_wide / win_level

    @property
    def kind(self) -> str:
        """Group used to avoid two similar tasks on one day."""
        return self.metric if not self.filt else f"{self.metric}:{self.filt}"

    def matches_card(self, card: str) -> bool:
        if self.filt == "colour":
            return colour_of(card) == self.value
        if self.filt == "type":
            return type_of(card) == self.value
        if self.filt == "card":
            return card == self.value
        return True

    def feasible(self, unlocked) -> bool:
        """Possible with the cards unlocked so far?"""
        if not self.filt:
            return True
        have = sum(1 for c in unlocked if self.matches_card(c))
        if self.filt == "colour":                      # a colour must be common enough on the boards to reach the target
            return have >= (1, 2, 3)[self.tier - 1]
        return have >= 1


# ---------------------------------------------------------------------------------------------------
def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _build() -> list[Challenge]:
    out: list[Challenge] = []

    def add(metric, target, tier, text, filt="", value="", param=0):
        ident = f"{metric}|{filt}|{value}|{param}|{target}"
        out.append(Challenge(ident, metric, target, tier, text, filt, value, param))

    # -- plain counters -------------------------------------------------------------------------
    for t, tier in ((3, EASY), (6, EASY), (10, MEDIUM), (15, MEDIUM), (25, HARD), (40, HARD)):
        add("cols", t, tier, f"Complete {t} columns")
    for t, tier in ((10, EASY), (20, EASY), (40, MEDIUM), (80, MEDIUM), (120, HARD), (200, HARD)):
        add("reveal", t, tier, f"Reveal {t} hidden cards")
    for t, tier in ((10, EASY), (25, EASY), (50, MEDIUM), (100, MEDIUM), (150, HARD), (250, HARD)):
        add("pairs", t, tier, f"Pair cards {t} times")
    for t, tier in ((30, EASY), (60, EASY), (120, MEDIUM), (200, MEDIUM), (350, HARD), (500, HARD)):
        add("moves", t, tier, f"Make {t} moves")
    for t, tier in ((1, EASY), (2, EASY), (3, MEDIUM), (5, MEDIUM), (8, HARD), (12, HARD)):
        add("boards", t, tier, f"Solve {t} {_plural(t, 'board', 'boards')}")
    for t, tier in ((1, MEDIUM), (2, HARD), (3, HARD)):
        add("win_hard", t, tier, f"Solve {t} {_plural(t, 'board', 'boards')} in Hard mode")
    for t, tier in ((1, EASY), (2, MEDIUM), (3, MEDIUM), (5, HARD)):
        add("win_clean", t, tier, f"Solve {t} {_plural(t, 'board', 'boards')} without using undo")
    for secs, tier in ((180, EASY), (120, MEDIUM), (90, HARD), (60, HARD)):
        add("win_fast", 1, tier, f"Solve a board in under {secs} seconds", param=secs)
    for secs, t, tier in ((150, 2, MEDIUM), (120, 3, HARD)):
        add("win_fast", t, tier, f"Solve {t} boards in under {secs} seconds each", param=secs)
    for cols, t, tier in ((6, 1, EASY), (8, 1, MEDIUM), (8, 2, MEDIUM), (10, 1, HARD), (10, 2, HARD)):
        add("win_wide", t, tier, f"Solve {t} {_plural(t, 'board', 'boards')} at least {cols} columns wide", param=cols)
    for lvl, tier in ((3, EASY), (6, MEDIUM), (9, MEDIUM), (12, HARD), (15, HARD)):
        add("win_level", 1, tier, f"Solve a Campaign board on level {lvl} or higher", param=lvl)
    for t, tier in ((1, MEDIUM), (2, HARD)):
        add("rescues", t, tier, f"Use a rescue {t} {_plural(t, 'time', 'times')}")
    add("win_rescued", 1, HARD, "Solve a board after using a rescue")
    for t, tier in ((3, EASY), (5, MEDIUM), (7, MEDIUM), (10, HARD), (14, HARD)):
        add("chain", t, tier, f"Reach a pairing chain of {t}")
    for t, tier in ((500, EASY), (1500, EASY), (3000, MEDIUM), (6000, MEDIUM), (12000, HARD), (25000, HARD)):
        add("score", t, tier, f"Reach {t:,} points in one run")

    # -- by colour --------------------------------------------------------------------------------
    for colour in COLOURS:
        rare = colour in ("white", "brown", "tan")
        for t, tier in (((1, MEDIUM), (2, HARD)) if rare else ((2, EASY), (4, MEDIUM), (8, HARD))):
            add("cols", t, tier, f"Complete {t} {colour} {_plural(t, 'column', 'columns')}", "colour", colour)
        for t, tier in (((4, MEDIUM),) if rare else ((6, EASY), (14, MEDIUM), (28, HARD))):
            add("reveal", t, tier, f"Reveal {t} {colour} cards", "colour", colour)

    # -- by card type (grape, apple, pear...) -------------------------------------------------------
    types: list[str] = []
    for card in _all_cards():
        if type_of(card) not in types:
            types.append(type_of(card))
    for typ in types:
        n_cards = sum(1 for c in _all_cards() if type_of(c) == typ)
        for t, tier in (((2, EASY), (4, MEDIUM)) if n_cards > 1 else ((1, EASY), (3, MEDIUM))):
            add("cols", t, tier, f"Complete {t} {typ} {_plural(t, 'column', 'columns')}", "type", typ)
        add("reveal", 6 if n_cards > 1 else 4, EASY, f"Reveal {6 if n_cards > 1 else 4} {typ} cards", "type", typ)
        add("reveal", 18 if n_cards > 1 else 12, MEDIUM, f"Reveal {18 if n_cards > 1 else 12} {typ} cards", "type", typ)

    # -- one exact card -------------------------------------------------------------------------
    for card in _all_cards():
        add("cols", 1, HARD, f"Complete a column of {card_label(card)} cards", "card", card)
    return out


CATALOGUE: list[Challenge] = _build()
BY_ID: dict[str, Challenge] = {c.id: c for c in CATALOGUE}
assert len(BY_ID) == len(CATALOGUE), "challenge ids must be unique"


# ---------------------------------------------------------------------------------------------------
def pick_daily(date: str, unlocked=None) -> list[Challenge]:
    """The three tasks for a calendar day ("YYYY-MM-DD"): easy, medium, hard. Same date -> same tasks."""
    seed = int.from_bytes(hashlib.sha256(f"orderwick-daily:{date}".encode()).digest()[:8], "big")
    rng = random.Random(seed)
    unlocked = list(unlocked) if unlocked is not None else _all_cards()
    chosen: list[Challenge] = []
    used: set[str] = set()
    for tier in (EASY, MEDIUM, HARD):
        pool = [c for c in CATALOGUE if c.tier == tier and c.feasible(unlocked) and c.kind not in used
                and not any(c.metric == o.metric and c.filt == o.filt == "" for o in chosen)]
        if not pool:                                         # cannot happen with the real catalogue; stay safe
            pool = [c for c in CATALOGUE if c.tier == tier and c.id not in {o.id for o in chosen}]
        pick = rng.choice(pool)
        chosen.append(pick)
        used.add(pick.kind)
    return chosen


class DailyState:
    """Today's tasks and progress. Pure data + rules; saved by data/daily.py."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        self.date: str = data.get("date", "")
        self.ids: list[str] = [i for i in data.get("ids", []) if i in BY_ID]
        self.progress: dict[str, int] = {k: int(v) for k, v in data.get("progress", {}).items() if k in BY_ID}
        self.done: set[str] = {i for i in data.get("done", []) if i in BY_ID}
        self.streak: int = int(data.get("streak", 0))              # consecutive days with at least one task done
        self.best_streak: int = int(data.get("best_streak", 0))
        self.last_done_date: str = data.get("last_done_date", "")
        self.total_done: int = int(data.get("total_done", 0))
        self.full_days: int = int(data.get("full_days", 0))        # days on which all three were done
        self.full_counted: str = data.get("full_counted", "")
        self.board_date: str = data.get("board_date", "")          # the day on which the daily board was solved
        self.board_score: int = int(data.get("board_score", 0))
        self.board_moves: int = int(data.get("board_moves", 0))
        self.board_time: float = float(data.get("board_time", 0.0))

    # ---- day handling ---------------------------------------------------------------------------
    def ensure_today(self, today: str, unlocked=None) -> bool:
        """Draws a new set if the date changed (or nothing was drawn yet). True when a new day started."""
        if self.date == today and len(self.ids) == PER_DAY:
            return False
        self.date = today
        self.ids = [c.id for c in pick_daily(today, unlocked)]
        self.progress = {}
        self.done = set()
        return True

    @property
    def today(self) -> list[Challenge]:
        return [BY_ID[i] for i in self.ids]

    def value(self, ch: Challenge) -> int:
        return self.progress.get(ch.id, 0)

    # ---- recording --------------------------------------------------------------------------------
    def record(self, metric: str, amount: int = 1, card: str = "", value: int = 0) -> list[Challenge]:
        """Counts an event for today's tasks. Returns the tasks completed by it.

        `card` = the card involved (for colour / type filters); `value` = the measured value for best metrics
        (chain, score) and for thresholds (seconds for win_fast, columns for win_wide, level for win_level)."""
        finished: list[Challenge] = []
        for ch in self.today:
            if ch.id in self.done or ch.metric != metric:
                continue
            if ch.filt and not ch.matches_card(card):
                continue
            if metric in BEST_METRICS:
                self.progress[ch.id] = max(self.progress.get(ch.id, 0), min(value, ch.target))
            else:
                rule = THRESHOLD_METRICS.get(metric)
                if rule == "max" and value > ch.param:
                    continue
                if rule == "min" and value < ch.param:
                    continue
                self.progress[ch.id] = min(ch.target, self.progress.get(ch.id, 0) + amount)
            if self.progress[ch.id] >= ch.target:
                self.done.add(ch.id)
                finished.append(ch)
        if finished:
            self._after_completion(len(finished))
        return finished

    def _after_completion(self, count: int) -> None:
        self.total_done += count
        if self.last_done_date != self.date:                      # first task of this day
            self.streak = self.streak + 1 if _is_next_day(self.last_done_date, self.date) else 1
            self.best_streak = max(self.best_streak, self.streak)
            self.last_done_date = self.date
        if len(self.done) >= PER_DAY and self.full_counted != self.date:
            self.full_counted = self.date
            self.full_days += 1

    def board_solved(self, today: str | None = None) -> bool:
        """The daily board was solved today (it cannot be played again until tomorrow)."""
        return self.board_date == (today or self.date)

    def solve_board(self, score: int, moves: int, seconds: float) -> None:
        self.board_date, self.board_score, self.board_moves, self.board_time = self.date, score, moves, seconds

    def current_streak(self, today: str) -> int:
        """The streak as the player should see it: broken if yesterday had no completed task."""
        if self.last_done_date == today or _is_next_day(self.last_done_date, today):
            return self.streak
        return 0

    def to_dict(self) -> dict:
        return {"date": self.date, "ids": list(self.ids), "progress": dict(self.progress), "done": sorted(self.done),
                "streak": self.streak, "best_streak": self.best_streak, "last_done_date": self.last_done_date,
                "total_done": self.total_done, "full_days": self.full_days, "full_counted": self.full_counted,
                "board_date": self.board_date, "board_score": self.board_score, "board_moves": self.board_moves,
                "board_time": self.board_time}


def _is_next_day(previous: str, current: str) -> bool:
    import datetime
    try:
        a = datetime.date.fromisoformat(previous)
        b = datetime.date.fromisoformat(current)
    except ValueError:
        return False
    return (b - a).days == 1

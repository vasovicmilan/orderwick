"""The daily board: ONE board per calendar day, the same for every player and every device. No pygame dependency.

The board is built from a seed derived from the date, with the cards every player has from the start (the first
card of each family) and without the time-limited shuffling step of the normal generator, so the result does not
depend on the speed of the computer or on what the player has unlocked.
"""
from __future__ import annotations

import hashlib
import random

from .. import config
from .levels import LevelCatalog, Mode
from .models import LevelSpec

MIN_LEVEL, MAX_LEVEL = 5, 15


def _seed(date: str) -> int:
    return int.from_bytes(hashlib.sha256(f"orderwick-daily-board:{date}".encode()).digest()[:8], "big")


def daily_level(date: str) -> int:
    """Difficulty of the day: a Campaign level between 5 and 15."""
    return random.Random(_seed(date) ^ 0x9E3779B9).randint(MIN_LEVEL, MAX_LEVEL)


def base_cards() -> frozenset[str]:
    """The cards every player has: the first card of each family."""
    return frozenset(names[0] for names in config.CARD_FAMILIES.values())


class DailyBoardMode(Mode):
    id = "daily"
    title = "Daily board"
    short_title = "DAILY BOARD"
    ranked = False                         # not on the leaderboards (it has its own one-per-day result)
    no_rescue_message = "There is no rescue on the daily board. Use undo, or restart the board."

    def __init__(self, date: str):
        self.date = date
        self.level = daily_level(date)

    def initial_level(self) -> int:
        return self.level

    def spec_for(self, level: int) -> LevelSpec:
        return LevelCatalog.spec(self.level)

    def next_level(self, level: int) -> int:
        return self.level

    def rescue_level(self, level: int) -> int | None:
        return None

    def level_label(self, level: int) -> str:
        return str(self.level)

    def seeded(self) -> tuple[random.Random, frozenset[str]]:
        """A fresh generator for the day's board: calling it again gives exactly the same board."""
        return random.Random(_seed(self.date)), base_cards()

"""Campaign level table and game modes."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import LevelSpec


def _reveal_for(level: int) -> int:
    """How many top cards of a column are face up at the start."""
    if level <= 2:
        return 3
    if level <= 4:
        return 2
    return 1


def _build_catalog() -> list[LevelSpec]:
    """From easy to hard:

    1-6   width grows 5 -> 10 (4 free slots, 6 cards per type)
    7-8   free slots 3, then 2
    9-14  height grows 7 -> 12 cards per type (2 free slots)
    15    finale: 10 x 13, one free slot, 9 full columns + 1 empty
    """
    rows: list[tuple[int, int, int]] = []
    for cols in range(5, 11):
        rows.append((cols, 4, 6))
    rows.append((10, 3, 6))
    rows.append((10, 2, 6))
    for k in range(7, 13):
        rows.append((10, 2, k))
    rows.append((10, 1, 12))
    return [LevelSpec(c, f, k, _reveal_for(i + 1)) for i, (c, f, k) in enumerate(rows)]


class LevelCatalog:
    """Campaign: level indexes start at 1. After the last level the finale repeats."""

    _specs = _build_catalog()

    @classmethod
    def count(cls) -> int:
        return len(cls._specs)

    @classmethod
    def final_level(cls) -> int:
        return len(cls._specs)

    @classmethod
    def spec(cls, level: int) -> LevelSpec:
        level = max(1, min(level, len(cls._specs)))
        return cls._specs[level - 1]

    @classmethod
    def all_specs(cls) -> list[LevelSpec]:
        return list(cls._specs)


class Mode(ABC):
    """Way of playing: decides the level order, the rescue, and whether the result is ranked."""

    id = "mode"
    title = "Mode"
    short_title = "MODE"      # short name for the HUD (at most 14 letters)
    ranked = True
    no_rescue_message = "There is no lower level than 1. Press R for a new board."

    def seeded(self):
        """None = a random board each time. A mode may return (rng, unlocked_cards) for a fixed, reproducible board."""
        return None

    @abstractmethod
    def initial_level(self) -> int: ...

    @abstractmethod
    def spec_for(self, level: int) -> LevelSpec: ...

    def next_level(self, level: int) -> int:
        return level + 1

    def rescue_level(self, level: int) -> int | None:
        """Level you fall back to on a rescue; None = rescue is not possible."""
        return level - 1 if level > 1 else None

    def level_label(self, level: int) -> str:
        return str(level)


class CampaignMode(Mode):
    id = "campaign"
    title = "Campaign"
    short_title = "CAMPAIGN"

    def __init__(self, start_level: int = 1):
        self.start_level = max(1, min(start_level, LevelCatalog.final_level()))

    def initial_level(self) -> int:
        return self.start_level

    def spec_for(self, level: int) -> LevelSpec:
        return LevelCatalog.spec(level)


class HardMode(CampaignMode):
    """The hardest level right away, then more finale boards."""

    id = "hard"
    title = "Hard mode"
    short_title = "HARD MODE"

    def __init__(self) -> None:
        super().__init__(LevelCatalog.final_level())


class CustomMode(Mode):
    """Custom board: width, free slots and height of your choice. Not on the leaderboard."""

    id = "custom"
    title = "Custom game"
    short_title = "CUSTOM GAME"
    ranked = False

    def __init__(self, cols: int, free: int, k: int, reveal: int = 1):
        self._spec = LevelSpec(cols, min(free, cols), k, reveal)

    def initial_level(self) -> int:
        return 1

    def spec_for(self, level: int) -> LevelSpec:
        return self._spec

    def next_level(self, level: int) -> int:
        return 1

    def rescue_level(self, level: int) -> int | None:
        return 1       # there are no levels, but a rescue (+1 free slot) is allowed

    def level_label(self, level: int) -> str:
        return "—"

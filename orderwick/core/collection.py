"""Card collection: the first card of every family is unlocked, the rest are earned by playing.

No pygame dependency. Keeps "points" per family and derives what is unlocked from them.
"""
from __future__ import annotations

from .. import config


class Collection:
    def __init__(self, data: dict | None = None):
        data = data or {}
        saved = {config.LEGACY_FAMILY_KEYS.get(k, k): v for k, v in data.get("points", {}).items()}
        self.points: dict[str, int] = {f: int(saved.get(f, 0)) for f in config.CARD_FAMILIES}
        self.granted: set[str] = {n for n in data.get("granted", []) if n in config.PREMIUM_CARDS}
        self._unlocked = self._compute()

    # ---- pravila -----------------------------------------------------------------------
    @staticmethod
    def thresholds(family: str) -> list[int]:
        """Threshold for each locked card of the family (in order: second, third...)."""
        locked = len(config.CARD_FAMILIES[family]) - 1
        if locked <= 0:
            return []
        return config.UNLOCK_THRESHOLDS[locked]

    @staticmethod
    def family_of(name: str) -> str | None:
        for family, names in config.CARD_FAMILIES.items():
            if name in names:
                return family
        return None

    def _compute(self) -> set[str]:
        out: set[str] = set()
        for family, names in config.CARD_FAMILIES.items():
            out.add(names[0])
            pts = self.points.get(family, 0)
            for name, need in zip(names[1:], self.thresholds(family)):
                if pts >= need:
                    out.add(name)
        return out | self.granted

    # ---- upiti ---------------------------------------------------------------------------
    @property
    def unlocked(self) -> frozenset[str]:
        return frozenset(self._unlocked)

    @staticmethod
    def total() -> int:
        return sum(len(n) for n in config.CARD_FAMILIES.values()) + len(config.PREMIUM_CARDS)

    def is_unlocked(self, name: str) -> bool:
        return name in self._unlocked

    def next_threshold(self, family: str) -> int | None:
        pts = self.points.get(family, 0)
        for need in self.thresholds(family):
            if pts < need:
                return need
        return None

    # ---- promene ---------------------------------------------------------------------------
    def add_points(self, family: str, amount: int) -> list[str]:
        """Adds points to a family; returns the names of newly unlocked cards."""
        if amount <= 0 or family not in self.points:
            return []
        self.points[family] += amount
        now = self._compute()
        new = sorted(now - self._unlocked, key=lambda n: config.CARD_FAMILIES[family].index(n)
                     if n in config.CARD_FAMILIES[family] else 0)
        self._unlocked = now
        return new

    def grant(self, name: str) -> bool:
        """Premium card (a reward): True if it was newly unlocked."""
        if name not in config.PREMIUM_CARDS or name in self.granted:
            return False
        self.granted.add(name)
        self._unlocked = self._compute()
        return True

    def to_dict(self) -> dict:
        return {"points": dict(self.points), "granted": sorted(self.granted)}

"""Scoring: level + bonus for few moves + bonus for speed."""
from __future__ import annotations

from .models import LevelSpec


class Scoring:
    LEVEL_POINTS = 100

    @staticmethod
    def par_moves(spec: LevelSpec) -> int:
        return spec.cards * 3

    @staticmethod
    def par_seconds(spec: LevelSpec) -> int:
        return spec.cards * 3

    @classmethod
    def move_bonus(cls, spec: LevelSpec, moves: int) -> int:
        return max(0, cls.par_moves(spec) - moves)

    @classmethod
    def time_bonus(cls, spec: LevelSpec, seconds: float) -> int:
        return max(0, int(cls.par_seconds(spec) - seconds))

    @classmethod
    def gain(cls, level: int, spec: LevelSpec, moves: int, seconds: float) -> int:
        return cls.LEVEL_POINTS * level + cls.move_bonus(spec, moves) + cls.time_bonus(spec, seconds)


def format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"

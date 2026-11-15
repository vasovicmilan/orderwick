"""Scoring: level, then few moves (the skill), and only a little for speed.

Why: an AI agent plays several times faster than a person, while a person usually finds a shorter solution. If time counted as much
as moves, the AI would always win. Now every move saved is worth MOVE_POINTS and every TIME_DIVISOR seconds under par is worth one
point, so time is a tie-breaker-sized bonus (at most par_seconds / TIME_DIVISOR points). Mirrored in orderwick-server/src/rules/scoring.js.
"""
from __future__ import annotations

from .models import LevelSpec


class Scoring:
    LEVEL_POINTS = 100
    MOVE_POINTS = 4      # per move under par
    TIME_DIVISOR = 6     # one point per this many seconds under par

    @staticmethod
    def par_moves(spec: LevelSpec) -> int:
        return spec.cards * 3

    @staticmethod
    def par_seconds(spec: LevelSpec) -> int:
        return spec.cards * 3

    @classmethod
    def move_bonus(cls, spec: LevelSpec, moves: int) -> int:
        return cls.MOVE_POINTS * max(0, cls.par_moves(spec) - moves)

    @classmethod
    def time_bonus(cls, spec: LevelSpec, seconds: float) -> int:
        return max(0, int(cls.par_seconds(spec) - seconds)) // cls.TIME_DIVISOR

    @classmethod
    def gain(cls, level: int, spec: LevelSpec, moves: int, seconds: float) -> int:
        return cls.LEVEL_POINTS * level + cls.move_bonus(spec, moves) + cls.time_bonus(spec, seconds)


def format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"

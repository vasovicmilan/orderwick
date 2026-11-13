"""Achievements: definitions and checking. No pygame dependency.

Every achievement is a threshold on one counter from `stats` (e.g. "boards_won" >= 10), so the same data
also gives progress (3/10) for the achievements screen.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    desc: str
    stat: str
    target: int


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_board", "First Steps", "Solve your first board.", "boards_won", 1),
    Achievement("boards_10", "Getting Going", "Solve 10 boards.", "boards_won", 10),
    Achievement("boards_50", "Sorting Pro", "Solve 50 boards.", "boards_won", 50),
    Achievement("boards_200", "Sorting Master", "Solve 200 boards.", "boards_won", 200),
    Achievement("level_5", "Warming Up", "Solve a campaign board on level 5.", "best_level", 5),
    Achievement("level_10", "Climbing", "Solve a campaign board on level 10.", "best_level", 10),
    Achievement("finale", "The Finale", "Solve the 10x13 finale board.", "campaign_clears", 1),
    Achievement("hard_1", "Brave Start", "Solve a board in Hard mode.", "hard_wins", 1),
    Achievement("hard_10", "Hard as Nails", "Solve 10 boards in Hard mode.", "hard_wins", 10),
    Achievement("clean", "Clean Hands", "Solve a level 5+ board without using undo.", "clean_wins", 1),
    Achievement("speedy", "Quick Fingers", "Solve a level 5+ board in under 90 seconds.", "fast_wins", 1),
    Achievement("rescue_1", "Lifesaver", "Use a rescue.", "rescues", 1),
    Achievement("comeback", "Comeback", "Solve a board after using a rescue.", "rescued_wins", 1),
    Achievement("cards_1", "New Friend", "Unlock your first new card.", "new_cards", 1),
    Achievement("cards_10", "Collector", "Unlock 10 new cards.", "new_cards", 10),
    Achievement("cards_all", "Full Collection", "Unlock every card.", "new_cards", 26),
    Achievement("family_1", "Family Reunion", "Unlock every card of one family.", "families_done", 1),
    Achievement("score_1k", "First Thousand", "Reach 1,000 points in one run.", "best_score", 1000),
    Achievement("score_5k", "Points Rolling", "Reach 5,000 points in one run.", "best_score", 5000),
    Achievement("score_10k", "Ten Thousand", "Reach 10,000 points in one run.", "best_score", 10000),
    Achievement("score_25k", "High Roller", "Reach 25,000 points in one run.", "best_score", 25000),
    Achievement("score_50k", "Fifty Thousand", "Reach 50,000 points in one run.", "best_score", 50000),
    Achievement("score_100k", "Hundred Thousand", "Reach 100,000 points in one run.", "best_score", 100000),
    Achievement("total_100k", "Piggy Bank", "Earn 100,000 points in total.", "total_points", 100000),
    Achievement("total_1m", "Millionaire", "Earn 1,000,000 points in total.", "total_points", 1000000),
    Achievement("reveal_100", "Peeker", "Reveal 100 hidden cards.", "cards_revealed", 100),
    Achievement("reveal_1k", "Detective", "Reveal 1,000 hidden cards.", "cards_revealed", 1000),
    Achievement("reveal_10k", "All-Seeing", "Reveal 10,000 hidden cards.", "cards_revealed", 10000),
    Achievement("cols_10", "Tidy", "Complete 10 columns.", "columns_done", 10),
    Achievement("cols_100", "Neat Freak", "Complete 100 columns.", "columns_done", 100),
    Achievement("cols_1k", "Perfectionist", "Complete 1,000 columns.", "columns_done", 1000),
    Achievement("combo_5", "Combo", "Pair cards 5 times in a row, quickly.", "best_chain", 5),
    Achievement("combo_10", "Super Combo", "Pair cards 10 times in a row, quickly.", "best_chain", 10),
    Achievement("rescue_10", "Safety Net", "Use 10 rescues.", "rescues", 10),
    Achievement("finale_5", "Finale Fan", "Solve the finale 5 times.", "campaign_clears", 5),
    Achievement("hard_50", "Hard Core", "Solve 50 boards in Hard mode.", "hard_wins", 50),
    Achievement("time_1h", "Dedicated", "Play for 1 hour in total.", "play_minutes", 60),
    Achievement("time_10h", "Long Haul", "Play for 10 hours in total.", "play_minutes", 600),
    Achievement("runs_10", "Regular", "Finish 10 runs.", "runs", 10),
    Achievement("runs_50", "Veteran", "Finish 50 runs.", "runs", 50),
    Achievement("daily_1", "Daily Starter", "Complete a daily challenge.", "daily_done", 1),
    Achievement("daily_10", "Daily Habit", "Complete 10 daily challenges.", "daily_done", 10),
    Achievement("daily_50", "Daily Devotion", "Complete 50 daily challenges.", "daily_done", 50),
    Achievement("daily_100", "Daily Centurion", "Complete 100 daily challenges.", "daily_done", 100),
    Achievement("daily_full_1", "Full House", "Complete all three daily challenges in one day.", "daily_full", 1),
    Achievement("daily_full_7", "Perfect Week", "Complete all three daily challenges on 7 different days.", "daily_full", 7),
    Achievement("daily_full_30", "Perfect Month", "Complete all three daily challenges on 30 different days.", "daily_full", 30),
    Achievement("streak_3", "On a Roll", "Complete a daily challenge 3 days in a row.", "daily_streak", 3),
    Achievement("streak_7", "Week Streak", "Complete a daily challenge 7 days in a row.", "daily_streak", 7),
    Achievement("streak_30", "Unstoppable", "Complete a daily challenge 30 days in a row.", "daily_streak", 30),
]
BY_ID = {a.id: a for a in ACHIEVEMENTS}

DEFAULT_STATS = {
    "boards_won": 0, "best_level": 0, "campaign_clears": 0, "hard_wins": 0, "clean_wins": 0, "fast_wins": 0,
    "rescues": 0, "rescued_wins": 0, "new_cards": 0, "families_done": 0, "best_score": 0, "runs": 0,
    "total_points": 0, "cards_revealed": 0, "columns_done": 0, "best_chain": 0, "play_minutes": 0,
    "daily_done": 0, "daily_full": 0, "daily_streak": 0,
}
FAST_SECONDS = 90
MIN_SKILL_LEVEL = 5


class AchievementTracker:
    """Holds the counters and the unlocked achievements (id -> date)."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        self.stats = {**DEFAULT_STATS, **{k: int(v) for k, v in data.get("stats", {}).items() if k in DEFAULT_STATS}}
        self.unlocked: dict[str, str] = dict(data.get("unlocked", {}))

    def progress(self, a: Achievement) -> tuple[int, int]:
        return min(self.stats.get(a.stat, 0), a.target), a.target

    def bump(self, stat: str, amount: int = 1) -> None:
        self.stats[stat] = self.stats.get(stat, 0) + amount

    def at_least(self, stat: str, value: int) -> None:
        self.stats[stat] = max(self.stats.get(stat, 0), int(value))

    def check(self, today: str) -> list[Achievement]:
        """Unlocks every achievement whose threshold is reached; returns the new ones."""
        new = []
        for a in ACHIEVEMENTS:
            if a.id not in self.unlocked and self.stats.get(a.stat, 0) >= a.target:
                self.unlocked[a.id] = today
                new.append(a)
        return new

    def to_dict(self) -> dict:
        return {"stats": dict(self.stats), "unlocked": dict(self.unlocked)}

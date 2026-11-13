"""Lokalna rang lista (po modu) i osnovna statistika."""
from __future__ import annotations

import time

from .. import config
from .storage import JsonStore

RANKED_MODES = ("campaign", "hard")


class Leaderboard:
    def __init__(self, store: JsonStore | None = None):
        self.store = store or JsonStore("leaderboard.json")
        self.data = self.store.load({
            "entries": {m: [] for m in RANKED_MODES},
            "stats": {"games": 0, "best_level": 0},
        })
        for m in RANKED_MODES:
            self.data["entries"].setdefault(m, [])

    # ---- rang lista -------------------------------------------------------------
    def top(self, mode_id: str) -> list[dict]:
        return list(self.data["entries"].get(mode_id, []))

    def qualifies(self, mode_id: str, score: int) -> bool:
        if mode_id not in RANKED_MODES or score <= 0:
            return False
        entries = self.data["entries"][mode_id]
        return len(entries) < config.LEADERBOARD_SIZE or score > min(e["score"] for e in entries)

    def add(self, mode_id: str, name: str, result: dict) -> int:
        """Dodaje rezultat i vraca poziciju (1 = prvi)."""
        entry = {
            "name": (name.strip() or "PLAYER")[: config.NAME_MAX_LEN],
            "score": int(result["score"]),
            "level": int(result["level"]),
            "time": float(result["time"]),
            "moves": int(result["moves"]),
            "date": time.strftime("%Y-%m-%d"),
        }
        entries = self.data["entries"][mode_id]
        entries.append(entry)
        entries.sort(key=lambda e: (-e["score"], e["time"]))
        del entries[config.LEADERBOARD_SIZE:]
        self.store.save(self.data)
        return entries.index(entry) + 1 if entry in entries else 0

    # ---- statistika ---------------------------------------------------------------
    def record_game(self, peak_level: int) -> None:
        stats = self.data["stats"]
        stats["games"] += 1
        stats["best_level"] = max(stats["best_level"], peak_level)
        self.store.save(self.data)

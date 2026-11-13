"""Connects game events to sound (effects for moves, pairing, winning, unlocking...)."""
from __future__ import annotations

import time

from .engine.audio import audio

CHAIN_WINDOW = 3.0            # sekundi: uzastopna spajanja unutar tog vremena penju lestvicu


class SfxDirector:
    def __init__(self, events):
        self.chain = 0
        self.events = events
        self.last_pair = 0.0
        events.subscribe("move", self._move)
        events.subscribe("undo", lambda **_: audio.play("undo"))
        events.subscribe("rescue", lambda **_: audio.play("rescue"))
        events.subscribe("restart", lambda **_: audio.play("restart"))
        events.subscribe("round_won", lambda **_: audio.play("win"))
        events.subscribe("card_unlocked", lambda **_: audio.play("unlock"))
        events.subscribe("cosmetic_unlocked", lambda **_: audio.play("unlock"))
        events.subscribe("challenge_done", lambda **_: audio.play("unlock"))
        events.subscribe("achievement_unlocked", lambda **_: audio.play("achievement"))

    def _move(self, paired: bool = False, revealed=(), completed: int = 0, **_):
        now = time.monotonic()
        if paired:
            self.chain = self.chain + 1 if now - self.last_pair < CHAIN_WINDOW else 0
            self.last_pair = now
            audio.play_pair(self.chain)
            self.events.emit("chain", length=self.chain + 1)
        else:
            audio.play("place")
        if completed:
            audio.play("column_done")
        if revealed:
            audio.play("reveal", 0.8)

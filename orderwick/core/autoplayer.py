"""The decision loop of a player that sees only face-up cards: plan, play, and when stuck: undo one, rescue, new board.

`observe(board)` is the only place that touches a Board, and it reads the kind of a card only if the card is face up.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Loc
from .planner import LoopGuard, Observation, Weights, choose_move, key_of, progress_of

STALL = 28            # moves without any new progress before the player tries something else
MAX_RESCUES = 3       # free slots the player is willing to buy on one board


def observe(board) -> Observation:
    hidden, up = [], []
    for col in board.columns:
        n_down = 0
        faces = []
        for card in col:
            if card.up:
                faces.append(card.kind)          # face up: a person can read it
            else:
                n_down += 1                      # face down: only that it exists
        hidden.append(n_down)
        up.append(faces)
    return Observation(hidden, up, list(board.free), board.capacity)


@dataclass
class Action:
    kind: str                      # "move" | "undo" | "rescue" | "restart" | "giveup"
    src: Loc | None = None
    dst: Loc | None = None
    why: str = ""


class VisiblePlayer:
    def __init__(self, weights: Weights | None = None, seed: int | None = None, depth: int = 5, beam: int = 70):
        self.w = weights or Weights()
        self.rng = random.Random(seed)
        self.depth, self.beam = depth, beam
        self.guard = LoopGuard()
        self.rescues = 0
        self.restarts_left = 2
        self.last = None             # "move" | "undo" | "rescue"
        self.noise = 0.0

    def new_board(self) -> None:
        self.guard.reset_board()
        self.rescues = 0
        self.last = None
        self.noise = 0.0

    def decide(self, obs: Observation, can_undo: bool, can_rescue: bool) -> Action:
        g = self.guard
        key = key_of(obs.state(), tuple(obs.free))
        prog = progress_of(obs)
        g.visits[key] = g.visits.get(key, 0) + 1
        if prog > g.best_progress + 1e-9:
            g.best_progress, g.stagnant = prog, 0
        else:
            g.stagnant += 1
        looping = g.visits[key] >= 3 or g.stagnant >= STALL
        if looping:
            g.episodes += 1
            g.stagnant = STALL // 2                          # a grace period after each remedy
            if can_undo and self.last == "move":
                g.ban_last()                                  # that move was a dead end from where it was played
                self.last = "undo"
                return Action("undo", why="loop: step back one move")
            if can_rescue and self.rescues < MAX_RESCUES:
                self.rescues += 1
                self.last = "rescue"
                g.best_progress = prog
                return Action("rescue", why="loop: one more free slot")
            if g.episodes >= 4 and self.restarts_left > 0:
                self.restarts_left -= 1
                return Action("restart", why="stuck for good: new board")
            self.noise = 12.0                                # last resort: shake the evaluation a little
        move, _val = choose_move(obs, g, self.w, self.depth, self.beam, self.rng, explore=self.noise)
        if move is None:
            if can_undo and self.last == "move":              # first take the last move back: it walked into the dead end
                g.ban_last()
                self.last = "undo"
                return Action("undo", why="no useful move: step back one move")
            if can_rescue and self.rescues < MAX_RESCUES:
                self.rescues += 1
                self.last = "rescue"
                return Action("rescue", why="no useful move: one more free slot")
            return Action("giveup", why="no legal move and nothing left to try")
        sk, si, dk, di = move
        g.history.append((key, move, prog))
        self.last = "move"
        return Action("move", Loc(sk, si), Loc(dk, di))

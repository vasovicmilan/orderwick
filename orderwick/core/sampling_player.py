"""A player that sees only what a person sees (face-up cards and how many are face down), but THINKS like a careful one.

It imagines a few ways the hidden cards could be laid out (the cards it has not seen are known: every type has `k`
cards), solves each imagined board with the real rules, and plays the first move most of the imagined boards agree on.
It keeps following that plan until a new card turns up, then imagines again. It never looks at the real hidden cards.
"""
from __future__ import annotations

import random
from collections import Counter

from .autoplayer import Action, VisiblePlayer
from .models import Loc
from .pathsolver import PathSolver


class SamplingPlayer(VisiblePlayer):
    def __init__(self, seed: int | None = None, samples: int = 10, candidates: int = 4, **kw):
        super().__init__(seed=seed, **kw)
        self.samples, self.candidates = samples, candidates
        self.sampler_rng = random.Random(seed)
        self.solver = PathSolver(node_cap=6000, time_limit=0.35)
        self.plan: list = []
        self.plan_hidden = -1

    def new_board(self) -> None:
        super().new_board()
        self.plan, self.plan_hidden = [], -1

    # ---- imagining ------------------------------------------------------------------------
    def _imagine(self, obs):
        n_types = len(obs.hidden) - 1                       # one column starts empty
        k = obs.capacity
        seen = Counter()
        for faces in obs.up:
            seen.update(faces)
        seen.update(f for f in obs.free if f is not None)
        pool = [t for t in range(n_types) for _ in range(max(0, k - seen[t]))]
        need = sum(obs.hidden)
        if len(pool) != need:
            return None
        self.sampler_rng.shuffle(pool)
        it = iter(pool)
        kinds = [[next(it) for _ in range(h)] + list(up) for h, up in zip(obs.hidden, obs.up)]
        return kinds

    def _after(self, kinds, free, k, src, dst):
        """The imagined board after a move, played with the real rules (all cards face up: only the kinds matter)."""
        from .board import Board
        board = Board.from_kinds(kinds, len(free), k, k)
        board.free = list(free)
        if not board.apply_move(src, dst).ok:
            return None
        return [[c.kind for c in col] for col in board.columns], list(board.free)

    def _fresh_plan(self, obs):
        k, n_free = obs.capacity, len(obs.free)
        boards, firsts, plans = [], Counter(), {}
        for _ in range(self.samples):
            kinds = self._imagine(obs)
            if kinds is None:
                return []
            boards.append(kinds)
            ok, moves = self.solver.solve(kinds, n_free, k, list(obs.free))
            if ok and moves:
                key = (moves[0][0].kind, moves[0][0].index, moves[0][1].kind, moves[0][1].index)
                firsts[key] += 1
                plans.setdefault(key, moves)
        if not firsts:
            return []
        best, best_score = None, -1
        for key, votes in firsts.most_common(self.candidates):
            src, dst = plans[key][0]
            good = 0
            for kinds in boards:
                nxt = self._after(kinds, list(obs.free), k, src, dst)
                if nxt is None:
                    continue
                ok, _m = self.solver.solve(nxt[0], n_free, k, nxt[1])
                good += bool(ok)
            score = good * 100 + votes
            if score > best_score:
                best, best_score = key, score
        return list(plans[best])

    def decide(self, obs, can_undo: bool, can_rescue: bool) -> Action:
        hidden_now = sum(obs.hidden)
        if self.plan and hidden_now == self.plan_hidden:
            src, dst = self.plan.pop(0)
            return Action("move", Loc(src.kind, src.index), Loc(dst.kind, dst.index), why="plan")
        self.plan = self._fresh_plan(obs)
        self.plan_hidden = hidden_now
        if self.plan:
            src, dst = self.plan.pop(0)
            return Action("move", Loc(src.kind, src.index), Loc(dst.kind, dst.index), why="plan")
        return super().decide(obs, can_undo, can_rescue)

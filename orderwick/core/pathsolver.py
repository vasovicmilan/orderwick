"""Solver that uses the EXACT game rules and returns real moves.

Unlike a quick check that moves one card at a time, this one moves a whole run of equal
cards like the game does, so "solvable" is a proof: the returned moves can be played through `Board.apply_move`
(`verify` does exactly that). Used when building boards to check/prove solvability.

The search is best-first with "safe" moves applied automatically (a run onto a pure column of the same
type, a card from a free slot onto a pure column) - the same as in the original game.
"""
from __future__ import annotations

import heapq
import time

from .board import Board
from .models import Loc, col, slot

Move = tuple[Loc, Loc]


def _uniform(c: list[int]) -> bool:
    first = c[0]
    for x in c:
        if x != first:
            return False
    return True


def _top_run(c: list[int]) -> int:
    t = c[-1]
    n = 0
    for x in reversed(c):
        if x != t:
            break
        n += 1
    return n


def _blockers(c: list[int]) -> int:
    if not c:
        return 0
    base = c[0]
    i = 0
    while i < len(c) and c[i] == base:
        i += 1
    return len(c) - i


def _first_empty(free: list[int | None]) -> int:
    for i, f in enumerate(free):
        if f is None:
            return i
    return -1


class PathSolver:
    def __init__(self, node_cap: int = 30000, time_limit: float = 2.0):
        self.node_cap = node_cap
        self.time_limit = time_limit

    # ---- safe moves ----------------------------------------------------------
    @staticmethod
    def _normalize(cols: list[list[int]], free: list[int | None], k: int, moves: list[Move]) -> None:
        changed = True
        while changed:
            changed = False
            pure: dict[int, int] = {}
            for idx, c in enumerate(cols):
                if c and _uniform(c):
                    t = c[0]
                    if t not in pure or len(c) > len(cols[pure[t]]):
                        pure[t] = idx
            for src, c in enumerate(cols):
                if not c:
                    continue
                t = c[-1]
                dst = pure.get(t)
                if dst is None or dst == src or len(cols[dst]) >= k:
                    continue
                if _uniform(c) and len(c) > len(cols[dst]):
                    continue
                n = min(_top_run(c), k - len(cols[dst]))
                del c[-n:]
                cols[dst].extend([t] * n)
                moves.append((col(src), col(dst)))
                changed = True
                break
            if changed:
                continue
            for fi, t in enumerate(free):
                if t is None:
                    continue
                dst = pure.get(t)
                if dst is not None and len(cols[dst]) < k:
                    free[fi] = None
                    cols[dst].append(t)
                    moves.append((slot(fi), col(dst)))
                    changed = True
                    break

    @staticmethod
    def _won(cols: list[list[int]], free: list[int | None], k: int) -> bool:
        if any(f is not None for f in free):
            return False
        return all(not c or (len(c) == k and _uniform(c)) for c in cols)

    @staticmethod
    def _h(cols: list[list[int]], free: list[int | None]) -> int:
        return sum(_blockers(c) for c in cols) + 2 * sum(1 for f in free if f is not None)

    # ---- pretraga -----------------------------------------------------------------
    def solve(self, kinds: list[list[int]], n_free: int, k: int,
              free_cards: list[int] | tuple = ()) -> tuple[bool | None, list[Move]]:
        """(True, moves) = solvable; (False, []) = no solution; (None, []) = undecided."""
        cols = [list(c) for c in kinds]
        free: list[int | None] = list(free_cards) + [None] * (n_free - len(free_cards))
        start_moves: list[Move] = []
        self._normalize(cols, free, k, start_moves)
        root_path = None
        for m in start_moves:
            root_path = (root_path, m)

        seen: set = set()
        counter = 0
        nodes = 0
        t0 = time.time()
        heap = [(self._h(cols, free), 0, cols, free, root_path)]
        while heap:
            _score, _n, cols, free, path = heapq.heappop(heap)
            if self._won(cols, free, k):
                return True, self._unroll(path)
            key = (tuple(sorted(tuple(c) for c in cols)), tuple(sorted(f for f in free if f is not None)))
            if key in seen:
                continue
            seen.add(key)
            nodes += 1
            if nodes > self.node_cap or (nodes & 127 == 0 and time.time() - t0 > self.time_limit):
                return None, []

            for nc, nf, mv in self._successors(cols, free, k):
                moves: list[Move] = [mv]
                self._normalize(nc, nf, k, moves)
                p = path
                for m in moves:
                    p = (p, m)
                counter += 1
                heapq.heappush(heap, (self._h(nc, nf), counter, nc, nf, p))
        return False, []

    @staticmethod
    def _unroll(path) -> list[Move]:
        out: list[Move] = []
        while path is not None:
            path, m = path
            out.append(m)
        out.reverse()
        return out

    @staticmethod
    def _successors(cols, free, k):
        empty_slot = _first_empty(free)
        for src, c in enumerate(cols):
            if not c or (len(c) == k and _uniform(c)):
                continue
            t = c[-1]
            pure_src = _uniform(c)
            if empty_slot >= 0 and not pure_src:
                nc = [list(x) for x in cols]
                nf = list(free)
                nc[src].pop()
                nf[empty_slot] = t
                yield nc, nf, (col(src), slot(empty_slot))
            run = _top_run(c)
            for dst, d in enumerate(cols):
                if dst == src or len(d) >= k:
                    continue
                if d:
                    if d[-1] != t:
                        continue
                elif pure_src:
                    continue
                n = min(run, k - len(d))
                nc = [list(x) for x in cols]
                del nc[src][-n:]
                nc[dst].extend([t] * n)
                yield nc, list(free), (col(src), col(dst))
        done_kinds = set()
        for fi, t in enumerate(free):
            if t is None or t in done_kinds:
                continue
            done_kinds.add(t)
            for dst, d in enumerate(cols):
                if len(d) >= k or (d and d[-1] != t):
                    continue
                nc = [list(x) for x in cols]
                nf = list(free)
                nf[fi] = None
                nc[dst].append(t)
                yield nc, nf, (slot(fi), col(dst))


def verify(kinds: list[list[int]], n_free: int, k: int, moves: list[Move], reveal: int = 1) -> bool:
    """Plays the moves through the real game logic; True only if all are legal and the board ends solved."""
    board = Board.from_kinds(kinds, n_free, k, reveal)
    for src, dst in moves:
        if not board.apply_move(src, dst).ok:
            return False
    return board.is_won()

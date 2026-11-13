"""Generator of solvable boards.

Instead of "deal randomly and check with a solver" (impossible for big boards with a single
free slot), the board is built BACKWARDS: it starts from the solved state and applies the
exact inverses of legal moves. So every generated board is solvable by construction,
and the solution move list is known (`GeneratedBoard.solution`).

Shuffling: a random walk backwards quickly "locks up" (all columns full, few moves) and the column bottoms
stay pure. So the main shuffle is a CIRCULAR BLOCK ROTATION: each column hands c top
cards to the next one (using the empty column), then repeats with a smaller c. Every step is an exact inverse
of a legal move (this is checked), and every column gets several layers of different types.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .models import LevelSpec, Loc, col, slot
from .pathsolver import PathSolver, verify

Move = tuple[Loc, Loc]


@dataclass
class GeneratedBoard:
    kinds: list[list[int]]            # kolone, odozdo nagore
    solution: list[Move] = field(default_factory=list)   # forward: from the start to the solution
    mixing: float = 0.0               # 0..1, share of neighbouring different cards
    score: float = 0.0                # ocena kvaliteta (izmesanost + raznovrsnost vrhova)


class BoardGenerator:
    """Builds boards for the given LevelSpec."""

    MAX_ATTEMPTS = 400
    WANTED_CANDIDATES = 24  # how many solvable candidates to compare (the best one is picked)
    PERTURB = True          # de-regularisation by swaps (verified by the solver)
    PERTURB_SCALE = 1.0     # how many swaps (1.0 = default; 0.5 = milder, 1.5 = more)
    SWAP_MAX_RUN = 3        # a swap must not create a run longer than this
    MAX_LEFTOVER = 3        # at most this many cards of the old layer may remain after a block is removed
    SKIP_PROB = 0.40        # chance that a column skips a step (irregular layers)
    POST_HIT_STEPS = 120    # how many steps to keep walking after the first 'deal' state
    SCRAMBLE_FACTOR = 6     # random shuffling steps per card
    FINISH_FACTOR = 12      # max steps for "assembling" into a deal, per card

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    # ------------------------------------------------------------------ javno
    def generate(self, spec: LevelSpec, budget: float | None = None, pause: float = 0.0) -> GeneratedBoard:
        """Returns a solvable board: the best of several "rotation" candidates, then broken up by swaps.

        `budget` = how many seconds the pattern-breaking by swaps may take (more = deeper).
        `pause` = pause between attempts (background building must not load the window).
        """
        best: GeneratedBoard | None = None
        successes = 0
        for _ in range(self.MAX_ATTEMPTS):
            result = self._candidate(spec)
            if result is None:
                continue
            successes += 1
            if best is None or result.score > best.score:
                best = result
            if successes >= self.WANTED_CANDIDATES:
                break
        if best is None:
            raise RuntimeError("Building the board failed.")
        if budget is None:
            budget = self.default_budget(spec)
        if self.PERTURB and budget > 0:
            best = self._perturb(spec, best, budget, pause)
        return best

    def default_budget(self, spec: LevelSpec) -> float:
        return 0.6 + 1.6 * self.mixing_strength(spec)

    def _perturb(self, spec: LevelSpec, board: GeneratedBoard, budget: float,
                 pause: float = 0.0) -> GeneratedBoard:
        """Breaks up the Latin square: swaps cards FROM DIFFERENT ROWS (a swap within one row
        keeps the permutation) and keeps only swaps after which the solver (exact rules) finds a solution
        that plays through the game. Every accepted state is proven solvable."""
        rng = self.rng
        k = spec.k
        kinds = [list(c) for c in board.kinds]
        solution = board.solution
        solver = PathSolver(node_cap=4000, time_limit=0.25)
        target = max(1, round(self.PERTURB_SCALE * spec.cards * (0.08 + 0.32 * self.mixing_strength(spec))))
        live = [i for i, c in enumerate(kinds) if c]
        deadline = time.time() + budget
        accepted = 0
        floor = min(self._distinct_tops(kinds), self.wanted_tops(spec))     # a swap must never make the top row more uniform
        while accepted < target and time.time() < deadline:
            if pause:
                time.sleep(pause)
            a, b = rng.sample(live, 2)
            ra = rng.randrange(3) if rng.random() < 0.5 else rng.randrange(k)     # 0 = gornji red
            rb = rng.randrange(k)
            if ra == rb or ra >= len(kinds[a]) or rb >= len(kinds[b]):
                continue
            ia, ib = len(kinds[a]) - 1 - ra, len(kinds[b]) - 1 - rb
            if kinds[a][ia] == kinds[b][ib]:
                continue
            kinds[a][ia], kinds[b][ib] = kinds[b][ib], kinds[a][ia]
            ok = (self._longest_run(kinds[a]) <= self.SWAP_MAX_RUN
                  and self._longest_run(kinds[b]) <= self.SWAP_MAX_RUN
                  and not self._is_uniform(kinds[a]) and not self._is_uniform(kinds[b])
                  and self._tops_ok(kinds, floor))
            if ok:
                found, moves = solver.solve(kinds, spec.free, k)
                ok = found is True and verify(kinds, spec.free, k, moves, spec.reveal)
            if ok:
                solution = moves
                accepted += 1
            else:
                kinds[a][ia], kinds[b][ib] = kinds[b][ib], kinds[a][ia]
        return GeneratedBoard(kinds=kinds, solution=solution, mixing=self._mixing(kinds),
                              score=self._quality(kinds, spec.types))

    @staticmethod
    def _tops_ok(cols: list[list[int]], floor: int) -> bool:
        """Top row variety: at least `floor` different types and no type on more than 4 column tops."""
        tops = [c[-1] for c in cols if c]
        return len(set(tops)) >= floor and max(tops.count(t) for t in set(tops)) <= 4

    @staticmethod
    def _longest_run(c: list[int]) -> int:
        best = run = 0
        for i, x in enumerate(c):
            run = run + 1 if i and c[i - 1] == x else 1
            best = max(best, run)
        return best

    def _candidate(self, spec: LevelSpec) -> GeneratedBoard | None:
        rotated = self._rotation(spec)
        if rotated is None:
            return self._attempt(spec)                     # rezerva: cista setnja
        # a little random noise after the rotation (breaks the pattern); if it fails, the rotation stays
        noisy = self._attempt(spec, start=rotated, scramble_steps=self.rng.randint(0, 30))
        if noisy is not None and noisy.score >= self._pack(spec, rotated).score - 0.15:
            return noisy
        return self._pack(spec, rotated)

    # --------------------------------------------------------------- interno
    def _attempt(self, spec: LevelSpec, start=None, scramble_steps: int | None = None
                 ) -> GeneratedBoard | None:
        """Walk backwards to a "deal" state. `start` = (columns, slots, log) from the rotation (optional)."""
        k, types, n = spec.k, spec.types, spec.cols
        if start is None:
            cols: list[list[int]] = [[t] * k for t in range(types)] + [[] for _ in range(n - types)]
            free: list[int | None] = [None] * spec.free
            log: list[Move] = []
        else:
            cols = [list(c) for c in start[0]]
            free = list(start[1])
            log = list(start[2])

        if scramble_steps is None:
            scramble_steps = spec.cards * self.SCRAMBLE_FACTOR
        finish_steps = spec.cards * self.FINISH_FACTOR
        want_tops = self.wanted_tops(spec)
        best: tuple[float, list[list[int]], list[Move]] | None = None
        first_hit: int | None = None
        for step in range(scramble_steps + finish_steps):
            if first_hit is not None and step - first_hit > self.POST_HIT_STEPS:
                break
            moves = self._reverse_moves(cols, free, k)
            if not moves:
                break
            if step < scramble_steps:
                move = self._pick_random(moves)
            else:
                move = self._pick_towards_deal(moves, cols, free, k)
            log.append(self._apply(move, cols, free))
            if step < scramble_steps or self._shape_distance(cols, free, k) != 0:
                continue
            if any(self._is_uniform(c) for c in cols if c):
                continue
            # the state is a "deal" (full columns + one empty): score it, then keep walking
            # looking for a better one (more different top cards) until it is good enough
            if first_hit is None:
                first_hit = step
            quality = self._quality(cols, types)
            if best is None or quality > best[0]:
                best = (quality, [list(c) for c in cols], list(log))
            if self._distinct_tops(cols) >= want_tops:
                break
        if best is None:
            return None
        _quality, kinds, forward = best
        forward.reverse()
        kinds, forward = self._empties_last(kinds, forward)
        return GeneratedBoard(kinds=kinds, solution=forward,
                              mixing=self._mixing(kinds), score=self._quality(kinds, types))

    @staticmethod
    def mixing_strength(spec: LevelSpec) -> float:
        """0 (easiest) .. 1 (finale): how many layers/rotations are needed."""
        s = (0.5 * (spec.cols - 5) / 5 + 0.3 * (spec.k - 6) / 6
             + 0.2 * (4 - min(spec.free, 4)) / 3)
        return max(0.0, min(1.0, s))

    def _rotation(self, spec: LevelSpec):
        """Shuffling in THIN layers (see the module docstring). Returns (columns, slots, log) or None.

        One chain over a group of columns: the first column hands c top cards to the empty column, each
        next one hands c to the previous one, and in the end the empty column goes back to the last. Columns stay full,
        and each of them got a new layer of c cards of another type.

        To keep layers thin (no long runs of one type), c goes down gradually (k-1, k-2, ..., 1),
        and only columns whose top run is just slightly bigger than c take part in the chain (1-3 cards of the old layer stay).
        So every column goes through many thin layers, and groups are picked randomly so layers
        are not aligned between columns.
        """
        rng = self.rng
        k, types = spec.k, spec.types
        cols: list[list[int]] = [[t] * k for t in range(types)] + [[] for _ in range(spec.cols - types)]
        free: list[int | None] = [None] * spec.free
        log: list[Move] = []
        empty = types                                       # indeks prazne kolone

        strength = self.mixing_strength(spec)
        c_stop = 1 + round((1.0 - strength) * (k - 3))      # easier boards stop earlier (fewer layers)
        for c in range(k - 1, 0, -1):
            runs = [self._top_run(cols[i]) for i in range(types)]
            last_chance = c + self.MAX_LEFTOVER
            # a column may skip a step only while it still has a chance; at the last moment
            # (more than MAX_LEFTOVER cards of the old layer would remain) it must take part. Below c_stop
            # there is no more random participation, only "thinning" of layers that would stay too thick.
            forced = [i for i in range(types) if runs[i] == last_chance]
            optional = [i for i in range(types)
                        if c >= c_stop and c + 1 <= runs[i] < last_chance and rng.random() >= self.SKIP_PROB]
            eligible = forced + optional
            if forced and len(eligible) < 2:
                partners = [i for i in range(types) if i not in forced and runs[i] >= c + 1]
                if partners:
                    eligible.append(rng.choice(partners))
            if len(eligible) < 2:
                continue
            rng.shuffle(eligible)
            pos = 0
            while pos < len(eligible):
                size = rng.randint(2, 5)
                if len(eligible) - pos - size < 2:
                    size = len(eligible) - pos
                members = eligible[pos:pos + size]
                pos += size
                if len(members) < 2:
                    continue
                order = None
                for _try in range(60):
                    cand = members[:]
                    rng.shuffle(cand)
                    tops = [cols[i][-1] for i in cand]
                    if all(tops[j] != tops[j - 1] for j in range(len(tops))):    # i krug (0, -1)
                        order = cand
                        break
                if order is None:
                    # fallback: at least one pair of columns with different top cards
                    pairs = [(x, y) for x in members for y in members
                             if x < y and cols[x][-1] != cols[y][-1]]
                    if not pairs:
                        continue
                    order = list(rng.choice(pairs))
                chain = [(order[0], empty)] + [(order[j], order[j - 1]) for j in range(1, len(order))]
                chain.append((empty, order[-1]))
                for b, a in chain:
                    n = len(cols[empty]) if b == empty else c
                    if ("cc", b, a, n) not in set(self._reverse_moves(cols, free, k)):
                        return None
                    log.append(self._apply(("cc", b, a, n), cols, free))
        if not log or any(self._is_uniform(c) for c in cols if c) \
                or self._shape_distance(cols, free, k) != 0:
            return None
        return cols, free, log

    def _pack(self, spec: LevelSpec, state) -> GeneratedBoard:
        cols, _free, log = state
        forward = list(reversed(log))
        kinds, forward = self._empties_last(cols, forward)
        return GeneratedBoard(kinds=kinds, solution=forward, mixing=self._mixing(kinds),
                              score=self._quality(kinds, spec.types))

    @staticmethod
    def wanted_tops(spec: LevelSpec) -> int:
        """Minimum number of DIFFERENT types that should be on the column tops (so the row is not monotonous)."""
        return min(spec.types, max(2, round(spec.types * 0.85)))

    @staticmethod
    def _distinct_tops(cols: list[list[int]]) -> int:
        return len({c[-1] for c in cols if c})

    @staticmethod
    def _empties_last(cols: list[list[int]], log: list[Move]) -> tuple[list[list[int]], list[Move]]:
        """The empty column goes all the way to the right (as in the imagined layout); moves are remapped."""
        order = [i for i, c in enumerate(cols) if c] + [i for i, c in enumerate(cols) if not c]
        new_index = {old: new for new, old in enumerate(order)}

        def remap(loc: Loc) -> Loc:
            return col(new_index[loc.index]) if loc.kind == "col" else loc

        return [list(cols[i]) for i in order], [(remap(a), remap(b)) for a, b in log]

    @staticmethod
    def _quality(kinds: list[list[int]], types: int) -> float:
        """Higher is better: shuffledness, short pure bottoms, varied top cards."""
        diff = total = 0
        base_total = near_pure = 0
        for c in kinds:
            if not c:
                continue
            base = 0
            for x in c:
                if x != c[0]:
                    break
                base += 1
            base_total += base / len(c)
            near_pure += base >= 0.8 * len(c)
            for i in range(1, len(c)):
                total += 1
                diff += c[i] != c[i - 1]
        ncols = sum(1 for c in kinds if c) or 1
        thr = max(3, max((len(c) for c in kinds), default=0) // 3)
        long_cards = cards = 0
        for c in kinds:
            run = 0
            for i, x in enumerate(c):
                run += 1
                if i + 1 == len(c) or c[i + 1] != x:
                    cards += run
                    long_cards += run if run >= thr else 0
                    run = 0
        long_frac = long_cards / cards if cards else 0.0
        mixing = diff / total if total else 0.0
        tops = [c[-1] for c in kinds if c]
        counts: dict[int, int] = {}
        for t in tops:
            counts[t] = counts.get(t, 0) + 1
        distinct = len(counts) / types
        worst = max(counts.values()) / len(tops) if tops else 1.0
        return (1.5 * mixing + 2.0 * distinct - 1.5 * worst
                - 3.0 * base_total / ncols - 2.0 * near_pure / ncols - 4.0 * long_frac)

    # ---- inverse moves -----------------------------------------------------
    @staticmethod
    def _is_uniform(c: list[int]) -> bool:
        return all(x == c[0] for x in c)

    @staticmethod
    def _top_run(c: list[int]) -> int:
        t = c[-1]
        n = 0
        for x in reversed(c):
            if x != t:
                break
            n += 1
        return n

    def _reverse_moves(self, cols, free, k):
        """All inverses of the legal moves from the current state.

        ('cc', b, a, n)  - n top cards of column b go back to column a
                           (forward: a -> b)
        ('cf', b, f)     - the top card of column b goes to the empty slot f
                           (forward: slot f -> b)
        ('fc', f, a)     - the card from slot f goes onto column a
                           (forward: a -> slot f)
        """
        moves = []
        for b, B in enumerate(cols):
            if not B:
                continue
            t = B[-1]
            r = self._top_run(B)
            full_b = len(B) == k
            for a, A in enumerate(cols):
                if a == b:
                    continue
                room = k - len(A)
                if room <= 0:
                    continue
                a_top_is_t = bool(A) and A[-1] == t
                if a_top_is_t and not full_b:
                    continue
                for n in range(1, min(r, room) + 1):
                    if n == r:
                        # the remaining part of B must not have t on top -> B had to be empty before the move
                        if len(B) != n:
                            continue
                        # (the game also allows "pure column onto empty", but the generator does not use it:
                        # the board then stays more varied)
                        if not A or all(x == t for x in A):
                            continue
                    moves.append(("cc", b, a, n))
            # inverse of the "slot -> column" move
            if len(B) == 1 or B[-2] == t:
                for f, v in enumerate(free):
                    if v is None:
                        moves.append(("cf", b, f))
        for f, v in enumerate(free):
            if v is None:
                continue
            for a, A in enumerate(cols):
                if len(A) < k:
                    moves.append(("fc", f, a))
        return moves

    @staticmethod
    def _apply(move, cols, free) -> Move:
        """Applies the inverse move and returns the corresponding FORWARD move."""
        kind = move[0]
        if kind == "cc":
            _, b, a, n = move
            t = cols[b][-1]
            del cols[b][-n:]
            cols[a].extend([t] * n)
            return (col(a), col(b))
        if kind == "cf":
            _, b, f = move
            free[f] = cols[b].pop()
            return (slot(f), col(b))
        _, f, a = move
        cols[a].append(free[f])
        free[f] = None
        return (col(a), slot(f))

    # ---- choosing moves ----------------------------------------------------------
    def _pick_random(self, moves):
        weights = []
        for m in moves:
            kind = m[0]
            if kind == "cc":
                weights.append(1.0 if m[3] == 1 else 0.7)
            elif kind == "cf":
                weights.append(0.35)
            else:
                weights.append(0.6)
        return self.rng.choices(moves, weights)[0]

    def _pick_towards_deal(self, moves, cols, free, k):
        """Picks the move that brings the board closer to the "deal" (full columns + one empty),
        and among equally good ones the one that gives more different top cards."""
        rng = self.rng
        if rng.random() < 0.12:
            return rng.choice(moves)
        base = self._shape_distance(cols, free, k)
        tops: dict[int, int] = {}
        for c in cols:
            if c:
                tops[c[-1]] = tops.get(c[-1], 0) + 1
        best_key = None
        best = []
        for m in moves:
            key = (base + self._delta(m, cols, k), -self._tops_after(m, cols, free, tops))
            if best_key is None or key < best_key:
                best_key, best = key, [m]
            elif key == best_key:
                best.append(m)
        return rng.choice(best)

    @staticmethod
    def _tops_after(move, cols, free, tops: dict[int, int]) -> int:
        """Number of different top cards after the move (without changing the state)."""
        change: dict[int, int] = {}

        def sub(t: int) -> None:
            change[t] = change.get(t, 0) - 1

        def add(t: int) -> None:
            change[t] = change.get(t, 0) + 1

        kind = move[0]
        if kind == "cc":
            _, b, a, n = move
            B, A = cols[b], cols[a]
            sub(B[-1])
            if len(B) > n:
                add(B[-n - 1])
            if A:
                sub(A[-1])
            add(B[-1])
        elif kind == "cf":
            _, b, _f = move
            B = cols[b]
            sub(B[-1])
            if len(B) > 1:
                add(B[-2])
        else:
            _, f, a = move
            A = cols[a]
            if A:
                sub(A[-1])
            add(free[f])
        total = 0
        for t in set(tops) | set(change):
            if tops.get(t, 0) + change.get(t, 0) > 0:
                total += 1
        return total

    @staticmethod
    def _cost(length: int, k: int) -> int:
        return min(length, k - length)

    def _delta(self, move, cols, k) -> int:
        c = self._cost
        kind = move[0]
        if kind == "cc":
            _, b, a, n = move
            lb, la = len(cols[b]), len(cols[a])
            return (c(lb - n, k) + c(la + n, k)) - (c(lb, k) + c(la, k))
        if kind == "cf":
            _, b, _f = move
            lb = len(cols[b])
            return (c(lb - 1, k) - c(lb, k)) + 1
        _, _f, a = move
        la = len(cols[a])
        return (c(la + 1, k) - c(la, k)) - 1

    def _shape_distance(self, cols, free, k) -> int:
        return sum(min(len(c), k - len(c)) for c in cols) + sum(1 for f in free if f is not None)

    @staticmethod
    def _mixing(cols) -> float:
        diff = total = 0
        for c in cols:
            for i in range(1, len(c)):
                total += 1
                if c[i] != c[i - 1]:
                    diff += 1
        return diff / total if total else 0.0

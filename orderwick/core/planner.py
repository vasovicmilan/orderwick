"""A move planner that plays like a person: it looks only at what is face up.

Face-down cards are never read. A column is a tuple of numbers, bottom to top: HIDDEN (-2) for a face-down card, REVEALED
(-1) for a card that a simulated move would turn over (its kind is unknown, so the search stops there and the real game
shows the truth), and 0.. for a known kind. The plan is a short beam search over the rules of the game; every state is
scored with weighted features (open columns, free slots in use, broken runs, face-down cards left, ...). The best line
wins and only its first move is played, then the player looks again.

`LoopGuard` keeps the search out of endless cycles: it counts how often a position was seen, forbids moves that already
led nowhere from that position, and tells the caller when to undo, rescue or give up.
"""
from __future__ import annotations

import random
from itertools import islice
from dataclasses import dataclass, field

HIDDEN, REVEALED = -2, -1

Move = tuple[str, int, str, int]            # ("col"|"free", index, "col"|"free", index)


@dataclass
class Weights:
    """How much each feature is worth. Tuned by playing a few hundred boards (tools/tune_planner.py)."""
    complete: float = 60.0         # a finished column (full, one kind)
    pure_card: float = 3.0         # per card in a column that holds one kind only and has nothing face down
    empty_col: float = 14.0        # an empty column is the most useful thing on the board
    free_card: float = 9.0         # a card parked in a free slot (more costly when few slots are left)
    broken: float = 4.0            # a card that has to leave before its column can become one pile (a blocker)
    hidden_card: float = 5.0       # a face-down card still on the board (revealing is progress)
    unknown_top: float = 3.0       # a card we just turned over in the simulation: its kind is a gamble
    top_run: float = 1.4           # length of the run on top of a column (it moves as one)
    top_pair: float = 4.0          # two columns whose top cards match (a merge is possible)
    free_match: float = 5.0        # a parked card that fits on a column right now
    anchor: float = 12.0           # a kind that already has a pure column: the rest of it has a place to go
    hidden_blocker: float = 0.15   # how much a face-down card counts as a blocker, as a share (0 = it counts fully)
    cramped: float = 18.0          # penalty per missing legal move when fewer than three are left (a deadlock is near)
    step: float = 1.2              # every move costs a little (short lines first)


@dataclass
class Observation:
    """What the player can see: per column the number of face-down cards and the face-up kinds (bottom to top)."""
    hidden: list[int]
    up: list[list[int]]
    free: list[int | None]
    capacity: int

    def state(self) -> tuple[tuple[int, ...], ...]:
        return tuple(tuple([HIDDEN] * h + list(u)) for h, u in zip(self.hidden, self.up))

    def free_cards(self) -> tuple[int, ...]:
        return tuple(f for f in self.free if f is not None)


def key_of(cols, free) -> tuple:
    return (tuple(sorted(cols)), tuple(sorted(f for f in free if f is not None)), len(free))


def _top_run(c: tuple[int, ...]) -> int:
    t, n = c[-1], 0
    for x in reversed(c):
        if x != t:
            break
        n += 1
    return n


def _pure(c: tuple[int, ...]) -> bool:
    return bool(c) and c[0] >= 0 and all(x == c[0] for x in c)


def successors(cols, free, cap):
    """All legal moves of a clean state (no unknown card on top). Yields (new_cols, new_free, move, dirty)."""
    empty_slot = next((i for i, f in enumerate(free) if f is None), -1)
    for src, c in enumerate(cols):
        if not c or (len(c) == cap and _pure(c)):
            continue
        t = c[-1]
        if t < 0:
            continue
        pure_src = _pure(c)
        run = _top_run(c)
        if empty_slot >= 0 and not pure_src:
            nc = list(cols)
            rest, dirty = _after_pop(c[:-1])
            nc[src] = rest
            nf = list(free)
            nf[empty_slot] = t
            yield nc, nf, ("col", src, "free", empty_slot), dirty
        seen_empty = False
        for dst, d in enumerate(cols):
            if dst == src or len(d) >= cap:
                continue
            if d:
                if d[-1] != t:
                    continue
            else:
                if pure_src or seen_empty:          # a pure column gains nothing by moving; all empty columns are alike
                    continue
                seen_empty = True
            n = min(run, cap - len(d))
            nc = list(cols)
            rest, dirty = _after_pop(c[:-n])
            nc[src] = rest
            nc[dst] = d + (t,) * n
            yield nc, list(free), ("col", src, "col", dst), dirty
    done = set()
    for fi, t in enumerate(free):
        if t is None or t in done:
            continue
        done.add(t)
        seen_empty = False
        for dst, d in enumerate(cols):
            if len(d) >= cap:
                continue
            if d:
                if d[-1] != t:
                    continue
            else:
                if seen_empty:
                    continue
                seen_empty = True
            nc = list(cols)
            nc[dst] = d + (t,)
            nf = list(free)
            nf[fi] = None
            yield nc, nf, ("free", fi, "col", dst), False


def _after_pop(rest: tuple[int, ...]):
    """The column after cards left it: a face-down card on top turns over (kind unknown from here on)."""
    if rest and rest[-1] == HIDDEN:
        return rest[:-1] + (REVEALED,), True
    return rest, False


def _lead(c: tuple[int, ...]) -> int:
    """Length of the run of equal known cards at the very bottom of a column (0 while its bottom is face down)."""
    if not c or c[0] < 0:
        return 0
    n = 0
    for x in c:
        if x != c[0]:
            break
        n += 1
    return n


def evaluate(cols, free, cap: int, w: Weights) -> float:
    s = 0.0
    n_free = len(free)
    used = sum(1 for f in free if f is not None)
    if used:
        s -= w.free_card * used * (1.0 + used / max(1, n_free))
    tops: dict[int, int] = {}
    for c in cols:
        if not c:
            s += w.empty_col
            continue
        t = c[-1]
        if t >= 0:
            tops[t] = tops.get(t, 0) + 1
        if _pure(c):
            s += w.pure_card * len(c) + w.anchor
            if len(c) == cap:
                s += w.complete
            continue
        hid = sum(1 for x in c if x == HIDDEN)
        vis = c[hid:]
        runs = 1 + sum(1 for a, b in zip(vis, vis[1:]) if a != b)
        # groups that must leave before this column can become one pile: a run of equal cards moves as one, so it counts once.
        # While the bottom is face down every group counts, a face-down card a little less (it may turn out to belong).
        s -= w.broken * (runs - (1 if hid == 0 else 0) + hid * (1.0 - w.hidden_blocker))
        s -= w.hidden_card * hid
        if c[-1] == REVEALED:
            s -= w.unknown_top
        s += w.top_run * (_top_run(c) if t >= 0 else 0)
    s += w.top_pair * sum(n - 1 for n in tops.values() if n > 1)
    for f in free:
        if f is not None and tops.get(f):
            s += w.free_match
    return s


@dataclass
class LoopGuard:
    """Remembers positions so the player never walks in circles."""
    visits: dict = field(default_factory=dict)
    tabu: set = field(default_factory=set)               # (position key, move): that move led nowhere from there
    history: list = field(default_factory=list)          # (key, move, progress) of the moves played on this board
    stagnant: int = 0
    best_progress: float = -1e9
    episodes: int = 0

    def seen(self, key) -> int:
        return self.visits.get(key, 0)

    def record(self, key, move, progress: float) -> None:
        self.visits[key] = self.visits.get(key, 0) + 1
        self.history.append((key, move, progress))
        if progress > self.best_progress + 1e-9:
            self.best_progress, self.stagnant = progress, 0
        else:
            self.stagnant += 1

    def ban_last(self) -> None:
        """The last move was a dead end: never play it from that position again."""
        if self.history:
            key, move, _ = self.history[-1]
            self.tabu.add((key, move))

    def reset_board(self) -> None:
        self.visits.clear(); self.tabu.clear(); self.history.clear()
        self.stagnant, self.best_progress, self.episodes = 0, -1e9, 0


def progress_of(obs: Observation) -> float:
    """Monotone-ish measure of real progress: face-down cards turned over and columns finished. Free slots do not count."""
    hidden_left = sum(obs.hidden)
    done = sum(1 for h, u in zip(obs.hidden, obs.up) if h == 0 and u and len(u) == obs.capacity and len(set(u)) == 1)
    return done * 100.0 - hidden_left * 10.0 - sum(1 for f in obs.free if f is not None)


def choose_move(obs: Observation, guard: LoopGuard, w: Weights | None = None, depth: int = 5, beam: int = 70,
                rng: random.Random | None = None, explore: float = 0.0, use_tabu: bool = True) -> tuple[Move | None, float]:
    """The best first move and its value, or (None, 0) when the position has no legal move."""
    move, val = _search(obs, guard, w, depth, beam, rng, explore, use_tabu)
    if move is None and use_tabu and guard.tabu:             # every move was banned earlier: a banned move beats giving up
        move, val = _search(obs, guard, w, depth, beam, rng, explore, False)
    return move, val


def _useful_moves(cols, free, cap: int, key) -> int:
    """Legal moves (up to three counted) that really change the position: swapping two same-looking stacks does not."""
    n = 0
    for nc, nf, _mv, _dirty in successors(cols, free, cap):
        if _dirty or key_of(nc, nf) != key:
            n += 1
            if n >= 3:
                break
    return n


def _search(obs, guard, w, depth, beam, rng, explore, use_tabu):
    w = w or Weights()
    rng = rng or random.Random()
    cap = obs.capacity
    cols0, free0 = obs.state(), tuple(obs.free)
    root_key = key_of(cols0, free0)
    frontier = [(0.0, cols0, free0, None, 0)]
    best: tuple[float, Move | None, int] = (-1e18, None, 0)
    seen_in_search = {root_key}
    for d in range(1, depth + 1):
        nxt = []
        for _v, cols, free, first, _n in frontier:
            for nc, nf, mv, dirty in successors(cols, free, cap):
                k = key_of(nc, nf)
                if k in seen_in_search:
                    continue
                seen_in_search.add(k)
                f = first or mv
                if use_tabu and d == 1 and (root_key, mv) in guard.tabu:
                    continue
                val = evaluate(nc, nf, cap, w) - w.step * d - 30.0 * guard.seen(k)
                if not dirty:
                    val -= w.cramped * max(0, 3 - _useful_moves(nc, nf, cap, k))
                if explore:
                    val += rng.random() * explore
                if val > best[0]:
                    best = (val, f, d)
                if not dirty:
                    nxt.append((val, nc, nf, f, d))
        if not nxt:
            break
        nxt.sort(key=lambda x: -x[0])
        frontier = nxt[:beam]
    return best[1], best[0]

"""The board and the move rules (a port of the logic from the original terminal game)."""
from __future__ import annotations

from dataclasses import dataclass

from .models import FREE, Card, Loc, MoveResult


@dataclass(frozen=True)
class BoardState:
    """Immutable snapshot of the board (for undo)."""
    columns: tuple
    free: tuple


class Board:
    """Columns of cards + free slots.

    Cards in a column are ordered bottom to top (the last one is the top card).
    Free slots are ordered left to right; they are shown in the top right corner.
    """

    def __init__(self, columns: list[list[Card]], free: list[int | None], capacity: int):
        self.columns = columns
        self.free = free
        self.capacity = capacity

    # ---- pravljenje -------------------------------------------------------
    @classmethod
    def from_kinds(cls, kinds: list[list[int]], n_free: int, capacity: int,
                   reveal: int = 1) -> "Board":
        columns = [
            [Card(k, i >= len(c) - reveal) for i, k in enumerate(c)]
            for c in kinds
        ]
        return cls(columns, [None] * n_free, capacity)

    # ---- upiti --------------------------------------------------------------
    @property
    def n_cols(self) -> int:
        return len(self.columns)

    @property
    def n_free(self) -> int:
        return len(self.free)

    @property
    def max_free(self) -> int:
        return self.n_cols

    def kinds(self) -> list[list[int]]:
        return [[c.kind for c in col] for col in self.columns]

    def free_cards(self) -> list[int]:
        return [f for f in self.free if f is not None]

    def is_pure(self, ci: int) -> bool:
        col = self.columns[ci]
        if not col:
            return False
        first = col[0].kind
        return all(c.kind == first for c in col)

    def is_complete(self, ci: int) -> bool:
        return len(self.columns[ci]) == self.capacity and self.is_pure(ci)

    def is_empty_at(self, loc: Loc) -> bool:
        if loc.kind == FREE:
            return self.free[loc.index] is None
        return not self.columns[loc.index]

    def is_won(self) -> bool:
        if any(f is not None for f in self.free):
            return False
        return all(not col or self.is_complete(i) for i, col in enumerate(self.columns))

    def has_moves(self) -> bool:
        cap = self.capacity
        cols = self.columns
        has_free_slot = any(f is None for f in self.free)
        for i, c in enumerate(cols):
            if not c:
                continue
            t = c[-1].kind
            pure = self.is_pure(i)
            if has_free_slot and not pure:
                return True
            for j, d in enumerate(cols):
                if i == j or len(d) >= cap:
                    continue
                if d:
                    if d[-1].kind == t:
                        return True
                elif not pure:
                    return True
        for t in self.free:
            if t is None:
                continue
            for d in cols:
                if len(d) < cap and (not d or d[-1].kind == t):
                    return True
        return False

    # ---- moves ---------------------------------------------------------------
    def apply_move(self, src: Loc, dst: Loc) -> MoveResult:
        """Performs a move. On failure the state is unchanged."""
        cols, free, cap = self.columns, self.free, self.capacity

        if src.kind == FREE:
            t = free[src.index]
            if t is None:
                return MoveResult(False, "That free slot is empty.")
            if dst.kind == FREE:
                return MoveResult(False, "A card from a free slot goes to a column.")
            d = cols[dst.index]
            if len(d) >= cap:
                return MoveResult(False, "The column is full.")
            if d and d[-1].kind != t:
                return MoveResult(False, "The cards do not match.")
            free[src.index] = None
            d.append(Card(t, True))
            return MoveResult(True, moved=1)

        s = cols[src.index]
        if not s:
            return MoveResult(False, "The column is empty.")
        t = s[-1].kind
        if dst.kind == FREE:
            if free[dst.index] is not None:
                return MoveResult(False, "That free slot is taken.")
            s.pop()
            self._reveal_top(s)
            free[dst.index] = t
            return MoveResult(True, moved=1)

        if src.index == dst.index:
            return MoveResult(False, "Source and target are the same.")
        d = cols[dst.index]
        if len(d) >= cap:
            return MoveResult(False, "The column is full.")
        if d and d[-1].kind != t:
            return MoveResult(False, "The cards do not match.")
        # Deliberately NO ban on "pure column onto an empty column": such a ban would tell the player
        # that the column is pure (and its cards hidden) whenever they try that move.
        n = 0
        while s and s[-1].kind == t and len(d) < cap:
            s.pop()
            d.append(Card(t, True))
            n += 1
        self._reveal_top(s)
        return MoveResult(True, moved=n)

    @staticmethod
    def _reveal_top(col: list[Card]) -> None:
        if col:
            col[-1].up = True

    def add_free_slot(self) -> bool:
        """Adds a free slot (on the left of the row; existing ones keep their place)."""
        if self.n_free >= self.max_free:
            return False
        self.free.insert(0, None)
        return True

    # ---- snimci -----------------------------------------------------------------
    def snapshot(self) -> BoardState:
        cols = tuple(tuple((c.kind, c.up) for c in col) for col in self.columns)
        return BoardState(cols, tuple(self.free))

    def restore(self, state: BoardState) -> None:
        self.columns = [[Card(k, up) for k, up in col] for col in state.columns]
        self.free = list(state.free)

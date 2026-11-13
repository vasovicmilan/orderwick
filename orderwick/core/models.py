"""Basic game types. No pygame dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

COL = "col"
FREE = "free"


class Loc(NamedTuple):
    """A place on the board: a column or a free slot (index from left to right)."""
    kind: str
    index: int


def col(index: int) -> Loc:
    return Loc(COL, index)


def slot(index: int) -> Loc:
    return Loc(FREE, index)


@dataclass
class Card:
    kind: int          # card type (index into the palette)
    up: bool = False   # True = otkrivena

    def copy(self) -> "Card":
        return Card(self.kind, self.up)


class MoveResult(NamedTuple):
    ok: bool
    message: str = ""
    moved: int = 0


@dataclass(frozen=True)
class LevelSpec:
    """Parameters of one board.
cols  - number of columns (width)
    cols  - broj kolona (sirina)
    free  - number of free slots at the start
    k     - cards per type = column capacity (height is k + 1 rows because of the free slots)
    reveal - how many top cards of a column are face up at the start
    One column is always empty, so the number of card types is cols - 1.
    """
    cols: int
    free: int
    k: int
    reveal: int = 1

    def __post_init__(self) -> None:
        if self.cols < 3:
            raise ValueError("At least 3 columns.")
        if not 1 <= self.free <= self.cols:
            raise ValueError("Free slots must be between 1 and the number of columns.")
        if self.k < 2:
            raise ValueError("A column must hold at least 2 cards.")

    @property
    def types(self) -> int:
        return self.cols - 1

    @property
    def rows(self) -> int:
        return self.k + 1

    @property
    def cards(self) -> int:
        return self.types * self.k

    def describe(self) -> str:
        return f"{self.cols}x{self.rows}, free slots: {self.free}"

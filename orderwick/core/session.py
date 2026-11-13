"""Game flow: a run (GameSession) made of boards (Round)."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .. import config
from .board import Board, BoardState
from .generator import BoardGenerator
from .levels import Mode
from .models import LevelSpec, Loc, MoveResult
from .palette import pick_palette
from .scoring import Scoring
from .pathsolver import PathSolver


@dataclass(frozen=True)
class UndoState:
    board: BoardState
    level: int
    moves: int


class Round:
    """One board: state, moves, time and ONE step back."""

    def __init__(self, spec: LevelSpec, level: int, board: Board, palette: list[str],
                 solution: list | None = None):
        self.spec = spec
        self.level = level
        self.board = board
        self.palette = palette          # palette[kind] = naziv sprite-a
        self.solution = solution or []
        self.moves = 0
        self.elapsed = 0.0
        self.undo: UndoState | None = None
        self.won = False
        self.gain = 0
        self.rescued = False
        self.log: list[str] = []         # every successful event of this board ("c3>c5", "s0>c2", "u", "x"): the proof for the server


class GameSession:
    """A whole run: level, score, total time. Independent of pygame."""

    def __init__(self, mode: Mode, events=None, rng: random.Random | None = None, unlocked=None):
        self.mode = mode
        self.events = events
        self.unlocked = unlocked           # set of names of unlocked cards (None = all)
        self.rng = rng or random.Random()
        self.level = mode.initial_level()
        self.start_level = self.level
        self.peak = self.level
        self.score = 0
        self.total_time = 0.0
        self.total_moves = 0
        self.solved = 0
        self.round: Round | None = None
        self.remote = None                 # online.remote.RemoteRun for a ranked online run (None = plain offline run)

    # ---- helpers ------------------------------------------------------------
    def _emit(self, event: str, **data) -> None:
        if self.events is not None:
            self.events.emit(event, session=self, **data)

    # ---- building a board ---------------------------------------------------
    def create_round(self, level: int | None = None, budget: float | None = None,
                     pause: float = 0.0) -> Round:
        """Slow (generator) - called from a background thread. Does not change the session state.

        `level` = which level the board is made for (default: the current one); `budget` = how many seconds
        the pattern-breaking may take (more = deeper shuffling, used for boards built in advance).
        """
        level = self.level if level is None else level
        if self.remote is not None:                        # ranked online: the server hands out the board (None = fall back to offline)
            remote_round = self.remote.next_round(self, level)
            if remote_round is not None:
                return remote_round
        spec = self.mode.spec_for(level)
        fixed = self.mode.seeded()
        if fixed is not None:                              # a reproducible board (the daily board): no time-based steps
            rng, cards = fixed
            generated = BoardGenerator(rng).generate(spec, 0.0, 0.0)
            palette = pick_palette(rng, spec.types, cards)
        else:
            generated = BoardGenerator(self.rng).generate(spec, budget, pause)
            palette = pick_palette(self.rng, spec.types, self.unlocked)
        board = Board.from_kinds(generated.kinds, spec.free, spec.k, spec.reveal)
        return Round(spec, level, board, palette, generated.solution)

    def start_round(self, rnd: Round) -> None:
        self.round = rnd
        if self.remote is not None:
            self.remote.apply(self)                        # the server decides the level and score of an online run
        self.peak = max(self.peak, rnd.level)
        self._emit("round_started", round=rnd)

    # ---- vreme ----------------------------------------------------------------
    def tick(self, dt: float) -> None:
        rnd = self.round
        if rnd is not None and not rnd.won:
            rnd.elapsed += dt

    # ---- moves -------------------------------------------------------------
    def move(self, src: Loc, dst: Loc) -> MoveResult:
        rnd = self.round
        if rnd is None or rnd.won:
            return MoveResult(False, "")
        before = UndoState(rnd.board.snapshot(), self.level, rnd.moves)
        paired = self._is_pair(rnd.board, src, dst)
        done_before = {i for i in range(rnd.board.n_cols) if rnd.board.is_complete(i)}
        result = rnd.board.apply_move(src, dst)
        if not result.ok:
            return result
        revealed = self._revealed_kinds(before.board, rnd.board.snapshot())
        completed = len({i for i in range(rnd.board.n_cols) if rnd.board.is_complete(i)} - done_before)
        rnd.undo = before
        rnd.moves += 1
        rnd.log.append(f"{'c' if src.kind == 'col' else 's'}{src.index}>{'c' if dst.kind == 'col' else 's'}{dst.index}")
        self._emit("move", src=src, dst=dst, moved=result.moved, paired=paired, revealed=revealed,
                   completed=completed, round=rnd)
        if rnd.board.is_won():
            self._on_round_won(rnd)
        return result

    @staticmethod
    def _is_pair(board: Board, src: Loc, dst: Loc) -> bool:
        """Whether the card goes onto a card of the same type (a pair), not onto an empty place."""
        if dst.kind != "col":
            return False
        d = board.columns[dst.index]
        if not d:
            return False
        if src.kind == "free":
            kind = board.free[src.index]
        else:
            s = board.columns[src.index]
            kind = s[-1].kind if s else None
        return kind is not None and d[-1].kind == kind

    @staticmethod
    def _revealed_kinds(before: BoardState, after: BoardState) -> list[int]:
        """Card types turned face up by this move (they were hidden)."""
        def hidden(state: BoardState) -> dict[int, int]:
            out: dict[int, int] = {}
            for col in state.columns:
                for kind, up in col:
                    if not up:
                        out[kind] = out.get(kind, 0) + 1
            return out
        b, a = hidden(before), hidden(after)
        return [k for k, n in b.items() for _ in range(max(0, n - a.get(k, 0)))]

    def undo(self) -> MoveResult:
        """Only one step back. Undoing counts as a move."""
        rnd = self.round
        if rnd is None or rnd.won:
            return MoveResult(False, "")
        if rnd.undo is None:
            return MoveResult(False, "Nothing to undo (only one step back is allowed).")
        state, rnd.undo = rnd.undo, None
        rnd.board.restore(state.board)
        self.level = state.level
        rnd.level = state.level
        rnd.moves += 1
        rnd.log.append("u")
        self._emit("undo")
        return MoveResult(True, "Move undone.")

    def _on_round_won(self, rnd: Round) -> None:
        rnd.won = True
        rnd.gain = Scoring.gain(self.level, rnd.spec, rnd.moves, rnd.elapsed)
        self.score += rnd.gain
        self.total_time += rnd.elapsed
        self.total_moves += rnd.moves
        self.solved += 1
        self._emit("round_won", round=rnd, gain=rnd.gain)

    def advance(self) -> None:
        """After a win: go to the next level (after a rescue you return to the earlier level)."""
        self.level = self.mode.next_level(self.level)

    def penalize_restart(self) -> None:
        self.score = max(0, self.score - config.RESTART_PENALTY)
        self._emit("restart")

    # ---- spas ---------------------------------------------------------------
    def rescue_blocker(self) -> str | None:
        """Reason why a rescue is not possible, or None."""
        rnd = self.round
        if rnd is None or rnd.won:
            return ""
        if self.mode.rescue_level(self.level) is None:
            return self.mode.no_rescue_message
        if rnd.board.n_free >= rnd.board.max_free:
            return "You already have the most free slots."
        return None

    def rescue_needs_check(self) -> bool:
        """If moves are still possible, first check whether a solution exists."""
        return self.round is not None and self.round.board.has_moves()

    def rescue_check_args(self) -> tuple:
        b = self.round.board
        return (b.kinds(), b.n_free, b.capacity, b.free_cards())

    @staticmethod
    def solution_exists(args: tuple) -> bool | None:
        kinds, n_free, cap, free_cards = args
        return PathSolver(node_cap=40000, time_limit=2.5).solve(kinds, n_free, cap, free_cards)[0]

    def apply_rescue(self) -> None:
        rnd = self.round
        new_level = self.mode.rescue_level(self.level)
        rnd.undo = UndoState(rnd.board.snapshot(), self.level, rnd.moves)
        self.level = new_level
        rnd.level = new_level
        rnd.board.add_free_slot()
        rnd.rescued = True
        rnd.log.append("x")
        self._emit("rescue", level=new_level)

    # ---- rezultat -------------------------------------------------------------
    def result(self) -> dict:
        return {
            "score": self.score,
            "level": self.peak,
            "time": round(self.total_time, 1),
            "moves": self.total_moves,
            "solved": self.solved,
            "start_level": self.start_level,
        }

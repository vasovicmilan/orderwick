"""Plays boards headlessly with the visible-only player and prints how often it wins.

    python tools/tune_planner.py [levels e.g. 1-15] [boards per level] [seed]
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orderwick.core.autoplayer import VisiblePlayer, observe  # noqa: E402
from orderwick.core.board import Board  # noqa: E402
from orderwick.core.generator import BoardGenerator  # noqa: E402
from orderwick.core.levels import LevelCatalog  # noqa: E402
from orderwick.core.pathsolver import PathSolver  # noqa: E402


def play_board(level: int, rng: random.Random, player: VisiblePlayer, max_moves: int = 1500, verbose: bool = False, kinds=None):
    spec = LevelCatalog.spec(level)
    kinds = kinds or BoardGenerator(rng).generate(spec).kinds
    board = Board.from_kinds(kinds, spec.free, spec.k, spec.reveal)
    player.new_board()
    undo = None
    moves, undos, rescues, restarts = 0, 0, 0, 0
    for _ in range(max_moves):
        if board.is_won():
            return True, moves, undos, rescues, restarts, 0
        can_rescue = board.n_free < board.max_free
        act = player.decide(observe(board), undo is not None, can_rescue)
        if verbose:
            print(act)
        if act.kind == "move":
            snap = board.snapshot()
            if board.apply_move(act.src, act.dst).ok:
                undo, moves = snap, moves + 1
        elif act.kind == "undo":
            board.restore(undo); undo = None; undos += 1; moves += 1
        elif act.kind == "rescue":
            if board.has_moves() and PathSolver(node_cap=40000, time_limit=1.5).solve(board.kinds(), board.n_free, board.capacity, board.free_cards())[0] is True:
                continue                                    # the game refuses: a solution still exists
            undo = board.snapshot(); board.add_free_slot(); rescues += 1
        elif act.kind == "restart":
            gen = BoardGenerator(rng).generate(spec)
            board = Board.from_kinds(gen.kinds, spec.free, spec.k, spec.reveal); undo = None; restarts += 1
            player.new_board()
        else:
            break
    return False, moves, undos, rescues, restarts, sum(observe(board).hidden)


def main() -> None:
    lv = sys.argv[1] if len(sys.argv) > 1 else "1-15"
    a, _, b = lv.partition("-")
    levels = range(int(a), int(b or a) + 1)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    rng = random.Random(seed)
    for level in levels:
        t0, wins, tot = time.time(), 0, [0, 0, 0, 0]
        for i in range(n):
            ok, m, u, r, rs, _h = play_board(level, rng, VisiblePlayer(seed=seed + i))
            wins += ok
            for j, x in enumerate((m, u, r, rs)):
                tot[j] += x
        print(f"level {level:2d}: won {wins}/{n}  avg moves {tot[0]/n:6.0f}  undo {tot[1]/n:4.1f}  rescue {tot[2]/n:3.1f}  restart {tot[3]/n:3.1f}  {time.time()-t0:5.1f}s", flush=True)


if __name__ == "__main__":
    main()

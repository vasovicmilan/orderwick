"""Compares planner settings by total moves (lower is better) over the same boards.

    python tools/tune_moves.py LEVEL BOARDS name=value ...     e.g.  free_match=0 step=2.0 depth=6
"""
from __future__ import annotations
import random, sys, time
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orderwick.core.autoplayer import VisiblePlayer, observe
from orderwick.core.board import Board
from orderwick.core.generator import BoardGenerator
from orderwick.core.levels import LevelCatalog
from orderwick.core.planner import Weights


def one(args):
    level, seed, overrides = args
    import orderwick.core.planner as pl
    pl.REVEAL_AFTER = int(overrides.pop("reveal_after", pl.REVEAL_AFTER))
    pl.REVEAL_DEPTH = int(overrides.pop("reveal_depth", pl.REVEAL_DEPTH))
    depth = int(overrides.pop("depth", 5))
    beam = int(overrides.pop("beam", 70))
    w = Weights(**overrides)
    spec = LevelCatalog.spec(level)
    kinds = BoardGenerator(random.Random(seed)).generate(spec).kinds
    board = Board.from_kinds(kinds, spec.free, spec.k, spec.reveal)
    p = VisiblePlayer(weights=w, seed=seed, depth=depth, beam=beam)
    p.new_board()
    undo, moves, resc = None, 0, 0
    for _ in range(700):
        if board.is_won():
            return True, moves, resc
        act = p.decide(observe(board), undo is not None, board.n_free < board.max_free)
        if act.kind == "move":
            snap = board.snapshot()
            if board.apply_move(act.src, act.dst).ok:
                undo, moves = snap, moves + 1
        elif act.kind == "undo":
            board.restore(undo); undo = None; moves += 1
        elif act.kind == "rescue":
            undo = board.snapshot(); board.add_free_slot(); resc += 1
        else:
            break
    return False, moves, resc


if __name__ == "__main__":
    level, n = int(sys.argv[1]), int(sys.argv[2])
    ov = {k: float(v) for k, v in (a.split("=") for a in sys.argv[3:])}
    t0 = time.time()
    with Pool(2) as pool:
        res = pool.map(one, [(level, 100 + i, dict(ov)) for i in range(n)])
    wins = sum(r[0] for r in res)
    print(f"{' '.join(sys.argv[3:]) or 'baseline':40s} won {wins}/{n}  moves {sum(r[1] for r in res)/n:6.1f}  rescue {sum(r[2] for r in res)/n:4.2f}  ({time.time()-t0:.0f}s)  per-board {[r[1] for r in res]}", flush=True)

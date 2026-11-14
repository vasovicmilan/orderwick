"""Shows how many of the player's moves are wasted: a move is useful only if it reveals a hidden card, completes a column,
joins a card to a same-kind stack that has to be built anyway, or frees something. Everything else is shuffling.

    python tools/analyze_moves.py [level] [boards] [seed]
"""
from __future__ import annotations
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orderwick.core.autoplayer import VisiblePlayer, observe
from orderwick.core.board import Board, FREE
from orderwick.core.generator import BoardGenerator
from orderwick.core.levels import LevelCatalog


def hidden(board):
    return sum(1 for c in board.columns for card in c if not card.up)


def run(level, seed, verbose=False):
    rng = random.Random(seed)
    spec = LevelCatalog.spec(level)
    kinds = BoardGenerator(rng).generate(spec).kinds
    board = Board.from_kinds(kinds, spec.free, spec.k, spec.reveal)
    player = VisiblePlayer(seed=seed)
    player.new_board()
    undo = None
    log, moves = [], 0
    for _ in range(1500):
        if board.is_won():
            break
        act = player.decide(observe(board), undo is not None, board.n_free < board.max_free)
        if act.kind == "move":
            h0 = hidden(board)
            src_kind = board.columns[act.src.index][-1].kind if act.src.kind != FREE and board.columns[act.src.index] else None
            snap = board.snapshot()
            res = board.apply_move(act.src, act.dst)
            if res.ok:
                undo = snap; moves += 1
                log.append((act.src, act.dst, src_kind, res.moved, h0 - hidden(board)))
        elif act.kind == "undo":
            board.restore(undo); undo = None; moves += 1; log.append(("undo",))
        elif act.kind == "rescue":
            undo = board.snapshot(); board.add_free_slot(); log.append(("rescue",))
        else:
            break
    return board.is_won(), moves, log


def waste(log):
    bad = 0
    for i, e in enumerate(log):
        if e[0] in ("undo", "rescue"):
            continue
        src, dst, kind, n, revealed = e
        if revealed > 0 or src.kind == FREE:
            continue
        if i and log[i - 1][0] not in ("undo", "rescue"):
            p = log[i - 1]
            if p[1] == src and p[0] == dst:         # moved straight back
                bad += 1
    return bad


if __name__ == "__main__":
    level = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    tot_m = tot_rev = tot_nr = tot_back = won = 0
    for i in range(n):
        ok, m, log = run(level, seed + i)
        mv = [e for e in log if e[0] not in ("undo", "rescue")]
        rev = sum(1 for e in mv if e[4] > 0)
        nr = len(mv) - rev
        back = waste(log)
        won += ok; tot_m += m; tot_rev += rev; tot_nr += nr; tot_back += back
        print(f"board {i}: won={ok} moves={m} reveal-moves={rev} no-reveal={nr} straight-back={back}", flush=True)
    print(f"TOTAL won {won}/{n}  moves {tot_m/n:.0f}  reveal {tot_rev/n:.0f}  no-reveal {tot_nr/n:.0f}  straight-back {tot_back/n:.1f}")

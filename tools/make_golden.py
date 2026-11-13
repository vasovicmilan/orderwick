"""Writes golden replay cases for the server's JS rules port (orderwick-server/test/golden.json).

Every case is played through the REAL GameSession (Python), and the outcome is recorded; the server test replays the same
events in JavaScript and must reach exactly the same result. Re-run this after ANY change in core/board.py, core/session.py,
core/levels.py or core/scoring.py:

    python tools/make_golden.py ../orderwick-server/test/golden.json
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orderwick.core.levels import CampaignMode, HardMode, LevelCatalog  # noqa: E402
from orderwick.core.models import col, slot  # noqa: E402
from orderwick.core.session import GameSession  # noqa: E402


def ev(src, dst) -> str:
    return f"{'c' if src.kind == 'col' else 's'}{src.index}>{'c' if dst.kind == 'col' else 's'}{dst.index}"


def loc(kind: str, i: int):
    return col(i) if kind == "c" else slot(i)


def shift_slots(e: str, by: int) -> str:
    """After a rescue a free slot is inserted at index 0: every slot index moves by one."""
    if e in ("u", "x"):
        return e
    a, b = e.split(">")
    f = lambda t: t if t[0] == "c" else f"s{int(t[1:]) + by}"
    return f"{f(a)}>{f(b)}"


def play(mode, level, seed, script, seconds):
    sess = GameSession(mode, rng=random.Random(seed))
    sess.level = level
    rnd = sess.create_round(level, 0.3, 0.0)
    sess.start_round(rnd)
    kinds0 = rnd.board.kinds()
    events: list[str] = []
    solution = [ev(a, b) for a, b in rnd.solution]
    for step in script(solution):
        events.append(step)
        if step == "u":
            assert sess.undo().ok, "undo"
        elif step == "x":
            assert sess.rescue_blocker() is None, sess.rescue_blocker()
            sess.apply_rescue()
        else:
            a, b = step.split(">")
            assert sess.move(loc(a[0], int(a[1:])), loc(b[0], int(b[1:]))).ok, step
    sess.tick(seconds)  # NOTE: elapsed is recorded AFTER the last move in this harness; the gain is recomputed below
    spec = rnd.spec
    from orderwick.core.scoring import Scoring
    won = rnd.board.is_won()
    gain = Scoring.gain(sess.level, spec, rnd.moves, seconds) if won else 0
    return {
        "mode": mode.id, "level": level,
        "spec": {"cols": spec.cols, "free": spec.free, "k": spec.k, "reveal": spec.reveal},
        "kinds": kinds0, "events": events, "seconds": seconds,
        "expect": {"won": won, "moves": rnd.moves, "level": sess.level, "rescued": rnd.rescued, "gain": gain},
    }


def main(out: str) -> None:
    cases = []
    plain = lambda s: list(s)

    def with_undo(s):
        return s[:5] + ["u"] + s[4:]  # undo move 5 (the 5th), then redo it from the same state

    def with_rescue_first(s):
        return ["x"] + [shift_slots(e, 1) for e in s]

    def rescue_undo_then_solve(s):
        return ["x", "u"] + s

    def rescue_twice(s):
        return ["x", "x"] + [shift_slots(e, 2) for e in s]

    scripts = {"plain": plain, "undo": with_undo, "rescue": with_rescue_first,
               "rescue_undo": rescue_undo_then_solve, "rescue_twice": rescue_twice}
    seed = 1
    for level in (1, 3, 6, 9, 12, 15):
        for name, script in scripts.items():
            mode = HardMode() if level == 15 and name == "plain" else CampaignMode(level)
            if level == 1 and "rescue" in name:
                continue                                    # level 1 has no rescue
            c = play(mode, level, seed, script, 37.9 + seed)
            c["name"] = f"L{level}-{name}"
            cases.append(c)
            seed += 1
    # finale keeps counting levels: level 16 uses the finale spec
    c = play(CampaignMode(15), 16, 777, plain, 80.2)
    c["name"] = "L16-plain"
    cases.append(c)
    # daily mode: no rescue
    c = play(CampaignMode(7), 7, 4242, plain, 51.0)
    c["mode"] = "daily"
    c["name"] = "daily-plain"
    cases.append(c)
    Path(out).write_text(json.dumps({"cases": cases}), encoding="utf-8")
    print(f"{len(cases)} golden cases -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "golden.json")

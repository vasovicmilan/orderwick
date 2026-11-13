"""Plays ranked online boards headlessly with the built-in solver. Used to test the server end to end and to seed a demo
leaderboard. It uses exactly the code path of the real game (GameSession + RemoteRun), only the clicks are replaced by moves.

    python tools/online_selfplay.py --url http://127.0.0.1:3000 --mode campaign --boards 6
    ORDERWICK_AGENT_KEY=<key> python tools/online_selfplay.py --url ... --mode hard --boards 2   # plays as an AI agent
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from orderwick.core.levels import CampaignMode, HardMode  # noqa: E402
from orderwick.core.daily_board import DailyBoardMode  # noqa: E402
from orderwick.core.pathsolver import PathSolver  # noqa: E402
from orderwick.core.session import GameSession  # noqa: E402
from orderwick.data.storage import JsonStore  # noqa: E402
from orderwick.engine.events import EventBus  # noqa: E402
from orderwick.online.service import OnlineService  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--mode", choices=["campaign", "hard", "daily"], default="campaign")
    ap.add_argument("--start-level", type=int, default=1)
    ap.add_argument("--boards", type=int, default=3)
    ap.add_argument("--seconds-per-move", type=float, default=0.5, help="simulated thinking time per move")
    args = ap.parse_args()

    svc = OnlineService(store=JsonStore("online.json", Path(tempfile.mkdtemp())), url=args.url)
    if not svc.agent_key:
        print("account:", svc.enable())
    events = EventBus()
    svc.attach(events)
    mode = {"campaign": lambda: CampaignMode(args.start_level), "hard": HardMode, "daily": lambda: DailyBoardMode(time.strftime("%Y-%m-%d"))}[args.mode]()
    session = GameSession(mode, events=events)
    session.remote = svc.new_remote(mode)
    if session.remote is None:
        print("online is not enabled")
        return 2
    for n in range(args.boards):
        rnd = session.create_round()
        if session.remote.broken:
            print("run went offline:", session.remote.poll(session))
            return 1
        session.start_round(rnd)
        print(session.remote.poll(session) or "", end="")
        b = rnd.board
        found, moves = PathSolver(node_cap=400000, time_limit=60).solve(b.kinds(), b.n_free, b.capacity, b.free_cards())
        if not found:
            print(f"board {n + 1}: solver gave up (level {rnd.level})")
            return 1
        for src, dst in moves:
            assert session.move(src, dst).ok
            session.tick(args.seconds_per_move)
        assert rnd.won
        for _ in range(100):                      # wait for the server's verdict
            note = session.remote.poll(session)
            if session.remote._applied:
                break
            time.sleep(0.05)
        print(f"board {n + 1}: level {rnd.level} solved in {rnd.moves} moves, server score {session.score}"
              + (f", {note}" if note else ""))
        if args.mode == "daily":
            break
        session.advance()
    events.emit("run_finished", session=session)
    time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())

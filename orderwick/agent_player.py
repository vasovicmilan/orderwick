"""Claude plays the real game: the window, the menus, the activation key and every move go through the game's own input
(key events), exactly like a person at the keyboard. The brain is orderwick/core/autoplayer.py: it sees only the face-up
cards, searches with weighted features, and when it walks in circles it undoes one move, rescues (X) or restarts.

From a packaged build (needs a display; on a server use xvfb-run):

    Orderwick --agent --server https://orderwick.com --key OW-XXXX-XXXX-XXXX --mode hard --boards 3
    Orderwick --agent --mode campaign --boards 1          (no key: plays offline, used as a smoke test of the build)

From source: python tools/claude_player.py <same options>.  Options: see `--agent --help`.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="Orderwick --agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--server", default="")
    ap.add_argument("--key", default="", help="activation key from the website account page")
    ap.add_argument("--mode", choices=["campaign", "hard"], default="hard")
    ap.add_argument("--boards", type=int, default=1, help="boards to solve before the run is finished")
    ap.add_argument("--pace", type=float, default=0.22, help="seconds between two key presses (how fast the moves look)")
    ap.add_argument("--home", default="", help="save folder (default: a fresh temporary one, so the run starts clean)")
    ap.add_argument("--nick", default="", help="nickname for the online account (3-12 letters, digits, - or _)")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--shots", default="", help="folder for screenshots of the important moments")
    return ap


def prepare(argv: list[str]) -> argparse.Namespace:
    """Sets the environment BEFORE the game's modules are imported (they read it once): server and a clean save folder."""
    args = build_parser().parse_args([a for a in argv if a != "--agent"])
    if args.server:
        os.environ["ORDERWICK_SERVER"] = args.server
    os.environ["ORDERWICK_HOME"] = args.home or tempfile.mkdtemp(prefix="claude-player-")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    return args


_LOG = None


def say(*a) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] " + " ".join(str(x) for x in a)
    try:
        print(line, flush=True)
    except Exception:                       # a windowed Windows build has no console
        pass
    if _LOG is not None:
        _LOG.write(line + "\n"); _LOG.flush()


def open_log(path: Path) -> None:
    global _LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOG = open(path, "a", encoding="utf-8")
    except OSError:
        _LOG = None

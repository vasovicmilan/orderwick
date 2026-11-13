"""Generates solvable boards for the online server and (optionally) uploads them.

The server hands these boards to players, so nobody can pick an easy layout, and it re-proves each one: the solution
we send must win when the server replays it with its own copy of the rules. The solution itself is never given to players.

    python tools/gen_boards.py --per-level 20 --out boards.json
    python tools/gen_boards.py --levels 5-15 --per-level 40 --url https://your.server --token $ADMIN_TOKEN

Cheap to run from cron: a finale board takes about a second.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orderwick.core.generator import BoardGenerator  # noqa: E402
from orderwick.core.levels import LevelCatalog  # noqa: E402


def ev(src, dst) -> str:
    return f"{'c' if src.kind == 'col' else 's'}{src.index}>{'c' if dst.kind == 'col' else 's'}{dst.index}"


def parse_levels(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        else:
            out.append(int(part))
    return [n for n in out if 1 <= n <= LevelCatalog.final_level()]


def make(level: int, rng: random.Random, budget: float) -> dict:
    spec = LevelCatalog.spec(level)
    g = BoardGenerator(rng).generate(spec, budget, 0.0)
    return {"level": level, "kinds": g.kinds, "events": [ev(a, b) for a, b in g.solution]}


def post(url: str, token: str, boards: list[dict]) -> dict:
    req = urllib.request.Request(url.rstrip("/") + "/api/v1/admin/boards", data=json.dumps({"boards": boards}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--levels", default="1-15", help="e.g. 1-15 or 5,9,15")
    ap.add_argument("--per-level", type=int, default=10)
    ap.add_argument("--budget", type=float, default=1.5, help="seconds of pattern breaking per board (more = more mixed)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", help="write the boards to this JSON file")
    ap.add_argument("--url", help="server base URL to upload to")
    ap.add_argument("--token", help="admin token (or env ORDERWICK_ADMIN_TOKEN)")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    boards: list[dict] = []
    t0 = time.time()
    for level in parse_levels(args.levels):
        for _ in range(args.per_level):
            boards.append(make(level, rng, args.budget))
        print(f"level {level:2d}: {args.per_level} boards ({time.time() - t0:.0f}s)", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps({"boards": boards}), encoding="utf-8")
        print(f"wrote {len(boards)} boards to {args.out}")
    if args.url:
        import os
        token = args.token or os.environ.get("ORDERWICK_ADMIN_TOKEN", "")
        if not token:
            sys.exit("need --token or ORDERWICK_ADMIN_TOKEN")
        for i in range(0, len(boards), 100):
            print("server:", post(args.url, token, boards[i:i + 100]))
    if not args.out and not args.url:
        print(json.dumps({"boards": boards}))


if __name__ == "__main__":
    main()

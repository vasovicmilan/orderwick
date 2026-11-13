"""Choosing the card types for one board."""
from __future__ import annotations

import random

from .. import config


def pick_palette(rng: random.Random, types: int, unlocked=None) -> list[str]:
    """Returns `types` sprite names. At most one per "family" (cards that look alike, e.g. 6 colours of
    grapes), so they are always easy to tell apart; every board picks differently."""
    pools = {f: [n for n in names if unlocked is None or n in unlocked]
             for f, names in config.CARD_FAMILIES.items()}
    pools = {f: p for f, p in pools.items() if p}
    for name in config.PREMIUM_CARDS:                      # unlocked premium cards are separate types
        if unlocked is None or name in unlocked:
            pools[f"premium:{name}"] = [name]
    families = list(pools)
    rng.shuffle(families)
    names = [rng.choice(pools[f]) for f in families[:types]]
    if len(names) < types:                       # more types than families: top up with other colours
        rest = [n for members in pools.values() for n in members if n not in names]
        rng.shuffle(rest)
        names += rest[:types - len(names)]
    rng.shuffle(names)
    return names

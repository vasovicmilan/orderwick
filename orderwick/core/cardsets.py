"""Card sets: WHICH pictures a board is dealt from. No pygame dependency.

The game's own set is the fruits and vegetables (config.CARD_FAMILIES). The server can add more (Christmas gift boxes,
Easter eggs ...): a set is a folder of transparent 16x16 pictures plus families.json, {"family": ["card_a", "card_b"]}, which
groups look-alikes exactly like CARD_FAMILIES (a board uses at most one card of each family). A card is drawn as
the card style's background with the set's picture on top, so every set works with every style.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config

DEFAULT_SET = "fruits"
_NAME = re.compile(r"^[a-z0-9_]{2,40}$")
MIN_CARDS = 12                      # the hardest boards use 9 types; a set needs a little more than that


def load_families(directory: Path) -> dict[str, list[str]] | None:
    """The families of a downloaded set, or None when families.json is missing or broken."""
    try:
        raw = json.loads((Path(directory) / "families.json").read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    families: dict[str, list[str]] = {}
    for family, names in raw.items():
        if not isinstance(names, list) or not _NAME.match(str(family)):
            return None
        good = [n for n in names if isinstance(n, str) and _NAME.match(n) and (Path(directory) / f"{n}.png").is_file()]
        if good:
            families[family] = good
    return families if sum(len(v) for v in families.values()) >= MIN_CARDS else None


def default_families() -> dict[str, list[str]]:
    return config.CARD_FAMILIES

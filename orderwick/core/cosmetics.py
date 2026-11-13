"""Unlockable looks: board themes and card styles. No pygame dependency.

Rules (config.BOARD_THEMES / CARD_STYLES): None = always available, "all_trophies" = every achievement unlocked,
anything else = the id of the achievement that unlocks it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import config
from .achievements import ACHIEVEMENTS, BY_ID

BOARD, CARDS = "board", "cards"

# Items that come from the server (see online/content.py): rule "item:<code>" is unlocked when the code is owned.
OWNED: set[str] = set()
ITEM_INFO: dict[str, str] = {}


@dataclass(frozen=True)
class Look:
    kind: str                 # BOARD or CARDS
    id: str
    name: str
    rule: str | None


def looks(kind: str) -> list[Look]:
    table = config.BOARD_THEMES if kind == BOARD else config.CARD_STYLES
    return [Look(kind, i, n, r) for i, n, r in table]


def default_id(kind: str) -> str:
    return looks(kind)[0].id


def is_unlocked(rule: str | None, unlocked_trophies) -> bool:
    if rule is None:
        return True
    if rule.startswith("item:"):
        return rule[5:] in OWNED
    if rule == "all_trophies":
        return all(a.id in unlocked_trophies for a in ACHIEVEMENTS)
    return rule in unlocked_trophies


def requirement(rule: str | None) -> str:
    """Short text that tells the player how to unlock a look."""
    if rule is None:
        return ""
    if rule.startswith("item:"):
        return ITEM_INFO.get(rule[5:]) or "From the shop"
    if rule == "all_trophies":
        return "Unlock every trophy"
    a = BY_ID.get(rule)
    return f"Trophy: {a.name} - {a.desc}" if a else f"Trophy: {rule}"


def resolve(kind: str, wanted: str, unlocked_trophies) -> str:
    """The id to really use: the wanted one if it exists and is unlocked, otherwise the default."""
    for look in looks(kind):
        if look.id == wanted and is_unlocked(look.rule, unlocked_trophies):
            return look.id
    return default_id(kind)

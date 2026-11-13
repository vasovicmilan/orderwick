"""A small event bus (the base for achievements).

The game sends events (e.g. "round_won") and anyone can subscribe:

    app.events.subscribe("round_won", lambda **d: print(d))
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., None]) -> None:
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    def emit(self, event: str, **data) -> None:
        for handler in list(self._handlers[event]):
            handler(**data)

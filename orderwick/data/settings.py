"""Player settings (sound): stored in JSON."""
from __future__ import annotations

from .. import config
from .storage import JsonStore


class Settings:
    def __init__(self, store: JsonStore | None = None):
        self.store = store or JsonStore("settings.json")
        self.data = self.store.load(dict(config.DEFAULT_SETTINGS))
        for key, default in config.DEFAULT_SETTINGS.items():           # repair broken values
            value = self.data.get(key, default)
            if isinstance(default, bool):
                self.data[key] = bool(value)
            elif isinstance(default, str):
                self.data[key] = value if isinstance(value, str) and value else default
            else:
                try:
                    self.data[key] = max(0, min(100, int(value)))
                except (TypeError, ValueError):
                    self.data[key] = default

    def save(self) -> None:
        self.store.save(self.data)

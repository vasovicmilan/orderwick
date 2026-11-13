"""Saving data to a JSON file in the user directory."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .. import config


def default_data_dir() -> Path:
    base = _base_dir()
    return base / "dev" if config.DEV else base            # developer mode never touches the real save files


def _base_dir() -> Path:
    override = os.environ.get("ORDERWICK_HOME")
    if override:
        return Path(override)
    try:
        import pygame
        path = pygame.system.get_pref_path(config.ORG_NAME, config.APP_NAME)
        if path:
            return Path(path)
    except Exception:       # pygame without the system module or without a video driver
        pass
    return Path.home() / f".{config.ORG_NAME}"


class JsonStore:
    def __init__(self, filename: str, directory: Path | None = None):
        self.path = (directory or default_data_dir()) / filename

    def load(self, default: dict) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return json.loads(json.dumps(default))
        if not isinstance(data, dict):
            return json.loads(json.dumps(default))
        for key, value in default.items():
            data.setdefault(key, json.loads(json.dumps(value)))
        return data

    def save(self, data: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

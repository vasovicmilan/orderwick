"""Error log: crash.log in the data folder (so you can see what happened when the game "crashes")."""
from __future__ import annotations

import time
import traceback
from pathlib import Path


def log_path() -> Path:
    from ..data.storage import default_data_dir
    return default_data_dir() / "crash.log"


def log_error(where: str, exc: BaseException | None = None) -> None:
    """Writes an error (with traceback) and never raises by itself."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {where}\n")
            if exc is not None:
                f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass

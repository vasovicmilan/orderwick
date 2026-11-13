"""Background tasks (so the window does not freeze while a board is built or a solution is checked)."""
from __future__ import annotations

import threading
from typing import Any, Callable


class BackgroundTask:
    def __init__(self, fn: Callable[..., Any], *args: Any):
        self.result: Any = None
        self.error: BaseException | None = None
        self.done = False
        self._thread = threading.Thread(target=self._run, args=(fn, args), daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = 30.0) -> None:
        self._thread.join(timeout)

    def _run(self, fn, args) -> None:
        try:
            self.result = fn(*args)
        except BaseException as exc:      # passed on to the main thread
            self.error = exc
        finally:
            self.done = True

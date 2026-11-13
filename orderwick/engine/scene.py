"""Scenes (screens) and their management."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from .app import App


class Scene:
    """Base class of screens. `transparent=True` -> the screen below is still drawn (overlay)."""

    transparent = False

    def __init__(self, app: "App"):
        self.app = app

    def on_enter(self) -> None: ...
    def on_exit(self) -> None: ...
    def on_resume(self) -> None: ...
    def on_quit(self) -> None:
        """Called for every screen on the stack when the application closes (window X, Quit...)."""
        return None

    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


class SceneManager:
    def __init__(self, app: "App"):
        self.app = app
        self._stack: list[Scene] = []

    @property
    def current(self) -> Scene | None:
        return self._stack[-1] if self._stack else None

    def __len__(self) -> int:
        return len(self._stack)

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)
        scene.on_enter()

    def pop(self) -> None:
        if not self._stack:
            return
        self._stack.pop().on_exit()
        if self._stack:
            self._stack[-1].on_resume()
        else:
            self.app.quit()

    def replace(self, scene: Scene) -> None:
        if self._stack:
            self._stack.pop().on_exit()
        self.push(scene)

    def reset(self, scene: Scene) -> None:
        while self._stack:
            self._stack.pop().on_exit()
        self.push(scene)

    def notify_quit(self) -> None:
        for scene in reversed(self._stack):
            scene.on_quit()

    # ---- petlja ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.current:
            self.current.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current:
            self.current.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        start = len(self._stack) - 1
        while start > 0 and self._stack[start].transparent:
            start -= 1
        for scene in self._stack[max(start, 0):]:
            scene.draw(surface)

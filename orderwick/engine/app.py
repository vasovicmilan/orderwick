"""Application: window, main loop, scenes, resources, events."""
from __future__ import annotations

from pathlib import Path

import pygame

from .assets import AssetManager
from .events import EventBus
from .scene import Scene, SceneManager


class App:
    def __init__(self, title: str, size: tuple[int, int], sprites_dir: Path,
                 min_size: tuple[int, int] = (640, 480), fps: int = 60, icon: Path | None = None):
        pygame.display.init()                 # not pygame.init(): the mixer is NOT started here (sound has its own process)
        pygame.font.init()
        pygame.display.set_caption(title)
        self.min_size = min_size
        self.fps = fps
        self._set_icon(icon)
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.assets = AssetManager(sprites_dir)
        self.events = EventBus()
        self.scenes = SceneManager(self)
        self.running = False
        self.fullscreen = False
        self._windowed_size = size

    @staticmethod
    def _set_icon(icon: Path | None) -> None:
        """Window / taskbar icon (must come before set_mode); a missing icon is not an error."""
        if icon is None:
            return
        try:
            pygame.display.set_icon(pygame.image.load(str(icon)))
        except (FileNotFoundError, pygame.error):
            pass

    def on_shutdown(self) -> None:
        """Hook: clean up before pygame.quit() (subclasses override)."""

    def update_overlay(self, dt: float) -> None: ...

    def draw_overlay(self, surface: pygame.Surface) -> None: ...

    def quit(self) -> None:
        self.running = False

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self._windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)

    def _on_resize(self, size: tuple[int, int]) -> None:
        w, h = size
        if not self.fullscreen and (w < self.min_size[0] or h < self.min_size[1]):
            self.screen = pygame.display.set_mode(
                (max(w, self.min_size[0]), max(h, self.min_size[1])), pygame.RESIZABLE)
        else:
            self.screen = pygame.display.get_surface()

    def run(self, first_scene: Scene) -> None:
        self.running = True
        self.scenes.reset(first_scene)
        while self.running:
            dt = min(self.clock.tick(self.fps) / 1000.0, 0.1)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif event.type == pygame.VIDEORESIZE:
                    self._on_resize(event.size)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                else:
                    self.scenes.handle_event(event)
            self.scenes.update(dt)
            self.update_overlay(dt)
            self.scenes.draw(self.screen)
            self.draw_overlay(self.screen)
            pygame.display.flip()
        self.scenes.notify_quit()
        try:
            self.on_shutdown()                      # stop sound etc. BEFORE pygame.quit()
        except Exception as exc:                    # shutting down must never crash
            from .logs import log_error
            log_error("on_shutdown failed", exc)
        pygame.quit()

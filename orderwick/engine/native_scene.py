"""A scene drawn on a NATIVE surface (pixel art) and then scaled to the window by an integer factor.

The whole screen (frames, buttons, letters) gets the same "pixel" as the board. The mouse is converted to native
coordinates; scenes write `paint(canvas)` and `on_event(event)` and work only in native pixels.
The smallest native area is 320x200, so every layout must fit into it.
"""
from __future__ import annotations

import pygame

from .. import config
from .scene import Scene

MIN_NATIVE = (320, 200)


def native_scale(size: tuple[int, int]) -> int:
    return max(1, min(size[0] // MIN_NATIVE[0], size[1] // MIN_NATIVE[1]))


class NativeScene(Scene):
    scale = 1
    native_size = MIN_NATIVE

    def _update_size(self, size: tuple[int, int]) -> None:
        self.scale = native_scale(size)
        self.native_size = (max(1, size[0] // self.scale), max(1, size[1] // self.scale))

    def handle_event(self, event: pygame.event.Event) -> None:
        self._update_size(self.app.screen.get_size())
        if hasattr(event, "pos"):
            data = dict(event.dict)
            data["pos"] = (event.pos[0] // self.scale, event.pos[1] // self.scale)
            event = pygame.event.Event(event.type, data)
        self.on_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        self._update_size(surface.get_size())
        canvas = pygame.Surface(self.native_size)
        canvas.fill(config.COLOR_BG)
        self.paint(canvas)
        surface.fill(config.COLOR_BG)
        if self.scale == 1:
            surface.blit(canvas, (0, 0))
        else:
            surface.blit(pygame.transform.scale(canvas, (canvas.get_width() * self.scale,
                                                         canvas.get_height() * self.scale)), (0, 0))

    # ---- for subclasses ------------------------------------------------------------------------
    def on_event(self, event: pygame.event.Event) -> None: ...
    def paint(self, canvas: pygame.Surface) -> None: ...

    @property
    def kit(self):
        kit = getattr(self.app, "_wood_kit", None)
        if kit is None:
            from ..view.wood_kit import WoodKit
            kit = self.app._wood_kit = WoodKit(self.app.assets)
        return kit

"""About: the game, the author, credits and links."""
from __future__ import annotations

import webbrowser

import pygame

from .. import config
from ..engine.native_scene import NativeScene
from ..engine.ui import Button, FocusGroup
from ..view.wood_kit import CREAM, GOLD, TAN
from .common import full_panel

BLURB = ("A cozy card-sorting puzzle. Sort the fruit into columns, reveal hidden cards, unlock new cards "
         "and collect trophies. Easy boards first, a real challenge at the finale.")


def real_links() -> list[tuple[str, str]]:
    """Only the links the author actually entered (the placeholder example.com is skipped)."""
    return [(n, u) for n, u in config.LINKS if "example.com" not in u]


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


class AboutScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        buttons = [Button(name, lambda u=url: open_url(u)) for name, url in real_links()]
        buttons.append(Button("Back", self.app.scenes.pop))
        self.group = FocusGroup(buttons)

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.scenes.pop()
                return
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):         # the buttons are in a row
                self.group._move(1 if event.key == pygame.K_RIGHT else -1)
                return
        self.group.handle_event(event)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "About", (nw // 2, 12), GOLD, "midtop", big=True)
        n = len(self.group.widgets)
        bw = min(96, (panel.w - 24 - 4 * (n - 1)) // n)
        total = n * bw + (n - 1) * 4
        x = nw // 2 - total // 2
        y = panel.bottom - 8 - 16
        for w in self.group.widgets:
            w.rect = pygame.Rect(x, y, bw, 16)
            x += bw + 4
        self.group.draw(canvas, kit)
        box = pygame.Rect(panel.x + 8, 32, panel.w - 16, y - 4 - 32)
        kit.draw_inset(canvas, box)
        inner = box.w - 14
        ty = box.y + 7
        kit.text(canvas, f"{config.APP_NAME}  v{config.VERSION}", (box.x + 7, ty), GOLD)
        ty += 12
        for line in kit.wrap(BLURB, inner, body=True):
            kit.text(canvas, line, (box.x + 7, ty), CREAM, shadow=False, body=True)
            ty += 9
        ty += 5
        kit.text(canvas, "Made by", (box.x + 7, ty), TAN, shadow=False)
        kit.text(canvas, config.AUTHOR_NAME, (box.x + 7 + 64, ty), CREAM)
        ty += 14
        for credit in config.CREDITS:
            for line in kit.wrap(credit, inner, body=True):
                if ty + 8 <= box.bottom - 4:
                    kit.text(canvas, line, (box.x + 7, ty), TAN, shadow=False, body=True)
                ty += 9

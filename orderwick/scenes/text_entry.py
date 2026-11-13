"""A one-line text entry (used for the online nickname)."""
from __future__ import annotations

from typing import Callable

import pygame

from .. import config
from ..engine.native_scene import NativeScene
from ..view.wood_kit import CREAM, GOLD, TAN
from .common import centered


class TextEntryScene(NativeScene):
    def __init__(self, app, title: str, hint: str, initial: str, on_ok: Callable[[str], None], max_len: int = config.NAME_MAX_LEN,
                 box_w: int = 124, upper: bool = False):
        super().__init__(app)
        self.title, self.hint, self.on_ok, self.max_len = title, hint, on_ok, max_len
        self.box_w, self.upper = box_w, upper
        self.text = initial
        self.t = 0.0

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            text = self.text.strip()
            if text:
                self.app.scenes.pop()
                self.on_ok(text)
        elif event.key == pygame.K_ESCAPE:
            self.app.scenes.pop()
        elif event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.key == pygame.K_v and event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META):
            self._paste()
        elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_len:
            self.text += event.unicode.upper() if self.upper else event.unicode

    def _paste(self) -> None:
        """Ctrl+V: long things like an activation key are easier to paste than to type. Silently ignored where the clipboard is unavailable."""
        try:
            import pygame.scrap
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            raw = pygame.scrap.get_text()
        except Exception:                                        # no clipboard on this platform / video driver
            return
        text = "".join(ch for ch in str(raw or "").strip() if ch.isprintable())
        if self.upper:
            text = text.upper()
        self.text = (self.text + text)[: self.max_len]

    def update(self, dt: float) -> None:
        self.t += dt

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = centered(nw, nh, 260, 118 if self.upper else 108)
        kit.draw_panel(canvas, panel)
        cx, y = panel.centerx, panel.y + 10
        kit.text(canvas, self.title, (cx, y), GOLD, "midtop", big=True)
        for i, line in enumerate(kit.wrap(self.hint, panel.w - 24, body=True)[:2]):
            kit.text(canvas, line, (cx, y + 24 + i * 9), TAN, "midtop", shadow=False, body=True)
        box = pygame.Rect(0, 0, self.box_w, 18)
        box.midtop = (cx, y + 46)
        kit.draw_inset(canvas, box)
        cursor = "_" if int(self.t * 2) % 2 == 0 else " "
        kit.text(canvas, self.text + cursor, (box.x + 6, box.y + 5), CREAM, shadow=False)
        hints = ["Enter = save   Esc = cancel"] + (["Ctrl+V = paste"] if self.upper else [])
        for i, line in enumerate(reversed(hints)):               # one short line each, so nothing sticks out of the panel
            kit.text(canvas, line, (cx, panel.bottom - 8 - i * 10), TAN, "midbottom", shadow=False)

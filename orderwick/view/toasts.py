"""Notifications (toasts) over all screens: an achievement unlocked / a new card. Drawn natively, then scaled."""
from __future__ import annotations

import pygame

from ..core.achievements import BY_ID
from ..engine.native_scene import native_scale
from .achievement_art import achievement_icon
from .wood_kit import GOLD, TAN, WoodKit

SHOW_TIME = 4.0
SLIDE = 0.35


class ToastManager:
    def __init__(self, app):
        self.app = app
        self.queue: list[dict] = []
        self.current: dict | None = None
        self.t = 0.0
        app.events.subscribe("achievement_unlocked", self._ach)
        app.events.subscribe("card_unlocked", self._card)
        app.events.subscribe("cosmetic_unlocked", self._cosmetic)
        app.events.subscribe("challenge_done", self._challenge)

    def _ach(self, id: str, **_):
        a = BY_ID[id]
        self.queue.append({"kind": "ach", "title": "ACHIEVEMENT", "text": a.name, "id": id})

    def _challenge(self, done: int = 0, **_):
        self.queue.append({"kind": "look", "title": "DAILY CHALLENGE", "text": f"DONE  {done}/3 TODAY", "name": "daily"})

    def _card(self, name: str, **_):
        self.queue.append({"kind": "card", "title": "NEW CARD!", "text": "", "name": name})

    def _cosmetic(self, kind: str, name: str, **_):
        title = "NEW BOARD!" if kind == "board" else "NEW CARDS!"
        self.queue.append({"kind": "look", "title": title, "text": name, "name": name})

    def update(self, dt: float) -> None:
        if self.current is None and self.queue:
            self.current, self.t = self.queue.pop(0), 0.0
            self.app.events.emit("toast_shown", kind=self.current["kind"])
        elif self.current is not None:
            self.t += dt
            if self.t >= SHOW_TIME:
                self.current = None

    def draw(self, surface: pygame.Surface) -> None:
        cur = self.current
        if cur is None:
            return
        kit = getattr(self.app, "_wood_kit", None) or WoodKit(self.app.assets)
        self.app._wood_kit = kit
        S = native_scale(surface.get_size())
        w, h = 150, 30
        canvas = pygame.Surface((w, h), pygame.SRCALPHA)
        kit.draw_panel(canvas, pygame.Rect(0, 0, w, h))
        if cur["kind"] == "ach":
            icon = achievement_icon(self.app.assets, cur["id"])
        elif cur["kind"] == "look":
            icon = kit.icons["trophy"]
        else:
            icon = self.app.assets.sprite(cur["name"])
        canvas.blit(icon, (8, (h - icon.get_height()) // 2))
        kit.text(canvas, cur["title"], (30, 8), TAN, shadow=False)
        kit.text(canvas, cur["text"] or cur["name"].upper(), (30, 17), GOLD)
        scaled = pygame.transform.scale(canvas, (w * S, h * S))
        slide = min(1.0, self.t / SLIDE, (SHOW_TIME - self.t) / SLIDE)
        y = int(-h * S + (h * S + 6 * S) * max(0.0, slide))
        surface.blit(scaled, ((surface.get_width() - w * S) // 2, y))

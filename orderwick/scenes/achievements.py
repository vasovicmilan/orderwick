"""Achievements and the card collection (two tabs, scroll with arrows / mouse wheel)."""
from __future__ import annotations

import pygame

from .. import config
from ..core.achievements import ACHIEVEMENTS
from ..core.collection import Collection
from ..engine.audio import audio
from ..engine.native_scene import NativeScene
from ..engine.tasks import BackgroundTask
from ..view.achievement_art import achievement_icon
from ..view.wood_kit import CREAM, DISABLED, GOLD, GOOD, TAN
from .common import full_panel

TABS = ["Achievements", "Cards"]
ROW_H = 20
FAMILY_NAMES = {"grape": "GRAPES", "apple": "APPLES", "pear": "PEARS", "cherry": "CHERRIES", "berry": "BERRIES",
                "curved": "CURVED", "carrot": "CARROTS", "beet": "ROOTS", "round": "ROUND",
                "dotted": "DOTTED", "sunflower": "SUNFLOWER", "watermelon": "MELON"}


class AchievementsScene(NativeScene):
    def __init__(self, app, tab: int = 0):
        super().__init__(app)
        self.tab = tab
        self.scroll = [0, 0]
        self.tab_rects: list[pygame.Rect] = []
        self.sync: BackgroundTask | None = None
        self.sync_note = ""
        online = getattr(app, "online", None)
        if online is not None and online.enabled and not online.is_agent:     # the server's list is the real one
            self.sync = BackgroundTask(online.sync_progress)
            if getattr(app, "content", None) is not None:
                app.content.sync_async(force=True)             # new items that came with achievements

    # ---- the list: the server's when online, otherwise the built-in one ---------------------------------
    def _server(self) -> dict:
        online = getattr(self.app, "online", None)
        return online.cached_progress if online is not None and online.enabled and not online.is_agent else {}

    def _entries(self) -> list[dict]:
        server = self._server().get("achievements")
        if server:
            return [{"id": a["code"], "name": a["title"], "desc": a["description"], "cur": a["progress"], "target": a["threshold"],
                     "done": a["unlocked"], "reward": a["reward"]} for a in server]
        tracker = self.app.progress.tracker
        return [{"id": a.id, "name": a.name, "desc": a.desc, "cur": tracker.progress(a)[0], "target": a.target,
                 "done": a.id in tracker.unlocked, "reward": 0} for a in ACHIEVEMENTS]

    def update(self, dt: float) -> None:
        if self.sync is not None and self.sync.done:
            self.sync_note = "" if self.sync.error is None else "Offline: showing the last saved list."
            self.sync = None

    # ---- geometry ----------------------------------------------------------------------
    def _box(self) -> pygame.Rect:
        nw, nh = self.native_size
        panel = full_panel(nw, nh)
        return pygame.Rect(panel.x + 8, 50, panel.w - 16, panel.bottom - 50 - 22)

    def _rows(self) -> int:
        return len(self._entries()) if self.tab == 0 else len(config.CARD_FAMILIES)

    def _visible(self) -> int:
        return max(1, (self._box().h - 6) // ROW_H)

    def _scroll_by(self, step: int) -> None:
        top = max(0, self._rows() - self._visible())
        self.scroll[self.tab] = max(0, min(top, self.scroll[self.tab] + step))

    # ---- events -------------------------------------------------------------------------
    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.app.scenes.pop()
            elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                self.tab = (self.tab + 1) % len(TABS)
                audio.play("ui_move")
            elif event.key == pygame.K_LEFT:
                self.tab = (self.tab - 1) % len(TABS)
                audio.play("ui_move")
            elif event.key == pygame.K_DOWN:
                self._scroll_by(1)
            elif event.key == pygame.K_UP:
                self._scroll_by(-1)
            elif event.key == pygame.K_PAGEDOWN:
                self._scroll_by(self._visible())
            elif event.key == pygame.K_PAGEUP:
                self._scroll_by(-self._visible())
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(event.pos) and i != self.tab:
                    self.tab = i
                    audio.play("ui_click")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            self._scroll_by(-1 if event.button == 4 else 1)

    # ---- drawing -------------------------------------------------------------------------
    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        entries = self._entries()
        got = sum(1 for e in entries if e["done"])
        kit.text(canvas, "Trophies", (nw // 2, 12), GOLD, "midtop", big=True)
        self.tab_rects = []
        widths = [112, 84]
        x = nw // 2 - (sum(widths) + 4) // 2
        for i, title in enumerate(TABS):
            r = pygame.Rect(x, 30, widths[i], 16)
            x += widths[i] + 4
            self.tab_rects.append(r)
            kit.draw_button(canvas, r, title, "hover" if i == self.tab else "normal")
        box = self._box()
        kit.draw_inset(canvas, box)
        old = canvas.get_clip()
        canvas.set_clip(box.inflate(-6, -6))
        if self.tab == 0:
            self._paint_achievements(canvas, kit, box)
        else:
            self._paint_cards(canvas, kit, box)
        canvas.set_clip(old)
        if self._rows() > self._visible():
            top = max(1, self._rows() - self._visible())
            frac = self.scroll[self.tab] / top
            bar = pygame.Rect(box.right - 5, box.y + 4 + int(frac * (box.h - 20)), 2, 12)
            canvas.fill(TAN, bar)
        coll = self.app.progress.collection
        server = self._server()
        coins = f"  {server['currency']['balance']} {server['currency']['name']}" if server.get("currency") else ""
        summary = (f"{got}/{len(entries)} achievements{coins}{'  ...' if self.sync else ''}" if self.tab == 0
                   else f"{len(coll.unlocked)}/{Collection.total()} cards")
        kit.text(canvas, summary, (panel.x + 10, panel.bottom - 8), TAN, "bottomleft", shadow=False)
        kit.text(canvas, self.sync_note or "Esc = back", (panel.right - 10, panel.bottom - 8), TAN, "bottomright", shadow=False)

    def _paint_achievements(self, canvas, kit, box) -> None:
        first = self.scroll[0]
        y = box.y + 5
        for a in self._entries()[first:first + self._visible() + 1]:
            done = a["done"]
            canvas.blit(achievement_icon(self.app.assets, a["id"], locked=not done), (box.x + 6, y + 2))
            kit.text(canvas, a["name"], (box.x + 28, y + 1), GOLD if done else DISABLED, shadow=done)
            kit.text(canvas, a["desc"], (box.x + 28, y + 11), CREAM if done else TAN, shadow=False, body=True)
            label = "DONE" if done else f"{a['cur']}/{a['target']}"
            kit.text(canvas, label, (box.right - 10, y + 1), GOOD if done else TAN, "topright", shadow=False)
            if a["reward"]:
                kit.text(canvas, f"+{a['reward']}", (box.right - 10, y + 11), GOLD if not done else TAN, "topright", shadow=False)
            y += ROW_H

    def _paint_cards(self, canvas, kit, box) -> None:
        coll = self.app.progress.collection
        first = self.scroll[1]
        y = box.y + 5
        for family in list(config.CARD_FAMILIES)[first:first + self._visible() + 1]:
            names = config.CARD_FAMILIES[family]
            kit.text(canvas, FAMILY_NAMES.get(family, family), (box.x + 7, y + 6), TAN, shadow=False)
            x = box.x + 92
            for name in names:
                shown = name if coll.is_unlocked(name) else config.HIDDEN_SPRITE
                canvas.blit(self.app.assets.sprite(shown), (x, y + 1))
                x += 19
            nxt = coll.next_threshold(family)
            pts = coll.points.get(family, 0)
            text = f"{pts}/{nxt}" if nxt else ("MAX" if len(names) > 1 else "-")
            kit.text(canvas, text, (box.right - 10, y + 6), CREAM if nxt else GOOD, "topright", shadow=False)
            y += ROW_H

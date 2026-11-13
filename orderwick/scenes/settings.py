"""Settings: music and effects on/off + volume."""
from __future__ import annotations

import pygame

from ..engine.audio import audio
from ..engine.native_scene import NativeScene
from ..core import cosmetics
from ..engine.ui import Button, Choice, FocusGroup, Slider, Toggle
from ..view.wood_kit import BAD, GOLD, TAN
from .common import full_panel


class SettingsScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        s = app.settings.data
        self.music_on = Toggle("Music", s["music_on"], lambda v: self._set("music_on", v), "music", "mute")
        self.music_vol = Slider("Music vol", s["music_vol"], lambda v: self._set("music_vol", v))
        self.sfx_on = Toggle("Effects", s["sfx_on"], lambda v: self._set("sfx_on", v), "sound", "mute")
        self.sfx_vol = Slider("Effects vol", s["sfx_vol"], self._sfx_volume)
        self.board = self._look_choice("Board", cosmetics.BOARD, "board_theme")
        self.cards = self._look_choice("Cards", cosmetics.CARDS, "card_style")
        self.group = FocusGroup([self.music_on, self.music_vol, self.sfx_on, self.sfx_vol, self.board, self.cards,
                                 Button("Back", self.app.scenes.pop)])

    def _look_choice(self, label: str, kind: str, key: str) -> Choice:
        looks = {look.id: look for look in cosmetics.looks(kind)}
        return Choice(label, [(look.id, look.name) for look in looks.values()], self.app.settings.data[key],
                      lambda look_id: self._choose(key, look_id),
                      lambda look_id: self.app.progress.look_unlocked(kind, look_id),
                      lambda look_id: cosmetics.requirement(looks[look_id].rule))

    def _choose(self, key: str, look_id: str) -> None:
        self._set(key, look_id)
        self.app.apply_appearance()

    def _set(self, key: str, value) -> None:
        self.app.settings.data[key] = value
        self.app.settings.save()
        audio.apply()

    def _sfx_volume(self, value: int) -> None:
        self._set("sfx_vol", value)
        audio.play_pair(4)                          # test tone: you hear the new volume right away

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.scenes.pop()
            return
        self.group.handle_event(event)

    def paint(self, canvas: pygame.Surface) -> None:
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "Settings", (nw // 2, 13), GOLD, "midtop", big=True)
        self.group.layout_column(nw // 2, 34, min(240, nw - 40), 16, 2)
        self.group.draw(canvas, kit)
        y = self.group.widgets[-1].rect.bottom + 6
        focused = self.group.widgets[self.group.focus]
        hint = focused.hint() if isinstance(focused, Choice) else ""
        text = hint or "Sounds vary slightly every time and the music rests between songs, so it never gets tiring."
        color = BAD if hint else TAN
        if y + 9 < panel.bottom - 6:
            for line in kit.wrap(text, min(240, nw - 40), body=True):
                if y + 8 > panel.bottom - 6:
                    break
                kit.text(canvas, line, (nw // 2, y), color, "midtop", shadow=False, body=True)
                y += 9

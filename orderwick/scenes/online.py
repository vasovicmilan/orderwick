"""The Online screen: consent (what is sent), the account, nickname, export and delete."""
from __future__ import annotations

import webbrowser

import pygame

from .. import config
from ..engine.native_scene import NativeScene
from ..engine.tasks import BackgroundTask
from ..engine.ui import Button, FocusGroup
from ..online.client import OnlineError
from ..view.wood_kit import BAD, CREAM, GOLD, GOOD, TAN
from .common import full_panel

ACTIVATE_TEXT = [
    "Online features need the activation key from your account on the Orderwick website (free account, key appears after you confirm your e-mail).",
    "The key and a random install id are sent once to the server, which checks the key and counts how many computers use it.",
    "The game itself works fully offline without a key.",
]

CONSENT_TEXT = [
    "Online features are OFF until you turn them on. The game works fully offline.",
    "If you turn them on, the game creates an anonymous player (a random id and a key kept on this computer) and sends:",
    "- your activation key and a random install id (to check the key)",
    "- the nickname you choose",
    "- your game version and operating system",
    "- the moves, time and score of boards you solve in Campaign, Hard mode and the Daily board, so the server can check them",
    "Nothing else leaves your computer: no name, email, location, device id or files. No ads, no tracking.",
    "Your nickname, score, level, time and moves are public on the leaderboard. You can export or delete everything at any time.",
]


class OnlineScene(NativeScene):
    def __init__(self, app):
        super().__init__(app)
        self.online = app.online
        self.status = ""
        self.status_bad = False
        self.task: BackgroundTask | None = None
        self.after = None
        self.me: dict | None = None
        self.update_note = ""
        self._built = None
        self.scroll = 0                    # text area scroll (native px); the consent text is longer than a small window
        self._max_scroll = 0
        self.group = FocusGroup([])
        self._rebuild()
        if self.online.enabled:
            self._run(self.online.refresh_me, self._got_me, "")

    def _update_size(self, size: tuple[int, int]) -> None:
        """This screen is mostly text: one integer step smaller than the other screens gives it room to show all of it."""
        super()._update_size(size)
        if self.scale > 1:
            self.scale -= 1
            self.native_size = (max(1, size[0] // self.scale), max(1, size[1] // self.scale))

    # ---- background work ----------------------------------------------------------------------------------
    def _run(self, fn, done, busy: str = "Working...") -> None:
        if self.task is not None:
            return
        self.status, self.status_bad = busy, False
        self.task, self.after = BackgroundTask(fn), done

    def update(self, dt: float) -> None:
        if self.task is not None and self.task.done:
            task, self.task = self.task, None
            if task.error is not None:
                err = task.error
                self.status = err.message if isinstance(err, OnlineError) else "Something went wrong."
                self.status_bad = True
            else:
                self.status = ""
                if self.after:
                    self.after(task.result)
            self._rebuild()

    def _got_me(self, me) -> None:
        self.me = me

    # ---- actions ---------------------------------------------------------------------------------------------
    def _consent(self) -> None:
        self._run(self.online.enable, lambda _n: self._run(self.online.refresh_me, self._got_me, "Connecting..."), "Creating your online account...")

    def _activate(self) -> None:
        from .text_entry import TextEntryScene

        def ok(code: str) -> None:
            self._run(lambda: self.online.activate(code), lambda name: setattr(self, "status", f"Activated for {name}."), "Checking the key...")
        self.app.scenes.push(TextEntryScene(self.app, "Activation key", "From your account page: OW-XXXX-XXXX-XXXX", "", ok,
                                            max_len=17, box_w=170, upper=True))

    def _account(self) -> None:
        webbrowser.open(f"{self.online.url}/account")

    def _forget_key(self) -> None:
        self.online.deactivate()
        self.online.disable()
        self.me = None
        self._rebuild()

    def _off(self) -> None:
        self.online.disable()
        self.me = None
        self._rebuild()

    def _board(self) -> None:
        from .online_leaderboard import OnlineLeaderboardScene
        self.app.scenes.push(OnlineLeaderboardScene(self.app))

    def _nickname(self) -> None:
        from .text_entry import TextEntryScene

        def ok(name: str) -> None:
            self._run(lambda: self.online.rename(name), lambda _n: None, "Saving...")
        self.app.scenes.push(TextEntryScene(self.app, "Nickname", "3-12 letters, digits, space, _ or -. No real names, please.",
                                            self.online.nickname, ok))

    def _export(self) -> None:
        self._run(self.online.export_to_file, lambda path: setattr(self, "status", f"Saved to {path}"), "Exporting...")

    def _delete(self) -> None:
        from .confirm import ConfirmScene
        self.app.scenes.push(ConfirmScene(self.app, "Delete online account?", "Your online scores and account are erased from the server. Your offline progress stays.",
                                          "Yes, delete", lambda: self._run(self.online.erase, lambda _n: setattr(self, "me", None), "Deleting...")))

    def _privacy(self) -> None:
        webbrowser.open(f"{self.online.url}/privacy")

    def _download(self) -> None:
        webbrowser.open(f"{self.online.url}/download")

    # ---- layout ------------------------------------------------------------------------------------------------
    def _state(self) -> str:
        if not self.online.available:
            return "unavailable"
        if self.online.enabled:
            return "on"
        return "off" if self.online.activated else "locked"

    def _rebuild(self) -> None:
        state = self._state()
        busy = self.task is not None
        if state == "on":
            buttons = [Button("Online leaderboard", self._board, enabled=not busy)]
            if not self.online.is_agent:
                buttons += [Button("Change nickname", self._nickname, enabled=not busy),
                            Button("Export my data", self._export, enabled=not busy),
                            Button("Delete account", self._delete, enabled=not busy),
                            Button("Turn off online", self._off, enabled=not busy)]
            buttons += [Button("Privacy policy", self._privacy), Button("Back", self.app.scenes.pop)]
        elif state == "locked":
            buttons = [Button("Enter activation key", self._activate, enabled=not busy), Button("Open my account page", self._account),
                       Button("How to get a key", self._download), Button("Not now", self.app.scenes.pop)]
        elif state == "off":
            buttons = [Button("Turn on online", self._consent, enabled=not busy), Button("Privacy policy", self._privacy),
                       Button("Forget key", self._forget_key, enabled=not busy), Button("Not now", self.app.scenes.pop)]
        else:
            buttons = [Button("Back", self.app.scenes.pop)]
        self.group = FocusGroup(buttons)
        self._built = state

    def on_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.task is None:
            self.app.scenes.pop()
            return
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * 18)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_HOME, pygame.K_END):
            step = {pygame.K_PAGEUP: -72, pygame.K_PAGEDOWN: 72, pygame.K_HOME: -10**6, pygame.K_END: 10**6}[event.key]
            self._scroll_by(step)
            return
        self.group.handle_event(event)

    def _scroll_by(self, delta: int) -> None:
        self.scroll = max(0, min(self._max_scroll, self.scroll + delta))

    def paint(self, canvas: pygame.Surface) -> None:
        if self._built != self._state():
            self._rebuild()
        nw, nh = self.native_size
        kit = self.kit
        panel = full_panel(nw, nh)
        kit.draw_panel(canvas, panel)
        kit.text(canvas, "Online", (nw // 2, 12), GOLD, "midtop", big=True)
        width = min(340, nw - 36)
        state = self._state()
        if state == "unavailable":
            lines = ["This build is offline only. Online features (leaderboard, daily board) are not set up yet."]
        elif state == "locked":
            lines = ACTIVATE_TEXT
        elif state == "off":
            lines = ([f"Key accepted for {self.online.account_name}."] if self.online.account_name else ["Key accepted."]) + CONSENT_TEXT
        else:
            who = "AI agent" if self.online.is_agent else "Player"
            lines = [f"{who}: {self.online.nickname or '...'}"]
            if self.me:
                for mode, label in (("hard", "Hard mode"), ("campaign", "Campaign")):
                    s = (self.me.get("stats") or {}).get(mode) or {}
                    rank = f"  rank #{s['rank']}" if s.get("rank") else ""
                    lines.append(f"{label}: best {s.get('best', 0)}{rank}")
            lines.append("Boards you solve in Campaign, Hard mode and the Daily board are checked by the server and ranked.")
        wrapped = [kit.wrap(text, width, body=True) for text in lines]
        text_h = sum(9 * len(w) + 2 for w in wrapped)
        # buttons are anchored at the bottom; the status line sits right above them; the text gets what is left and scrolls
        n = len(self.group.widgets)
        bh, gap = 14, 2
        btn_top = panel.bottom - 8 - n * (bh + gap)
        status_h = 12 if self.status else 0
        area = pygame.Rect(panel.x + 6, 30, panel.w - 12, max(20, btn_top - status_h - 4 - 30))
        self._max_scroll = max(0, text_h - area.h)
        self.scroll = min(self.scroll, self._max_scroll)
        old_clip = canvas.get_clip()
        canvas.set_clip(area)
        y = area.y - self.scroll
        for block in wrapped:
            for line in block:
                kit.text(canvas, line, (nw // 2, y), CREAM, "midtop", shadow=False, body=True)
                y += 9
            y += 2
        canvas.set_clip(old_clip)
        if self._max_scroll:                                     # a thin scroll bar on the right edge of the text area
            track = pygame.Rect(area.right - 3, area.y, 2, area.h)
            canvas.fill(config.COLOR_BG, track)
            thumb_h = max(8, track.h * area.h // text_h)
            thumb_y = track.y + (track.h - thumb_h) * self.scroll // self._max_scroll
            canvas.fill(GOLD, (track.x, thumb_y, 2, thumb_h))
        if self.status:
            kit.text(canvas, self.status[:70], (nw // 2, btn_top - status_h - 1), BAD if self.status_bad else GOOD, "midtop", shadow=False, body=True)
        self.group.layout_column(nw // 2, btn_top, min(168, nw - 40), bh, gap)
        self.group.draw(canvas, kit)

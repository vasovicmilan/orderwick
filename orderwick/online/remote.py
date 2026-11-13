"""One ranked run that lives on the server.

The server hands out the boards and re-plays every solved board with the real rules before it counts. This class keeps
the thin client side of that: it asks for boards, records nothing itself (the Round already keeps a move log), submits a
solved board in the background and applies the server's score. If anything goes wrong the run silently continues as a normal
offline run ("unranked") and the player is told once.
"""
from __future__ import annotations

import random

from .. import config
from ..core.board import Board
from ..core.daily_board import base_cards
from ..core.models import LevelSpec
from ..core.palette import pick_palette
from ..core.session import Round
from ..engine.tasks import BackgroundTask
from .client import OnlineError


def round_from_payload(payload: dict, unlocked, daily: bool) -> Round:
    s = payload["spec"]
    spec = LevelSpec(s["cols"], s["free"], s["k"], s.get("reveal", 1))
    board = Board.from_kinds(payload["kinds"], spec.free, spec.k, spec.reveal)
    # The palette is only cosmetic. The daily board uses the cards everybody has, so it looks the same for everyone.
    palette = pick_palette(random.Random(payload["seed"]), spec.types, base_cards() if daily else unlocked)
    return Round(spec, payload["level"], board, palette)


class RemoteRun:
    def __init__(self, client, mode_id: str, start_level: int):
        self.client = client
        self.mode_id = mode_id
        self.start_level = start_level
        self.run_id: str | None = None
        self.broken = False                  # True = continue offline, unranked
        self._notice = ""                    # one message for the player, delivered once by poll()
        self._submit: BackgroundTask | None = None
        self._applied = True
        self._score: int | None = None       # server's score, applied when the next board starts
        self.rank: int | None = None
        self.on_progress = None              # called with what the server says this board earned (achievements, coins)

    # ---- helpers ----------------------------------------------------------------------------------------
    @property
    def ranked(self) -> bool:
        return self.run_id is not None and not self.broken

    def _break(self, message: str) -> None:
        self.broken = True
        self._notice = message

    def _fail(self, err: OnlineError, what: str) -> None:
        if err.code == "daily_done":
            self._break("You already solved today's board online. This attempt is not ranked.")
        elif err.code == "network":
            self._break(f"Offline: {what} This run is not ranked.")
        else:
            self._break(f"{what} {err.message} This run is not ranked.")

    # ---- boards (called from a background thread by GameSession.create_round) -----------------------------
    def next_round(self, session, level: int) -> Round | None:
        daily = self.mode_id == "daily"
        try:
            if self.broken:
                return None
            cur = session.round
            if self.run_id is None:                                            # first board of the run
                resp = self.client.start_run(self.mode_id, self.start_level)
                self.run_id = resp["runId"]
                payload = resp["round"]
                self._notice = "RANKED ONLINE: the server checks your result."
            elif cur is not None and cur.won:                                   # next level
                if self._submit is not None:
                    self._submit.join()
                    if self._submit.error is not None and not self._applied:       # poll() has not looked at it yet
                        self._applied = True
                        err = self._submit.error
                        self._fail(err if isinstance(err, OnlineError) else OnlineError("bad_response", "Unexpected answer."),
                                   "Your result could not be verified.")
                if self.broken:
                    return None
                payload = self.client.round(self.run_id)["round"]
            else:                                                                # new board (R, R) or daily restart
                resp = self.client.restart(self.run_id, list(cur.log) if cur is not None else [])
                self._score = resp.get("score")
                payload = resp["round"]
            return round_from_payload(payload, session.unlocked, daily)
        except OnlineError as err:
            self._fail(err, "Could not get a board from the server.")
            return None

    def apply(self, session) -> None:
        """Main thread, when a board starts: the server decides the level and the score."""
        rnd = session.round
        if self.ranked and rnd is not None:
            session.level = rnd.level
            if self._score is not None:
                session.score = self._score
        self._score = None

    # ---- results --------------------------------------------------------------------------------------------
    def submit_async(self, session, rnd: Round) -> None:
        if not self.ranked:
            return
        events, elapsed = list(rnd.log), float(rnd.elapsed)
        self._applied = False

        def work():
            for attempt in (0, 1):
                try:
                    return self.client.submit_round(self.run_id, events, elapsed)
                except OnlineError as err:
                    if err.code != "network" or attempt:
                        raise
        self._submit = BackgroundTask(work)

    def poll(self, session) -> str:
        """Main thread, every frame. Applies the server's verdict once it arrives; returns a message to show (or "")."""
        notice, self._notice = self._notice, ""
        task = self._submit
        if task is not None and task.done and not self._applied:
            self._applied = True
            if task.error is not None:
                self._fail(task.error if isinstance(task.error, OnlineError) else OnlineError("bad_response", "Unexpected answer."),
                           "Your result could not be verified.")
                notice = self._notice or notice
                self._notice = ""
            else:
                resp = task.result or {}
                rnd = session.round
                if rnd is not None:
                    rnd.gain = int(resp.get("gain", rnd.gain))
                session.score = int(resp.get("score", session.score))
                self.rank = resp.get("rank")
                if self.mode_id == "daily" and self.rank:
                    notice = f"Daily board rank today: #{self.rank}"
                earned = resp.get("progress")
                if earned and self.on_progress is not None:
                    self.on_progress(earned)
                if earned and earned.get("coins"):
                    notice = (notice + "  " if notice else "") + f"+{earned['coins']} coins"
                names = [i["name"] for a in (earned or {}).get("unlocked", []) for i in a.get("items", [])]
                if names:
                    notice = (notice + "  " if notice else "") + "New: " + ", ".join(names)
        return notice

    def finish_async(self) -> None:
        if not self.ranked:
            return
        run_id = self.run_id
        submit = self._submit

        def work():
            if submit is not None:
                submit.join()
            try:
                self.client.finish(run_id)          # run-count achievements are picked up by the next progress sync (Trophies screen)
            except OnlineError:
                pass                       # the score is already on the server; closing the run is a courtesy
        BackgroundTask(work)

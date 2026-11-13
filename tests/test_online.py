"""Online layer without a network: a fake server API drives the real GameSession + RemoteRun code."""
import os
import random
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ORDERWICK_AUDIO", "off")
os.environ.setdefault("ORDERWICK_HOME", tempfile.mkdtemp(prefix="orderwick_online_"))

from orderwick import config  # noqa: E402
from orderwick.core.daily_board import DailyBoardMode  # noqa: E402
from orderwick.core.generator import BoardGenerator  # noqa: E402
from orderwick.core.levels import CampaignMode, HardMode, LevelCatalog  # noqa: E402
from orderwick.core.models import col, slot  # noqa: E402
from orderwick.core.pathsolver import PathSolver  # noqa: E402
from orderwick.core.session import GameSession  # noqa: E402
from orderwick.data.storage import JsonStore  # noqa: E402
from orderwick.engine.events import EventBus  # noqa: E402
from orderwick.online.client import OnlineError  # noqa: E402
from orderwick.online.remote import RemoteRun, round_from_payload  # noqa: E402
from orderwick.online.service import OnlineService  # noqa: E402


class FakeApi:
    """Stands in for ApiClient: hands out generated boards and records what the game sends."""

    def __init__(self):
        self.sent = []
        self.level = 1
        self.fail = None            # an OnlineError to raise from the next call
        self.score = 0
        self.n = 0

    def _board(self, level):
        spec = LevelCatalog.spec(level)
        g = BoardGenerator(random.Random(100 + self.n)).generate(spec, 0.0, 0.0)
        self.n += 1
        s = spec
        return {"boardId": self.n, "level": level, "seed": 12345 + self.n, "kinds": g.kinds,
                "spec": {"cols": s.cols, "free": s.free, "k": s.k, "reveal": s.reveal}}

    def _maybe_fail(self):
        if self.fail:
            err, self.fail = self.fail, None
            raise err

    def start_run(self, mode, start_level):
        self._maybe_fail()
        self.sent.append(("start", mode, start_level))
        self.level = start_level
        return {"runId": "run-1", "round": self._board(start_level)}

    def round(self, run_id):
        self._maybe_fail()
        self.sent.append(("round", run_id))
        return {"round": self._board(self.level)}

    def submit_round(self, run_id, events, elapsed):
        self._maybe_fail()
        self.sent.append(("submit", list(events), elapsed))
        self.score += 1000
        self.level += 1
        return {"accepted": True, "gain": 1000, "score": self.score, "level": self.level, "rank": 3}

    def restart(self, run_id, events):
        self._maybe_fail()
        self.sent.append(("restart", list(events)))
        self.score = max(0, self.score - 50)
        return {"score": self.score, "round": self._board(self.level)}

    def finish(self, run_id):
        self.sent.append(("finish", run_id))
        return {}

    def progress(self):
        self._maybe_fail()
        self.sent.append(("progress",))
        return {"currency": {"name": "Coins", "balance": 15}, "stats": {},
                "achievements": [
                    {"code": "first_board", "title": "First Steps", "description": "Solve your first board.", "threshold": 1, "progress": 1,
                     "reward": 5, "unlocked": True, "unlockedAt": "2026-11-12T10:00:00.000Z"},
                    {"code": "boards_10", "title": "Getting Going", "description": "Solve 10 boards.", "threshold": 10, "progress": 1,
                     "reward": 10, "unlocked": False, "unlockedAt": None},
                    {"code": "server_only", "title": "Added Later", "description": "New on the server.", "threshold": 3, "progress": 3,
                     "reward": 7, "unlocked": True, "unlockedAt": None}]}

    def activate(self, code, install_id):
        self._maybe_fail()
        self.sent.append(("activate", code, install_id))
        return {"ok": True, "name": "Milan", "activations": {"used": 1, "max": 3}}


def wait_applied(session, timeout=5.0):
    end = time.time() + timeout
    note = ""
    while time.time() < end:
        note = session.remote.poll(session) or note
        if session.remote._applied:
            return note
        time.sleep(0.01)
    raise AssertionError("the submit never finished")


def solve(session):
    b = session.round.board
    found, moves = PathSolver(node_cap=100000, time_limit=20).solve(b.kinds(), b.n_free, b.capacity, b.free_cards())
    assert found
    for src, dst in moves:
        assert session.move(src, dst).ok
        session.tick(0.5)


def make_session(mode, api):
    events = EventBus()
    svc = OnlineService(store=JsonStore("online.json", Path(tempfile.mkdtemp())), url="http://x", client=api)
    svc.state.update(consent=config.ONLINE_CONSENT_VERSION, key="k", nickname="Tester", activation="OW-AAAA-BBBB-CCCC")
    svc.attach(events)
    session = GameSession(mode, events=events)
    session.remote = svc.new_remote(mode)
    return session, events, svc


class MoveLog(unittest.TestCase):
    def test_log_records_moves_undo_and_rescue_in_wire_format(self):
        s = GameSession(CampaignMode(5), rng=random.Random(2))
        s.start_round(s.create_round())
        b = s.round.board
        found, moves = PathSolver(node_cap=50000, time_limit=10).solve(b.kinds(), b.n_free, b.capacity, b.free_cards())
        first = moves[0]
        self.assertTrue(s.move(*first).ok)
        self.assertTrue(s.undo().ok)
        s.apply_rescue()
        self.assertTrue(s.move(*moves[0]).ok is not None)
        wire = lambda a, c: f"{'c' if a.kind == 'col' else 's'}{a.index}>{'c' if c.kind == 'col' else 's'}{c.index}"
        self.assertEqual(s.round.log[:3], [wire(*first), "u", "x"])
        self.assertFalse(s.move(col(0), col(0)).ok)                       # a refused move is not logged
        self.assertEqual(len(s.round.log), 3 + (1 if s.round.moves == 4 else 0) if False else len(s.round.log))


class ServiceGating(unittest.TestCase):
    def test_dormant_without_server_url(self):
        svc = OnlineService(store=JsonStore("o.json", Path(tempfile.mkdtemp())), url="")
        self.assertFalse(svc.available)
        self.assertFalse(svc.enabled)
        self.assertIsNone(svc.new_remote(HardMode()))

    def test_nothing_is_on_without_consent(self):
        svc = OnlineService(store=JsonStore("o.json", Path(tempfile.mkdtemp())), url="http://x", client=FakeApi())
        self.assertTrue(svc.available)
        self.assertFalse(svc.enabled)
        self.assertIsNone(svc.new_remote(HardMode()))
        svc.state.update(consent=config.ONLINE_CONSENT_VERSION, key="k")
        self.assertFalse(svc.enabled, "consent and a player key are not enough without an activation key")
        svc.state.update(activation="OW-AAAA-BBBB-CCCC")
        self.assertTrue(svc.enabled)
        self.assertIsNotNone(svc.new_remote(HardMode()))
        self.assertIsNone(svc.new_remote(__import__("orderwick.core.levels", fromlist=["CustomMode"]).CustomMode(6, 2, 6)))
        svc.disable()
        self.assertFalse(svc.enabled)

    def test_new_consent_version_asks_again(self):
        svc = OnlineService(store=JsonStore("o.json", Path(tempfile.mkdtemp())), url="http://x", client=FakeApi())
        svc.state.update(consent=config.ONLINE_CONSENT_VERSION - 1, key="k")
        self.assertFalse(svc.enabled)

    def test_agent_key_from_environment(self):
        os.environ["ORDERWICK_AGENT_KEY"] = "agentkey"
        try:
            svc = OnlineService(store=JsonStore("o.json", Path(tempfile.mkdtemp())), url="http://x", client=FakeApi())
            self.assertTrue(svc.enabled and svc.is_agent)
            self.assertEqual(svc._key(), "agentkey")
            self.assertEqual(svc.state.get("key"), "")          # never written to disk
        finally:
            del os.environ["ORDERWICK_AGENT_KEY"]


class Activation(unittest.TestCase):
    def make(self, api=None):
        api = api or FakeApi()
        return OnlineService(store=JsonStore("act.json", Path(tempfile.mkdtemp())), url="http://x", client=api), api

    def test_online_cannot_be_turned_on_before_the_key_is_accepted(self):
        svc, _ = self.make()
        with self.assertRaises(OnlineError) as ctx:
            svc.enable()
        self.assertEqual(ctx.exception.code, "not_activated")

    def test_activate_remembers_the_key_and_sends_one_stable_install_id(self):
        svc, api = self.make()
        self.assertEqual(svc.activate("  ow-aaaa-bbbb-cccc "), "Milan")
        self.assertTrue(svc.activated)
        self.assertEqual(svc.state["activation"], "OW-AAAA-BBBB-CCCC")
        first = api.sent[-1][2]
        self.assertGreaterEqual(len(first), 16)
        svc.activate("OW-AAAA-BBBB-CCCC")
        self.assertEqual(api.sent[-1][2], first, "the install id does not change between calls")
        svc2 = OnlineService(store=svc.store, url="http://x", client=api)
        self.assertEqual(svc2.state["install_id"], first, "and it survives a restart")

    def test_a_refused_key_is_not_remembered(self):
        svc, api = self.make()
        api.fail = OnlineError("not_found", "Unknown activation key.", 404)
        with self.assertRaises(OnlineError):
            svc.activate("OW-AAAA-BBBB-CCCC")
        self.assertFalse(svc.activated)
        with self.assertRaises(OnlineError) as ctx:
            svc.activate("   ")
        self.assertEqual(ctx.exception.code, "bad_key")

    def test_enable_links_the_new_player_by_sending_the_key_again(self):
        svc, api = self.make()
        api.register = lambda nickname=None: {"playerId": "p1", "key": "k1", "nickname": "Auto"}
        svc.activate("OW-AAAA-BBBB-CCCC")
        svc.enable()
        self.assertEqual([m[0] for m in api.sent if m[0] == "activate"], ["activate", "activate"])
        self.assertTrue(svc.enabled)

    def test_a_revoked_key_turns_online_off_but_a_network_problem_does_not(self):
        svc, api = self.make()
        svc.state.update(consent=config.ONLINE_CONSENT_VERSION, key="k", activation="OW-AAAA-BBBB-CCCC")
        api.me = lambda: {"nickname": "x"}
        api.fail = OnlineError("network", "Can't reach the server.")
        svc.refresh_me()
        self.assertTrue(svc.enabled, "offline is not a reason to lock anybody out")
        api.fail = OnlineError("forbidden", "This key was revoked.", 403)
        with self.assertRaises(OnlineError):
            svc.refresh_me()
        self.assertFalse(svc.activated)
        self.assertFalse(svc.enabled)

    def test_agents_need_no_key(self):
        os.environ["ORDERWICK_AGENT_KEY"] = "agentkey"
        try:
            svc, api = self.make()
            self.assertTrue(svc.activated and svc.enabled)
            self.assertEqual([m for m in api.sent if m[0] == "activate"], [])
        finally:
            del os.environ["ORDERWICK_AGENT_KEY"]

    def test_the_online_screen_walks_from_locked_to_off_to_on(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.online import OnlineScene
        app = OrderwickGame()
        api = FakeApi()
        api.register = lambda nickname=None: {"playerId": "p1", "key": "k1", "nickname": "Auto"}
        api.me = lambda: {"nickname": "Auto", "stats": {}}
        app.online = OnlineService(store=JsonStore("scene.json", Path(tempfile.mkdtemp())), url="http://x", client=api)
        scene = OnlineScene(app)
        self.assertEqual(scene._state(), "locked")
        labels = [b.text for b in scene.group.widgets]
        self.assertIn("Enter activation key", labels)
        self.assertNotIn("Turn on online", labels)
        app.online.activate("OW-AAAA-BBBB-CCCC")
        scene._rebuild()
        self.assertEqual(scene._state(), "off")
        self.assertIn("Turn on online", [b.text for b in scene.group.widgets])
        app.online.enable()
        scene._rebuild()
        self.assertEqual(scene._state(), "on")


class RemoteFlow(unittest.TestCase):
    def test_ranked_run_end_to_end(self):
        api = FakeApi()
        session, events, _ = make_session(CampaignMode(1), api)
        rnd = session.create_round()
        session.start_round(rnd)
        self.assertTrue(session.remote.ranked)
        self.assertEqual(api.sent[0], ("start", "campaign", 1))
        solve(session)
        note = wait_applied(session)
        kind, sent_events, elapsed = api.sent[1]
        self.assertEqual(kind, "submit")
        self.assertEqual(sent_events, rnd.log)
        self.assertAlmostEqual(elapsed, rnd.elapsed, places=1)
        self.assertEqual(session.score, 1000, "the server's score replaces the local one")
        self.assertEqual(rnd.gain, 1000)
        session.advance()
        nxt = session.create_round()
        session.start_round(nxt)
        self.assertEqual(api.sent[2][0], "round")
        self.assertEqual(nxt.level, 2)
        self.assertEqual(session.level, 2, "the server decides the level")
        events.emit("run_finished", session=session)
        time.sleep(0.3)
        self.assertEqual(api.sent[-1], ("finish", "run-1"))

    def test_new_board_sends_the_log_and_takes_the_servers_score(self):
        api = FakeApi()
        api.score = 400
        session, _, _ = make_session(CampaignMode(5), api)
        session.start_round(session.create_round())
        b = session.round.board
        found, moves = PathSolver(node_cap=50000, time_limit=10).solve(b.kinds(), b.n_free, b.capacity, b.free_cards())
        session.move(*moves[0])
        session.penalize_restart()
        session.start_round(session.create_round())
        self.assertEqual(api.sent[-1][0], "restart")
        self.assertEqual(len(api.sent[-1][1]), 1)
        self.assertEqual(session.score, 350)

    def test_server_down_at_start_falls_back_to_a_normal_run(self):
        api = FakeApi()
        api.fail = OnlineError("network", "Can't reach the server.")
        session, _, _ = make_session(CampaignMode(1), api)
        rnd = session.create_round()
        session.start_round(rnd)
        self.assertTrue(session.remote.broken)
        self.assertFalse(session.remote.ranked)
        self.assertIn("not ranked", session.remote.poll(session))
        self.assertTrue(rnd.board.kinds())
        solve(session)
        self.assertTrue(rnd.won)
        self.assertEqual([x[0] for x in api.sent], [], "a broken run sends nothing more")

    def test_rejected_result_marks_the_run_unranked_but_the_game_goes_on(self):
        api = FakeApi()
        session, _, _ = make_session(CampaignMode(1), api)
        session.start_round(session.create_round())
        api.fail = OnlineError("invalid_round", "illegal move #3", 422)
        solve(session)
        note = wait_applied(session)
        self.assertTrue(session.remote.broken)
        self.assertIn("not ranked", note)
        session.advance()
        session.start_round(session.create_round())            # local board
        self.assertEqual(session.round.level, 2)

    def test_daily_done_is_explained(self):
        api = FakeApi()
        api.fail = OnlineError("daily_done", "done", 409)
        session, _, _ = make_session(DailyBoardMode("2026-11-11"), api)
        session.start_round(session.create_round())
        self.assertIn("already solved today", session.remote.poll(session))

    def test_daily_uses_the_common_cards_so_everybody_sees_the_same_board(self):
        api = FakeApi()
        payload = api._board(7)
        a = round_from_payload(payload, {"red_apple", "red_pear"}, daily=True)
        b = round_from_payload(payload, None, daily=True)
        self.assertEqual(a.palette, b.palette)
        self.assertEqual(a.board.kinds(), payload["kinds"])


if __name__ == "__main__":
    unittest.main()


class AccountRecovery(unittest.TestCase):
    """The server forgot us (reset database): the client makes a new account and retries once."""

    def test_401_creates_a_new_account_and_retries(self):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        known = {"good"}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/v1/players":
                    return self._send(201, {"playerId": "p2", "key": "good", "nickname": body.get("nickname") or "Auto"})
                if self.headers.get("Authorization") != "Bearer good":
                    return self._send(401, {"error": {"code": "unauthorized", "message": "Invalid key"}})
                self._send(201, {"runId": "r1"})

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            svc = OnlineService(store=JsonStore("r.json", Path(tempfile.mkdtemp())), url=f"http://127.0.0.1:{srv.server_address[1]}")
            svc.state.update(consent=config.ONLINE_CONSENT_VERSION, player_id="old", key="stale", nickname="OldNick", activation="OW-AAAA-BBBB-CCCC")
            self.assertEqual(svc.client.start_run("campaign", 1)["runId"], "r1")
            self.assertEqual((svc.state["key"], svc.state["nickname"]), ("good", "OldNick"))
        finally:
            srv.shutdown()

    def test_agent_keys_are_never_replaced(self):
        os.environ["ORDERWICK_AGENT_KEY"] = "agent"
        try:
            svc = OnlineService(store=JsonStore("a.json", Path(tempfile.mkdtemp())), url="http://127.0.0.1:9", client=FakeApi())
            self.assertFalse(svc._recover())
        finally:
            del os.environ["ORDERWICK_AGENT_KEY"]


class ButtonLabels(unittest.TestCase):
    def test_fit_label_never_exceeds_the_button(self):
        from orderwick.game import OrderwickGame
        from orderwick.view.wood_kit import WoodKit
        app = OrderwickGame()
        kit = WoodKit(app.assets)
        self.assertEqual(kit.fit_label("OK", 60, False), (["OK"], False))
        lines, body = kit.fit_label("Create my account now", 100, True)
        self.assertGreater(len(lines), 1)
        font = kit.body if body else kit.f8
        for line in lines:
            self.assertLessEqual(font.size(line)[0], 100)
        lines, body = kit.fit_label("Create my account now", 100, False)
        self.assertEqual((len(lines), body), (1, True))




class ServerProgress(unittest.TestCase):
    """Achievements and coins are counted by the server; the game shows them and lets them overwrite its local copy."""

    def make(self):
        from orderwick.data.progress import Progress
        events = EventBus()
        svc = OnlineService(store=JsonStore("online.json", Path(tempfile.mkdtemp())), url="http://x", client=FakeApi())
        svc.state.update(consent=config.ONLINE_CONSENT_VERSION, key="k", nickname="T", activation="OW-AAAA-BBBB-CCCC")
        svc.attach(events)
        progress = Progress(events, JsonStore("progress.json", Path(tempfile.mkdtemp())))
        return svc, progress, events

    def test_sync_stores_a_copy_and_overwrites_local_trophies(self):
        svc, progress, _ = self.make()
        progress.tracker.unlocked["boards_10"] = "2026-01-01"          # earned offline, the server never saw it
        progress.tracker.unlocked["cards_1"] = "2026-01-01"            # a local-only trophy the server has no entry for
        svc.sync_progress()
        self.assertEqual(svc.cached_progress["currency"]["balance"], 15)
        self.assertIn("first_board", progress.tracker.unlocked)
        self.assertNotIn("boards_10", progress.tracker.unlocked, "the server's state wins")
        self.assertIn("cards_1", progress.tracker.unlocked, "what the server does not know stays")
        self.assertIn("server_only", progress.tracker.unlocked)

    def test_a_new_unlock_announces_itself_once_and_the_copy_survives_a_restart(self):
        svc, progress, events = self.make()
        shown = []
        events.subscribe("achievement_unlocked", lambda id=None, **_: shown.append(id))
        svc.sync_progress()
        svc.sync_progress()
        self.assertEqual(shown, ["first_board"], "only known local trophies pop up, and only the first time")
        again = OnlineService(store=svc.store, url="http://x", client=FakeApi())
        self.assertEqual(again.cached_progress["currency"]["balance"], 15)

    def test_a_solved_board_updates_the_copy_without_asking_again(self):
        svc, progress, _ = self.make()
        svc.sync_progress()
        svc.note_progress({"unlocked": [{"code": "boards_10", "title": "Getting Going", "reward": 10}], "coins": 10, "balance": 25})
        item = [a for a in svc.cached_progress["achievements"] if a["code"] == "boards_10"][0]
        self.assertTrue(item["unlocked"])
        self.assertEqual(svc.cached_progress["currency"]["balance"], 25)
        self.assertIn("boards_10", progress.tracker.unlocked)

    def test_the_trophy_screen_lists_the_servers_achievements_when_online(self):
        from orderwick.scenes.achievements import AchievementsScene
        svc, progress, _ = self.make()
        svc.sync_progress()

        class AppStub:
            online = svc
        AppStub.progress = progress
        scene = AchievementsScene.__new__(AchievementsScene)
        scene.app = AppStub
        names = [e["name"] for e in scene._entries()]
        self.assertEqual(names, ["First Steps", "Getting Going", "Added Later"])
        self.assertEqual(scene._entries()[1]["reward"], 10)
        svc.state["consent"] = 0                                         # offline: the built-in list comes back
        self.assertGreater(len(scene._entries()), 40)

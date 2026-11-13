"""Tests for collection, achievements, sound and the new screens. Headless."""
import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ORDERWICK_AUDIO", "off")      # tests never spawn the sound process unless they ask for it
os.environ["ORDERWICK_HOME"] = tempfile.mkdtemp()

import pygame

from orderwick import config
from orderwick.core.achievements import ACHIEVEMENTS, AchievementTracker
from orderwick.core.collection import Collection
from orderwick.core.levels import CampaignMode
from orderwick.core.palette import pick_palette
from orderwick.core.session import GameSession
from orderwick.data.progress import Progress
from orderwick.data.settings import Settings
from orderwick.data.storage import JsonStore
from orderwick.engine.events import EventBus


class CollectionRules(unittest.TestCase):
    def test_base_cards_unlocked_and_total(self):
        c = Collection()
        self.assertEqual(len(c.unlocked), len(config.CARD_FAMILIES))
        for names in config.CARD_FAMILIES.values():
            self.assertTrue(c.is_unlocked(names[0]))
        self.assertEqual(Collection.total(), 38)

    def test_thresholds_match_family_size(self):
        for family, names in config.CARD_FAMILIES.items():
            self.assertEqual(len(Collection.thresholds(family)), len(names) - 1)
        self.assertEqual(Collection.thresholds("beet"), [100])
        self.assertEqual(Collection.thresholds("grape"), [10, 25, 50, 100, 200])

    def test_points_unlock_in_order_and_persist(self):
        c = Collection()
        self.assertEqual(c.add_points("grape", 9), [])
        self.assertEqual(c.add_points("grape", 1), [config.CARD_FAMILIES["grape"][1]])
        self.assertEqual(len(c.add_points("grape", 40)), 2)                # 50 -> prag 25 i 50
        again = Collection(c.to_dict())
        self.assertEqual(again.unlocked, c.unlocked)

    def test_palette_uses_only_unlocked(self):
        c = Collection()
        rng = random.Random(1)
        for _ in range(50):
            pal = pick_palette(rng, 9, c.unlocked)
            self.assertTrue(set(pal) <= c.unlocked)
            self.assertEqual(len(set(pal)), 9)


class ProgressFlow(unittest.TestCase):
    def make(self):
        events = EventBus()
        store = JsonStore("t_progress.json", Path(tempfile.mkdtemp()))
        return events, Progress(events, store), store

    def play_round(self, session):
        """Solves the board using the solution the generator returned."""
        rnd = session.create_round(budget=0.3)
        session.start_round(rnd)
        for src, dst in rnd.solution:
            session.move(src, dst)
        return rnd

    def test_move_reports_reveals_and_pairs(self):
        events = EventBus()
        seen = []
        events.subscribe("move", lambda **d: seen.append(d))
        s = GameSession(CampaignMode(1), events=events, rng=random.Random(3))
        self.play_round(s)
        self.assertTrue(seen)
        self.assertTrue(any(d["revealed"] for d in seen))
        self.assertTrue(any(d["paired"] for d in seen))
        self.assertTrue(s.round.won)

    def test_winning_gives_points_and_achievement(self):
        events, progress, store = self.make()
        got = []
        events.subscribe("achievement_unlocked", lambda id, **_: got.append(id))
        s = GameSession(CampaignMode(1), events=events, rng=random.Random(5), unlocked=progress.collection.unlocked)
        self.play_round(s)
        self.assertIn("first_board", got)
        self.assertGreater(sum(progress.collection.points.values()), 0)
        self.assertEqual(progress.tracker.stats["boards_won"], 1)
        # saved to disk
        reloaded = Progress(EventBus(), store)
        self.assertEqual(reloaded.collection.points, progress.collection.points)
        self.assertIn("first_board", reloaded.tracker.unlocked)

    def test_reveal_points_capped_per_round(self):
        events, progress, _ = self.make()
        s = GameSession(CampaignMode(1), events=events, rng=random.Random(8))
        rnd = s.create_round(budget=0.3)
        s.start_round(rnd)
        k = rnd.spec.k
        for _ in range(5):                                           # the same "reveal" move many times
            events.emit("move", round=rnd, revealed=[0] * k, paired=False)
        family = Collection.family_of(rnd.palette[0])
        self.assertLessEqual(progress.collection.points[family], k)

    def test_unlock_event_and_new_cards_stat(self):
        events, progress, _ = self.make()
        names = []
        events.subscribe("card_unlocked", lambda name, **_: names.append(name))
        progress._add_points("grape", 10)
        self.assertEqual(names, [config.CARD_FAMILIES["grape"][1]])
        self.assertEqual(progress.tracker.stats["new_cards"], 1)

    def test_every_achievement_reachable(self):
        t = AchievementTracker()
        for a in ACHIEVEMENTS:
            t.stats[a.stat] = max(t.stats.get(a.stat, 0), a.target)
        self.assertEqual(len(t.check("2026-01-01")), len(ACHIEVEMENTS))
        self.assertEqual(len({a.id for a in ACHIEVEMENTS}), len(ACHIEVEMENTS))


class SettingsAndAudio(unittest.TestCase):
    def test_settings_sanitized(self):
        store = JsonStore("t_settings.json", Path(tempfile.mkdtemp()))
        store.save({"music_vol": 900, "sfx_vol": "x", "music_on": 0})
        s = Settings(store)
        self.assertEqual(s.data["music_vol"], 100)
        self.assertEqual(s.data["sfx_vol"], config.DEFAULT_SETTINGS["sfx_vol"])
        self.assertIs(s.data["music_on"], False)

    def test_audio_files_load_and_play(self):
        from orderwick.engine.audio import Audio
        a = Audio()
        self.assertTrue(a.init(config.AUDIO_DIR, dict(config.DEFAULT_SETTINGS)))
        for name in ("pick", "place", "pairA", "pairB", "pairC", "column_done", "win", "unlock", "achievement",
                     "ui_move", "invalid"):
            self.assertIn(name, a.sfx)
        for tag in ("pairA", "pairB", "pairC"):
            self.assertEqual(len(a.sfx[tag]), 10)
        self.assertEqual(set(config.SFX_GAIN) - set(a.sfx) - {"pair"}, set())      # every effect has a file and a gain
        self.assertGreater(config.SFX_GAIN["column_done"], config.SFX_GAIN["place"])
        self.assertLess(config.SFX_GAIN["pair"], config.SFX_GAIN["place"] / 2)
        self.assertGreaterEqual(len(a.tracks), 3)
        picks = []
        for _ in range(40):
            snd = a._pick("place")
            picks.append(id(snd))
        self.assertGreater(len(set(picks)), 2)                       # the variants change
        a.play("place")
        a.play_pair(99)
        a.play("column_done")
        a.update(100.0)                                              # krece muzika
        self.assertTrue(a._playing)
        a.settings["music_on"] = False
        a.apply()
        self.assertFalse(a._playing)

    def test_music_bag_has_no_immediate_repeat(self):
        from orderwick.engine.audio import Audio
        a = Audio()
        a.tracks = [Path(f"t{i}.ogg") for i in range(3)]
        order = [a._next_track() for _ in range(30)]
        self.assertTrue(all(x != y for x, y in zip(order, order[1:])))

    def test_audio_icons_match_generator(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mk", Path(config.ROOT_DIR, "tools", "make_audio_icons.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        pygame.init()
        pygame.display.set_mode((1, 1))
        disk = pygame.image.load(str(Path(config.ASSETS_DIR, config.AUDIO_ICONS))).convert_alpha()
        self.assertEqual(pygame.image.tobytes(disk, "RGBA"), pygame.image.tobytes(tool.make_sheet(), "RGBA"))
        self.assertEqual(tool.ORDER, config.AUDIO_ICON_ORDER)


class NewScreens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orderwick.game import OrderwickGame
        cls.app = OrderwickGame()
        cls.app.running = True

    def test_screens_render_at_small_and_large_sizes(self):
        from orderwick.scenes.achievements import AchievementsScene
        from orderwick.scenes.menu import MenuScene
        from orderwick.scenes.settings import SettingsScene
        for size in ((640, 400), (1180, 780), (1920, 1080)):
            self.app.screen = pygame.display.set_mode(size)
            for sc in (MenuScene(self.app), AchievementsScene(self.app), AchievementsScene(self.app, 1),
                       SettingsScene(self.app)):
                sc.draw(self.app.screen)

    def test_settings_toggle_and_slider(self):
        from orderwick.scenes.settings import SettingsScene
        sc = SettingsScene(self.app)
        key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0)
        sc.on_event(key(pygame.K_RETURN))                            # Music: iskljuci
        self.assertFalse(self.app.settings.data["music_on"])
        before = self.app.settings.data["music_vol"]
        sc.on_event(key(pygame.K_DOWN))
        sc.on_event(key(pygame.K_LEFT))
        self.assertEqual(self.app.settings.data["music_vol"], before - 10)
        sc.on_event(key(pygame.K_UP))
        sc.on_event(key(pygame.K_RETURN))                            # opet ukljuci
        self.assertTrue(self.app.settings.data["music_on"])

    def test_ticker_covers_every_card_and_hides_locked(self):
        from orderwick.view.wood_kit import CardTicker
        names = [n for m in config.CARD_FAMILIES.values() for n in m]
        t = CardTicker(names, 176, random.Random(2))
        seen = set(t.queue)
        for _ in range(400):
            t.update(0.5)
            seen |= set(t.queue)
        self.assertEqual(seen, set(names))
        surf = pygame.Surface((200, 40))
        t.draw(surf, self.app.assets, pygame.Rect(10, 5, 176, 22), unlocked=frozenset())

    def test_toast_shows_for_unlock(self):
        self.app.events.emit("card_unlocked", name="blue_grape", family="grape")
        self.app.toasts.update(0.1)
        self.assertEqual(self.app.toasts.current["kind"], "card")
        surf = pygame.Surface((640, 400))
        self.app.toasts.t = 1.0
        self.app.toasts.draw(surf)
        self.app.toasts.update(10.0)
        self.assertIsNone(self.app.toasts.current)


if __name__ == "__main__":
    unittest.main()


class ExtraFeatures(unittest.TestCase):
    def test_column_done_event_and_stat(self):
        events = EventBus()
        done = []
        events.subscribe("move", lambda completed=0, **_: done.append(completed))
        s = GameSession(CampaignMode(1), events=events, rng=random.Random(4))
        rnd = s.create_round(budget=0.3)
        s.start_round(rnd)
        for src, dst in rnd.solution:
            s.move(src, dst)
        self.assertGreaterEqual(sum(done), rnd.board.n_cols - 1)      # one column per type

    def test_more_trophies_and_unique_ids(self):
        self.assertGreaterEqual(len(ACHIEVEMENTS), 35)
        score_ones = [a for a in ACHIEVEMENTS if a.stat == "best_score"]
        self.assertGreaterEqual(len(score_ones), 6)

    def test_premium_card_reward(self):
        old = dict(config.PREMIUM_CARDS)
        config.PREMIUM_CARDS["gold_grape"] = "first_board"
        try:
            events = EventBus()
            p = Progress(events, JsonStore("t_premium.json", Path(tempfile.mkdtemp())))
            got = []
            events.subscribe("card_unlocked", lambda name, **_: got.append(name))
            p.tracker.bump("boards_won")
            p._finish_event()
            self.assertIn("gold_grape", got)
            self.assertIn("gold_grape", p.collection.unlocked)
            pal = pick_palette(random.Random(1), 9, p.collection.unlocked)
            self.assertIn("gold_grape", pal)
            self.assertEqual(Collection.total(), 39)
        finally:
            config.PREMIUM_CARDS.clear()
            config.PREMIUM_CARDS.update(old)

    def test_body_font_has_lowercase_and_about_renders(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.about import AboutScene, real_links
        app = OrderwickGame()
        kit = __import__("orderwick.view.wood_kit", fromlist=["WoodKit"]).WoodKit(app.assets)
        self.assertEqual(kit.body.size("Hello")[1], 8)
        self.assertNotEqual(pygame.image.tobytes(kit.body.render("abc", False, (255, 255, 255)), "RGBA"),
                            pygame.image.tobytes(kit.body.render("ABC", False, (255, 255, 255)), "RGBA"))
        self.assertEqual([n for n, _ in real_links()], ["Contact"])   # example.com placeholders are not shown
        for size in ((640, 400), (1180, 780)):
            app.screen = pygame.display.set_mode(size)
            AboutScene(app).draw(app.screen)


class Robustness(unittest.TestCase):
    def test_audio_errors_never_propagate_and_disable_after_three(self):
        from orderwick.engine.audio import Audio
        a = Audio()
        self.assertTrue(a.init(config.AUDIO_DIR, dict(config.DEFAULT_SETTINGS)))
        orig = pygame.mixer.music.load
        pygame.mixer.music.load = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            for _ in range(6):
                a._gap = 0
                a._playing = False
                a.update(1.0)                                   # must not raise
        finally:
            pygame.mixer.music.load = orig
        self.assertFalse(a.ready)                               # after 3 errors the sound is off
        a.play("place")                                         # i dalje bezbedno
        a.update(1.0)

    def test_no_audio_switch(self):
        from orderwick.engine.audio import Audio
        os.environ["ORDERWICK_NO_AUDIO"] = "1"
        try:
            self.assertFalse(Audio().init(config.AUDIO_DIR, dict(config.DEFAULT_SETTINGS)))
        finally:
            del os.environ["ORDERWICK_NO_AUDIO"]

    def test_hud_adapts_to_height_without_overlap(self):
        from orderwick.engine.assets import AssetManager
        from orderwick.view.hud_view import MIN_HUD_HEIGHT, HudButton, HudData, HudView, tier_for
        pygame.init()
        pygame.display.set_mode((1, 1))
        hud = HudView(AssetManager(config.SPRITES_DIR))
        data = HudData("CAMPAIGN", "LEVEL 1", ["5x7 TYPES 4", "FREE SLOTS 4"], "0", "00:50", "0",
                       [("x " * 80, config.COLOR_TAN)],
                       [HudButton("UNDO MOVE", "undo"), HudButton("RESCUE", "rescue"),
                        HudButton("NEW BOARD", "restart"), HudButton("PAUSE", "pause")])
        tiers = set()
        for h in range(MIN_HUD_HEIGHT, 330, 7):
            tiers.add(tier_for(h))
            surf = hud.render(data, h)
            self.assertEqual(surf.get_height(), h)
            rects = HudView.button_rects(h, 4)
            self.assertGreaterEqual(rects[0].y, 100)                          # ispod brojki
            self.assertLessEqual(rects[-1].bottom, h)
            for r1, r2 in zip(rects, rects[1:]):
                self.assertLess(r1.bottom, r2.y)
        self.assertEqual(tiers, {"full", "mid", "tight"})

    def test_fit_scale_keeps_hud_tall_enough(self):
        from orderwick.view.board_view import BoardView
        from orderwick.view.hud_view import MIN_HUD_HEIGHT
        for w, h in ((1180, 780), (900, 620), (1920, 1080), (1280, 720)):
            s = BoardView.fit_scale(5, 6, w, h, extra_native_w=config.HUD_WIDTH, min_native_h=MIN_HUD_HEIGHT)
            self.assertGreaterEqual(h // s, MIN_HUD_HEIGHT if s > 1 else 0)


class Holes(unittest.TestCase):
    def test_every_card_sprite_exists_and_is_16x16(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        names = [n for m in config.CARD_FAMILIES.values() for n in m] + [config.HIDDEN_SPRITE, config.BLOCKED_SPRITE]
        for n in names:
            img = pygame.image.load(str(Path(config.SPRITES_DIR, f"{n}.png")))
            self.assertEqual(img.get_size(), (16, 16), n)

    def test_missing_sprite_falls_back_to_question_mark(self):
        from orderwick.engine.assets import AssetManager
        pygame.display.set_mode((1, 1))
        a = AssetManager(config.SPRITES_DIR)
        img = a.sprite("no_such_card")
        self.assertEqual(img.get_size(), (16, 16))

    def test_columns_cannot_be_farmed_with_undo(self):
        events = EventBus()
        p = Progress(events, JsonStore("t_cols.json", Path(tempfile.mkdtemp())))
        s = GameSession(CampaignMode(1), events=events, rng=random.Random(2))
        rnd = s.create_round(budget=0.3)
        s.start_round(rnd)
        for _ in range(50):
            events.emit("move", round=rnd, completed=1, revealed=[], paired=False)
        self.assertEqual(p.tracker.stats["columns_done"], rnd.board.n_cols - 1)

    def test_odd_sized_trophy_art_is_normalised(self):
        from orderwick.engine.assets import AssetManager
        from orderwick.view import achievement_art
        pygame.display.set_mode((1, 1))
        d = Path(tempfile.mkdtemp())
        pygame.image.save(pygame.Surface((32, 32)), str(d / "first_board.png"))
        old = config.ASSETS_DIR
        try:
            config.ASSETS_DIR = d.parent
            (d.parent / "achievements").mkdir(exist_ok=True)
            pygame.image.save(pygame.Surface((32, 32)), str(d.parent / "achievements" / "first_board.png"))
            img = achievement_art.achievement_icon(AssetManager(config.SPRITES_DIR if False else old / "sprites"),
                                                   "first_board")
            self.assertEqual(img.get_size(), (16, 16))
        finally:
            config.ASSETS_DIR = old


class Naming(unittest.TestCase):
    def test_sprite_names_are_colour_then_type_and_exist(self):
        names = [n for m in config.CARD_FAMILIES.values() for n in m]
        for n in names:
            self.assertRegex(n, r"^[a-z]+_[a-z]+$", n)
            self.assertTrue(Path(config.SPRITES_DIR, f"{n}.png").exists(), n)
        self.assertEqual(len(names), len(set(names)))
        for special in (config.HIDDEN_SPRITE, config.BLOCKED_SPRITE):
            self.assertTrue(Path(config.SPRITES_DIR, f"{special}.png").exists())
        stray = {p.stem for p in Path(config.SPRITES_DIR).glob("*.png")} - set(names) - {config.HIDDEN_SPRITE, config.BLOCKED_SPRITE}
        self.assertEqual(stray, set())                              # no unused or misspelled files

    def test_old_family_keys_in_saves_are_migrated(self):
        c = Collection({"points": {"lump": 30, "brownround": 12, "grape": 5}})
        self.assertEqual(c.points["berry"], 30)
        self.assertEqual(c.points["round"], 12)
        self.assertEqual(c.points["grape"], 5)

    def test_hud_title_fits_for_two_digit_levels(self):
        from orderwick.engine.assets import AssetManager
        from orderwick.view.hud_view import HudButton, HudData, HudView, W, MARGIN
        pygame.init()
        pygame.display.set_mode((1, 1))
        hud = HudView(AssetManager(config.SPRITES_DIR))
        data = HudData("HARD MODE", "LEVEL 15", ["10x13 TYPES 9", "FREE SLOTS 1"], "0", "00:00", "0", [],
                       [HudButton("PAUSE", "pause")])
        surf = hud.render(data, 260)
        # nothing may be drawn in the right margin (x >= W - MARGIN) except the panel frame itself
        right = surf.subsurface((W - MARGIN, 14, MARGIN - 6, 40))
        plain = hud.render(HudData("HARD MODE", "", ["", ""], "0", "00:00", "0", [], [HudButton("PAUSE", "pause")]), 260)
        ref = plain.subsurface((W - MARGIN, 14, MARGIN - 6, 40))
        self.assertEqual(pygame.image.tobytes(right, "RGBA"), pygame.image.tobytes(ref, "RGBA"))


class Shutdown(unittest.TestCase):
    def test_audio_shutdown_is_clean_and_idempotent(self):
        from orderwick.engine.audio import Audio
        a = Audio()
        self.assertTrue(a.init(config.AUDIO_DIR, dict(config.DEFAULT_SETTINGS)))
        a.update(100.0)                                          # music starts
        a.shutdown()
        self.assertFalse(pygame.mixer.get_init())
        self.assertFalse(a.ready)
        a.shutdown()                                             # second call: nothing happens
        a.play("place")
        a.update(1.0)

    def test_app_run_closes_audio_before_pygame_quit(self):
        import threading
        from orderwick.engine.audio import audio
        from orderwick.game import OrderwickGame
        from orderwick.scenes.menu import MenuScene
        app = OrderwickGame()
        threading.Timer(0.5, lambda: pygame.event.post(pygame.event.Event(pygame.QUIT))).start()
        app.run(MenuScene(app))                                  # returns after the QUIT event
        self.assertFalse(audio.ready)


class RemoteAudioProcess(unittest.TestCase):
    """The sound runs in its own process: its death must never reach the game."""

    def _start(self):
        from orderwick.engine.audio import RemoteAudio
        old = os.environ.pop("ORDERWICK_AUDIO", None)
        try:
            r = RemoteAudio()
            r.init(config.AUDIO_DIR, dict(config.DEFAULT_SETTINGS))
        finally:
            if old is not None:
                os.environ["ORDERWICK_AUDIO"] = old
        return r

    def test_worker_plays_and_shuts_down_fast(self):
        import time
        r = self._start()
        self.assertTrue(r.ready)
        r.play("place")
        r.play_pair(3)
        r.settings["music_vol"] = 10
        r.apply()
        time.sleep(1.0)
        proc = r._proc
        t = time.monotonic()
        r.shutdown()
        self.assertLess(time.monotonic() - t, 2.0)
        self.assertFalse(proc.is_alive())
        self.assertFalse(r.ready)
        r.shutdown()                                             # idempotent

    def test_game_survives_killed_worker(self):
        import os as _os
        import signal
        import time
        r = self._start()
        self.assertTrue(r.ready)
        time.sleep(0.5)
        _os.kill(r._proc.pid, signal.SIGKILL)
        time.sleep(0.3)
        for _ in range(5):
            r.play("place")
            r.play_pair(2)
            r.update(1.5)                                        # must not raise
        self.assertFalse(r.ready)
        r.shutdown()


class DevMode(unittest.TestCase):
    def test_dev_unlocks_everything_and_uses_separate_folder(self):
        from orderwick.core.achievements import ACHIEVEMENTS
        from orderwick.engine.events import EventBus
        from orderwick.data import storage
        from orderwick.data.progress import Progress
        old = config.DEV
        config.DEV = True
        try:
            self.assertEqual(storage.default_data_dir().name, "dev")
            pr = Progress(EventBus(), storage.JsonStore("dev_progress_test.json", Path(tempfile.mkdtemp())))
            self.assertEqual(len(pr.collection.unlocked), Collection.total())
            self.assertEqual(len(pr.tracker.unlocked), len(ACHIEVEMENTS))
            self.assertTrue(pr.look_unlocked("board", "emerald") and pr.look_unlocked("cards", "gold"))
        finally:
            config.DEV = old
        self.assertNotEqual(storage.default_data_dir().name, "dev")

    def test_dev_is_off_by_default(self):
        self.assertFalse(config.DEV)


class Looks(unittest.TestCase):
    def test_rules(self):
        from orderwick.core import cosmetics
        from orderwick.core.achievements import ACHIEVEMENTS
        none: set = set()
        self.assertTrue(cosmetics.is_unlocked(None, none))
        self.assertFalse(cosmetics.is_unlocked("all_trophies", none))
        self.assertFalse(cosmetics.is_unlocked("all_trophies", {a.id for a in ACHIEVEMENTS[:-1]}))
        self.assertTrue(cosmetics.is_unlocked("all_trophies", {a.id for a in ACHIEVEMENTS}))
        self.assertTrue(cosmetics.is_unlocked("score_100k", {"score_100k"}))
        self.assertEqual(cosmetics.resolve("board", "emerald", none), "wood")            # locked -> default
        self.assertEqual(cosmetics.resolve("board", "nonsense", none), "wood")
        self.assertEqual(cosmetics.resolve("cards", "gold", {"score_100k"}), "gold")
        self.assertIn("Trophy", cosmetics.requirement("score_100k"))

    def test_every_registered_look_has_its_files(self):
        for look_id, _name, _rule in config.BOARD_THEMES[1:]:
            self.assertTrue(Path(config.THEMES_DIR, look_id, "board", "board.png").exists(), look_id)
            for f in ("panel", "inset", "button", "divider"):
                self.assertTrue(Path(config.THEMES_DIR, look_id, "hud", f"{f}.png").exists(), (look_id, f))
        for look_id, _name, _rule in config.CARD_STYLES[1:]:
            for n in [c for m in config.CARD_FAMILIES.values() for c in m]:
                self.assertTrue(Path(config.CARD_STYLES_DIR, look_id, f"{n}.png").exists(), (look_id, n))

    def test_asset_manager_switches_and_falls_back(self):
        from orderwick.engine.assets import AssetManager
        pygame.display.set_mode((1, 1))
        a = AssetManager(config.SPRITES_DIR)
        classic = pygame.image.tobytes(a.sprite("red_apple"), "RGBA")
        board0 = pygame.image.tobytes(a.image(config.BOARD_IMAGE), "RGBA")
        a.set_card_style(config.CARD_STYLES_DIR / "gold")
        a.set_theme(config.THEMES_DIR / "emerald")
        self.assertNotEqual(pygame.image.tobytes(a.sprite("red_apple"), "RGBA"), classic)
        self.assertNotEqual(pygame.image.tobytes(a.image(config.BOARD_IMAGE), "RGBA"), board0)
        self.assertEqual(a.image(config.BOARD_IMAGE).get_size(), (193, 217))
        # a theme that does not provide a file falls back to the default look
        partial = Path(tempfile.mkdtemp())
        (partial / "board").mkdir()
        pygame.image.save(a.image(config.BOARD_IMAGE), str(partial / "board" / "board.png"))
        a2 = AssetManager(config.SPRITES_DIR)
        a2.set_theme(partial)
        self.assertEqual(pygame.image.tobytes(a2.image(config.HUD_ICONS), "RGBA"),
                         pygame.image.tobytes(pygame.image.load(str(config.ASSETS_DIR / config.HUD_ICONS)).convert_alpha(), "RGBA"))
        a.set_theme(None)
        a.set_card_style(None)
        self.assertEqual(pygame.image.tobytes(a.sprite("red_apple"), "RGBA"), classic)

    def test_board_assembly_works_in_every_theme(self):
        from orderwick.engine.assets import AssetManager
        from orderwick.view.board_skin import BoardSkin
        pygame.display.set_mode((1, 1))
        for look_id, _n, _r in config.BOARD_THEMES:
            a = AssetManager(config.SPRITES_DIR)
            if look_id != config.BOARD_THEMES[0][0]:
                a.set_theme(config.THEMES_DIR / look_id)
            skin = BoardSkin(a.image(config.BOARD_IMAGE))
            for cols, k in ((5, 4), (10, 12)):
                self.assertEqual(skin.build(cols, k).get_size(), BoardSkin.native_size(cols, k))

    def test_unlocking_all_trophies_announces_the_emerald_board_once(self):
        from orderwick.core.achievements import ACHIEVEMENTS
        events = EventBus()
        p = Progress(events, JsonStore("t_looks.json", Path(tempfile.mkdtemp())))
        seen = []
        events.subscribe("cosmetic_unlocked", lambda kind, id, name, **_: seen.append((kind, id)))
        for a in ACHIEVEMENTS:
            p.tracker.stats[a.stat] = max(p.tracker.stats.get(a.stat, 0), a.target)
        p._finish_event()
        p._finish_event()
        self.assertIn(("board", "emerald"), seen)
        self.assertEqual(seen.count(("board", "emerald")), 1)
        self.assertTrue(p.look_unlocked("board", "emerald"))
        self.assertIn(("cards", "gold"), seen)                       # score_100k is part of "all trophies"
        reloaded = Progress(EventBus(), p.store)
        self.assertIn("board:emerald", reloaded.cosmetics_seen)

    def test_settings_choice_locked_and_unlocked(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.settings import SettingsScene
        app = OrderwickGame()
        sc = SettingsScene(app)
        key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0)
        sc.group.focus = sc.group.widgets.index(sc.board)
        sc.on_event(key(pygame.K_RIGHT))                              # Emerald is locked
        self.assertEqual(app.settings.data["board_theme"], "wood")
        self.assertIn("trophy", sc.board.hint().lower())
        for a in __import__("orderwick.core.achievements", fromlist=["x"]).ACHIEVEMENTS:
            app.progress.tracker.unlocked[a.id] = "2026-01-01"
        sc.on_event(key(pygame.K_LEFT))
        sc.on_event(key(pygame.K_RIGHT))                              # now it can be chosen
        self.assertEqual(app.settings.data["board_theme"], "emerald")
        self.assertEqual(app.assets.theme_dir, config.THEMES_DIR / "emerald")
        for size in ((640, 400), (1180, 780)):
            app.screen = pygame.display.set_mode(size)
            sc.draw(app.screen)
        app.settings.data["board_theme"] = "wood"
        app.apply_appearance()
        self.assertIsNone(app.assets.theme_dir)


class Importer(unittest.TestCase):
    def _tool(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, Path(config.ROOT_DIR, "tools", f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        import sys
        sys.path.insert(0, str(Path(config.ROOT_DIR, "tools")))
        spec.loader.exec_module(mod)
        return mod

    def test_every_card_has_a_source_name_mapping(self):
        tool = self._tool("import_aseprite")
        self.assertEqual(set(tool.OLD_TO_NEW.values()), set(tool.CARD_NAMES))
        self.assertEqual(len(tool.OLD_TO_NEW), len(set(tool.OLD_TO_NEW)))

    def test_card_sources_are_present_and_match_the_game_sprites(self):
        pygame.display.set_mode((1, 1))
        tool = self._tool("import_aseprite")
        read_aseprite = tool.read_aseprite
        for name in tool.CARD_NAMES:
            src = Path(config.ASSETS_DIR, "aseprite", "cards", f"{name}.aseprite")
            self.assertTrue(src.exists(), name)
            s = read_aseprite(src)
            classic = pygame.image.frombytes(s.flatten(0), (16, 16), "RGBA")
            gold = pygame.image.frombytes(s.flatten(1), (16, 16), "RGBA")
            game = pygame.image.load(str(Path(config.SPRITES_DIR, f"{name}.png"))).convert_alpha()
            style = pygame.image.load(str(Path(config.CARD_STYLES_DIR, "gold", f"{name}.png"))).convert_alpha()
            self.assertEqual(pygame.image.tobytes(classic, "RGBA"), pygame.image.tobytes(game, "RGBA"), name)
            self.assertEqual(pygame.image.tobytes(gold, "RGBA"), pygame.image.tobytes(style, "RGBA"), name)

    def test_theme_palette_roles_and_live_colours(self):
        import json
        from orderwick.view import colors
        palette = json.loads(Path(config.THEMES_DIR, "emerald", "palette.json").read_text())
        for role in ("WOOD", "DARK", "MID", "PLANK", "PLANK_L", "TAN", "CREAM", "BTN_TEXT", "TEXT", "BTN_VALUE"):
            self.assertIn(role, palette)
        before = tuple(colors.CREAM)
        colors.apply({k: tuple(v) for k, v in palette.items()})
        self.assertEqual(tuple(colors.BTN_TEXT)[:3], tuple(palette["BTN_TEXT"]))
        self.assertNotEqual(tuple(colors.CREAM), before)
        colors.apply(None)                                          # back to the default look
        self.assertEqual(tuple(colors.CREAM), before)

    def test_themed_hud_pieces_use_only_the_theme_palette(self):
        import json
        pygame.display.set_mode((1, 1))
        palette = {tuple(v) for v in json.loads(Path(config.THEMES_DIR, "emerald", "palette.json").read_text()).values()}
        accents = {(255, 205, 80), (190, 130, 40), (90, 200, 120), (40, 110, 60), (214, 90, 80), (90, 160, 220)}
        for name in ("panel", "inset", "button", "divider", "icons", "icons_audio"):
            img = pygame.image.load(str(Path(config.THEMES_DIR, "emerald", "hud", f"{name}.png"))).convert_alpha()
            used = {tuple(img.get_at((x, y)))[:3] for x in range(img.get_width()) for y in range(img.get_height())
                    if img.get_at((x, y))[3] > 0}
            self.assertLessEqual(used, palette | accents, name)


class DailyChallengesTests(unittest.TestCase):
    """Catalogue, the daily pick, progress rules, streaks, persistence and the trophies they feed."""

    def test_catalogue_is_big_and_balanced(self):
        from collections import Counter
        from orderwick.core import challenges as ch
        self.assertGreaterEqual(len(ch.CATALOGUE), 100)
        self.assertEqual(len({c.id for c in ch.CATALOGUE}), len(ch.CATALOGUE))
        tiers = Counter(c.tier for c in ch.CATALOGUE)
        self.assertTrue(all(tiers[t] >= 30 for t in (ch.EASY, ch.MEDIUM, ch.HARD)), tiers)
        self.assertTrue(all(c.target > 0 and c.text for c in ch.CATALOGUE))

    def test_daily_pick_is_deterministic_and_varied(self):
        from orderwick.core import challenges as ch
        cards = [n for names in config.CARD_FAMILIES.values() for n in names]
        a = ch.pick_daily("2026-11-03", cards)
        self.assertEqual([c.id for c in a], [c.id for c in ch.pick_daily("2026-11-03", cards)])
        self.assertEqual([c.tier for c in a], [ch.EASY, ch.MEDIUM, ch.HARD])
        self.assertEqual(len({c.kind for c in a}), 3)
        sets = {tuple(c.id for c in ch.pick_daily(f"2026-12-{d:02d}", cards)) for d in range(1, 29)}
        self.assertGreater(len(sets), 20)                                   # a different set most days

    def test_pick_only_uses_possible_tasks(self):
        from orderwick.core import challenges as ch
        first_cards = [names[0] for names in config.CARD_FAMILIES.values()]    # a new player's cards
        for day in range(1, 29):
            for c in ch.pick_daily(f"2026-10-{day:02d}", first_cards):
                self.assertTrue(c.feasible(first_cards), c.text)
                if c.filt == "card":
                    self.assertIn(c.value, first_cards)

    def test_record_rules(self):
        from orderwick.core import challenges as ch
        by = ch.BY_ID
        state = ch.DailyState()
        state.date, state.ids = "2026-11-03", [by[i].id for i in (
            "cols|colour|red|0|2", "win_fast|||120|1", "chain|||0|7")]
        self.assertEqual(state.record("cols", 1, "green_grape"), [])          # wrong colour
        state.record("cols", 1, "red_apple")
        self.assertEqual(state.progress[state.ids[0]], 1)
        self.assertEqual(len(state.record("cols", 1, "red_cherry")), 1)        # target reached
        self.assertEqual(state.record("cols", 1, "red_cherry"), [])            # already done: no more counting
        self.assertEqual(state.record("win_fast", 1, value=121), [])           # too slow
        self.assertEqual(len(state.record("win_fast", 1, value=100)), 1)
        state.record("chain", value=4)
        state.record("chain", value=2)                                          # a best value never goes down
        self.assertEqual(state.progress[state.ids[2]], 4)
        self.assertEqual(len(state.record("chain", value=9)), 1)
        self.assertEqual(state.total_done, 3)
        self.assertEqual(state.full_days, 1)

    def test_new_day_draws_new_tasks_and_keeps_totals(self):
        from orderwick.core import challenges as ch
        cards = [names[0] for names in config.CARD_FAMILIES.values()]
        state = ch.DailyState()
        self.assertTrue(state.ensure_today("2026-11-03", cards))
        self.assertFalse(state.ensure_today("2026-11-03", cards))               # same day: nothing changes
        first = list(state.ids)
        state.ids = ["moves|||0|30", "boards|||0|1", "pairs|||0|10"]
        state.record("moves", 9999)
        state.record("boards", 9999)
        state.record("pairs", 9999)
        self.assertEqual(state.total_done, 3)
        total = state.total_done
        self.assertTrue(state.ensure_today("2026-11-04", cards))
        self.assertEqual(state.done, set())
        self.assertEqual(state.progress, {})
        self.assertEqual(state.total_done, total)
        self.assertNotEqual(first, state.ids)
        self.assertEqual(len(state.ids), 3)

    def test_streak(self):
        from orderwick.core import challenges as ch
        s = ch.DailyState()
        for day in ("2026-11-03", "2026-11-04", "2026-11-05"):
            s.date, s.ids, s.progress, s.done = day, [ch.CATALOGUE[0].id] + [c.id for c in ch.CATALOGUE[6:8]], {}, set()
            s.record("cols", 99)
        self.assertEqual((s.streak, s.best_streak), (3, 3))
        self.assertEqual(s.current_streak("2026-11-05"), 3)
        self.assertEqual(s.current_streak("2026-11-06"), 3)                     # yesterday counts: still alive
        self.assertEqual(s.current_streak("2026-11-07"), 0)                     # a day was skipped
        s.date, s.done, s.progress = "2026-11-08", set(), {}
        s.record("cols", 99)
        self.assertEqual((s.streak, s.best_streak), (1, 3))

    def test_persistence_roundtrip(self):
        from orderwick.core import challenges as ch
        s = ch.DailyState()
        s.ensure_today("2026-11-03", None)
        s.record("moves", 5)
        s.record("boards", 3)
        again = ch.DailyState(json_roundtrip(s.to_dict()))
        self.assertEqual(again.to_dict(), s.to_dict())
        junk = ch.DailyState({"ids": ["nope"], "progress": {"nope": 4}, "done": ["nope"]})   # unknown ids are dropped
        self.assertEqual((junk.ids, junk.progress, junk.done), ([], {}, set()))

    def _make(self, today):
        from orderwick.data.daily import DailyChallenges
        events = EventBus()
        progress = Progress(events, JsonStore("p.json", Path(tempfile.mkdtemp())))
        daily = DailyChallenges(events, progress, JsonStore("d.json", Path(tempfile.mkdtemp())), today=lambda: today[0])
        return events, progress, daily

    def test_playing_counts_and_feeds_trophies(self):
        today = ["2026-11-03"]
        events, progress, daily = self._make(today)
        daily.state.ids = ["moves|||0|30", "boards|||0|1", "pairs|||0|10"]
        daily.state.progress, daily.state.done = {}, set()
        seen: list[int] = []
        events.subscribe("challenge_done", lambda done=0, **_: seen.append(done))
        session = GameSession(CampaignMode(1), events=events, rng=random.Random(5))
        rnd = session.create_round(budget=0.3)
        session.start_round(rnd)
        for src, dst in rnd.solution:                                            # the real solution of a real board
            session.move(src, dst)
        self.assertTrue(rnd.won)
        self.assertIn("boards|||0|1", daily.state.done)
        self.assertTrue(seen)
        self.assertGreaterEqual(progress.tracker.stats["daily_done"], 1)
        self.assertIn("daily_1", progress.tracker.unlocked)

    def test_custom_games_do_not_count(self):
        from orderwick.core.levels import CustomMode
        today = ["2026-11-03"]
        events, progress, daily = self._make(today)
        before = dict(daily.state.progress)
        session = GameSession(CustomMode(6, 2, 4), events=events, rng=random.Random(3))
        rnd = session.create_round(budget=0.3)
        session.start_round(rnd)
        for src, dst in rnd.solution:
            session.move(src, dst)
        self.assertTrue(rnd.won)
        self.assertEqual(daily.state.progress, before)

    def test_midnight_rollover_while_running(self):
        today = ["2026-11-03"]
        events, progress, daily = self._make(today)
        first = list(daily.state.ids)
        today[0] = "2026-11-04"
        self.assertTrue(daily.refresh())
        self.assertNotEqual(first, daily.state.ids)

    def test_daily_trophies_exist(self):
        for ach_id in ("daily_1", "daily_10", "daily_50", "daily_100", "daily_full_1", "daily_full_7", "daily_full_30",
                       "streak_3", "streak_7", "streak_30"):
            self.assertIn(ach_id, {a.id for a in ACHIEVEMENTS})

    def test_screen_and_menu_draw(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.daily import DailyScene, seconds_to_midnight
        from orderwick.scenes.menu import MenuScene
        app = OrderwickGame()
        for size in ((640, 400), (1180, 780)):
            app.screen = pygame.display.set_mode(size)
            DailyScene(app).draw(app.screen)
            MenuScene(app).draw(app.screen)
        self.assertTrue(0 < seconds_to_midnight() <= 86400)

    def test_daily_screen_buttons_start_a_run(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.daily import DailyScene
        from orderwick.scenes.game import GameScene
        from orderwick.scenes.level_select import LevelSelectScene
        from orderwick.scenes.menu import MenuScene
        app = OrderwickGame()
        app.screen = pygame.display.set_mode((960, 600))
        app.scenes.push(MenuScene(app))
        for index, expected in ((2, GameScene), (1, LevelSelectScene)):
            scene = DailyScene(app)
            app.scenes.push(scene)
            scene.draw(app.screen)
            scene.group.widgets[index].on_click()
            self.assertIsInstance(app.scenes.current, expected)
            app.scenes.pop()


def json_roundtrip(data):
    import json
    return json.loads(json.dumps(data))


class DailyBoardTests(unittest.TestCase):
    """One board a day: identical for everybody, solvable once, locked until the next day."""

    @staticmethod
    def _round(date, unlocked=None, seed=0):
        from orderwick.core.daily_board import DailyBoardMode
        session = GameSession(DailyBoardMode(date), events=EventBus(), rng=random.Random(seed), unlocked=unlocked)
        return session, session.create_round()

    def test_same_board_for_everyone(self):
        from orderwick.core.daily_board import MAX_LEVEL, MIN_LEVEL, daily_level
        everything = {n for names in config.CARD_FAMILIES.values() for n in names}
        _, a = self._round("2026-11-03", None, seed=1)
        _, b = self._round("2026-11-03", everything, seed=999)           # another player, other unlocks, other rng
        self.assertEqual(a.board.kinds(), b.board.kinds())
        self.assertEqual(a.palette, b.palette)
        self.assertEqual(a.solution, b.solution)
        self.assertTrue(MIN_LEVEL <= daily_level("2026-11-03") <= MAX_LEVEL)
        levels = {daily_level(f"2026-12-{d:02d}") for d in range(1, 29)}
        self.assertGreater(len(levels), 5)
        _, other = self._round("2026-11-04")
        self.assertNotEqual((a.board.kinds(), a.palette), (other.board.kinds(), other.palette))

    def test_board_uses_only_cards_every_player_has(self):
        from orderwick.core.daily_board import base_cards
        for day in range(1, 8):
            _, rnd = self._round(f"2026-11-{day:02d}")
            self.assertTrue(set(rnd.palette) <= set(base_cards()), rnd.palette)

    def test_every_daily_board_is_solvable(self):
        for day in range(1, 6):
            session, rnd = self._round(f"2026-11-{day:02d}")
            session.start_round(rnd)
            for src, dst in rnd.solution:
                self.assertTrue(session.move(src, dst).ok)
            self.assertTrue(rnd.won, day)

    def test_solved_once_then_locked_until_tomorrow(self):
        from orderwick.core.daily_board import DailyBoardMode
        from orderwick.data.daily import DailyChallenges
        today = ["2026-11-03"]
        events = EventBus()
        progress = Progress(events, JsonStore("p.json", Path(tempfile.mkdtemp())))
        directory = Path(tempfile.mkdtemp())
        daily = DailyChallenges(events, progress, JsonStore("d.json", directory), today=lambda: today[0])
        self.assertTrue(daily.board_open())
        session = GameSession(DailyBoardMode("2026-11-03"), events=events)
        rnd = session.create_round()
        session.start_round(rnd)
        for src, dst in rnd.solution:
            session.move(src, dst)
        self.assertTrue(rnd.won)
        self.assertTrue(daily.state.board_solved())
        self.assertGreater(daily.state.board_score, 0)
        self.assertFalse(daily.board_open())
        again = DailyChallenges(EventBus(), progress, JsonStore("d.json", directory), today=lambda: today[0])
        self.assertFalse(again.board_open())                              # still locked after a restart of the game
        today[0] = "2026-11-04"
        self.assertTrue(again.board_open())                               # a new day: a new board
        self.assertEqual(again.state.board_score, daily.state.board_score)   # the old result stays as history

    def test_daily_board_is_not_a_campaign_run(self):
        from orderwick.game import OrderwickGame
        from orderwick.scenes.daily import DailyScene
        from orderwick.scenes.game import GameScene
        from orderwick.scenes.menu import MenuScene
        app = OrderwickGame()
        app.screen = pygame.display.set_mode((960, 600))
        app.scenes.push(MenuScene(app))
        scene = DailyScene(app)
        app.scenes.push(scene)
        scene.draw(app.screen)
        scene.board_button.on_click()
        game = app.scenes.current
        self.assertIsInstance(game, GameScene)
        self.assertEqual(game.session.mode.id, "daily")
        self.assertFalse(game.session.mode.ranked)
        rnd = game.session.create_round()
        game.session.start_round(rnd)
        game.load_task = None
        for src, dst in rnd.solution:
            game.session.move(src, dst)
        data = game._win_data()
        self.assertEqual(len(data.buttons), 1)                            # no "next level" on the daily board
        self.assertIn("DAILY", data.title)
        game.draw(app.screen)
        games_before = app.leaderboard.data["stats"]["games"]
        app.scenes.pop()
        app.scenes.push(MenuScene(app)) if app.scenes.current is None else None
        game._finish()
        self.assertEqual(app.leaderboard.data["stats"]["games"], games_before)
        app.scenes.pop() if app.scenes.current is game else None
        solved = DailyScene(app)                                          # the button is disabled after solving
        solved.draw(app.screen)
        self.assertFalse(solved.board_button.enabled)
        solved.board_button.on_click()
        self.assertNotIsInstance(app.scenes.current, GameScene)

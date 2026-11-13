"""End-to-end test through the real UI (headless): menu -> game -> clicks -> win -> leaderboard.

Screenshots are saved to the directory from ORDERWICK_SHOTS (if set).
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ORDERWICK_AUDIO", "off")      # tests never spawn the sound process unless they ask for it
_TMP = tempfile.mkdtemp(prefix="orderwick_test_")
os.environ["ORDERWICK_HOME"] = _TMP

import pygame  # noqa: E402

from orderwick import config  # noqa: E402
from orderwick.core.levels import CampaignMode, HardMode  # noqa: E402
from orderwick.core.session import GameSession  # noqa: E402
from orderwick.game import OrderwickGame  # noqa: E402
from orderwick.scenes.custom import CustomScene  # noqa: E402
from orderwick.scenes.game import GameScene  # noqa: E402
from orderwick.scenes.help import HelpScene  # noqa: E402
from orderwick.scenes.leaderboard import LeaderboardScene  # noqa: E402
from orderwick.scenes.level_select import LevelSelectScene  # noqa: E402
from orderwick.scenes.menu import MenuScene  # noqa: E402
from orderwick.scenes.name_entry import NameEntryScene  # noqa: E402
from orderwick.scenes.pause import PauseScene  # noqa: E402

SHOTS = os.environ.get("ORDERWICK_SHOTS")


def key(k, ch=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0)


def click(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


class UiFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = OrderwickGame()
        cls.app.running = True

    def frame(self, n=1, events=()):
        for e in events:
            self.app.scenes.handle_event(e)
        for _ in range(n):
            self.app.scenes.update(1 / 60)
            self.app.scenes.draw(self.app.screen)

    def shot(self, name):
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.app.screen, str(Path(SHOTS) / f"{name}.png"))

    def wait_loaded(self, scene, timeout=30):
        t = time.time()
        while scene.loading and time.time() - t < timeout:
            self.frame()
            time.sleep(0.01)
        self.assertFalse(scene.loading, "tabla se nije ucitala")
        self.frame()

    def click_loc(self, scene, loc):
        pos = scene.view.loc_rect(loc).center
        self.frame(events=[click(pos)])

    def play_solution(self, scene):
        for src, dst in list(scene.rnd.solution):
            self.click_loc(scene, src)
            self.click_loc(scene, dst)

    # ------------------------------------------------------------------------------
    def test_01_menu_and_screens(self):
        scenes = self.app.scenes
        scenes.reset(MenuScene(self.app))
        self.frame(2)
        self.shot("01_menu")
        for cls, name in ((LevelSelectScene, "02_level_select"), (CustomScene, "03_custom"),
                          (LeaderboardScene, "04_leaderboard_empty"), (HelpScene, "05_help")):
            scenes.push(cls(self.app))
            self.frame(2)
            self.shot(name)
            scenes.pop()
        self.assertIsInstance(scenes.current, MenuScene)

    def test_02_hard_mode_full_flow(self):
        scenes = self.app.scenes
        scenes.reset(MenuScene(self.app))
        self.frame(events=[key(pygame.K_DOWN), key(pygame.K_RETURN)])    # Tezak mod
        game = scenes.current
        self.assertIsInstance(game, GameScene)
        self.wait_loaded(game)
        rnd = game.rnd
        self.assertEqual((rnd.board.n_cols, rnd.spec.rows, rnd.board.n_free), (10, 13, 1))
        self.shot("10_hard_start")

        # selection + wrong move + undo
        self.click_loc(game, game.view.hit_test(game.view.loc_rect(self._loc(0)).center))
        self.shot("11_hard_selected")
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertIsNone(game.selected)

        src, dst = rnd.solution[0]
        self.click_loc(game, src)
        self.click_loc(game, dst)
        self.assertEqual(rnd.moves, 1)
        self.assertIsNotNone(rnd.undo)
        self.frame(events=[key(pygame.K_u, "u")])
        self.assertIsNone(rnd.undo)
        self.frame(events=[key(pygame.K_u, "u")])        # second time - no more
        self.assertIn("only one step", game.msg)

        # pauza (vreme stoji)
        t0 = rnd.elapsed
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertIsInstance(scenes.current, PauseScene)
        self.frame(30)
        self.shot("12_pause")
        self.assertEqual(rnd.elapsed, t0)
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertIs(scenes.current, game)

        # solve the whole board with real clicks
        self.play_solution(game)
        self.assertTrue(rnd.won)
        self.assertGreater(self.app.screen.get_width(), 0)
        self.frame(3)
        self.shot("13_hard_won")

        # next board
        self.frame(events=[key(pygame.K_RETURN)])
        self.assertTrue(game.loading)
        self.wait_loaded(game)
        self.assertFalse(game.rnd.won)
        self.assertEqual(game.session.solved, 1)

        # kraj partije -> unos imena -> rang lista
        self.frame(events=[key(pygame.K_ESCAPE)])
        pause = scenes.current
        self.assertIsInstance(pause, PauseScene)
        self.frame(events=[key(pygame.K_DOWN), key(pygame.K_DOWN), key(pygame.K_RETURN)])
        entry = scenes.current
        self.assertIsInstance(entry, NameEntryScene)
        self.frame(2)
        self.shot("14_name_entry")
        for ch in "Milan":
            self.frame(events=[key(ord(ch.lower()), ch)])
        self.frame(events=[key(pygame.K_RETURN)])
        board = scenes.current
        self.assertIsInstance(board, LeaderboardScene)
        self.frame(2)
        self.shot("15_leaderboard")
        top = self.app.leaderboard.top("hard")
        self.assertEqual(top[0]["name"], "Milan")
        self.assertGreater(top[0]["score"], 0)
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertIsInstance(scenes.current, MenuScene)

    @staticmethod
    def _loc(i):
        from orderwick.core.models import col
        return col(i)

    def test_03_rescue_and_small_board(self):
        scenes = self.app.scenes
        scenes.reset(MenuScene(self.app))
        game = GameScene(self.app, GameSession(CampaignMode(1), events=self.app.events))
        scenes.push(game)
        self.wait_loaded(game)
        self.shot("20_level1")
        # level 1: there is no lower level
        self.frame(events=[key(pygame.K_x, "x")])
        self.assertIn("no lower level", game.msg)
        scenes.pop()

        game = GameScene(self.app, GameSession(CampaignMode(7), events=self.app.events))
        scenes.push(game)
        self.wait_loaded(game)
        before = game.rnd.board.n_free
        self.frame(events=[key(pygame.K_x, "x")])
        t = time.time()
        while game.rescue_task is not None and time.time() - t < 10:
            self.frame()
            time.sleep(0.01)
        # either a solution is still found (stays) or the rescue was applied
        if game.rnd.board.n_free == before:
            self.assertIn("A solution still exists", game.msg)
        else:
            self.assertEqual(game.rnd.board.n_free, before + 1)
            self.assertEqual(game.session.level, 6)
        self.shot("21_rescue")
        scenes.pop()

    def test_04_custom_mode(self):
        scenes = self.app.scenes
        scenes.reset(MenuScene(self.app))
        custom = CustomScene(self.app)
        scenes.push(custom)
        self.frame(events=[key(pygame.K_LEFT), key(pygame.K_DOWN), key(pygame.K_RIGHT),
                           key(pygame.K_DOWN), key(pygame.K_RIGHT), key(pygame.K_DOWN),
                           key(pygame.K_RETURN)])
        game = scenes.current
        self.assertIsInstance(game, GameScene)
        self.wait_loaded(game)
        spec = game.rnd.spec
        self.assertEqual((spec.cols, spec.free, spec.k), (7, 4, 7))
        self.assertFalse(game.session.mode.ranked)
        self.shot("30_custom_game")
        self.play_solution(game)
        self.assertTrue(game.rnd.won)
        self.shot("31_custom_won")
        self.frame(events=[key(pygame.K_q, "q")])       # end: not ranked -> back to the menu
        self.assertIsInstance(scenes.current, MenuScene)

    def test_06_selection_highlight_does_not_leak_hidden_cards(self):
        """The frame around the selected column may cover only REVEALED cards."""
        from orderwick.core.board import Board
        game = GameScene(self.app, GameSession(HardMode(), events=self.app.events))
        self.app.scenes.reset(MenuScene(self.app))
        self.app.scenes.push(game)
        self.wait_loaded(game)
        # column: three identical cards, only the top one revealed -> the frame = one cell
        board = Board.from_kinds([[1, 1, 1, 1], [], []], 1, 4, reveal=1)
        view = game.view
        view.layout(board, pygame.Rect(0, 0, 800, 700))
        one = view.cell_rect(0, 1)
        self.assertEqual(view._run_rect(board, 0).height, one.height)
        # if the 3 top ones are revealed -> the frame covers exactly 3
        board3 = Board.from_kinds([[1, 1, 1, 1], [], []], 1, 4, reveal=3)
        self.assertEqual(view._run_rect(board3, 0).height,
                         view.cell_rect(0, 1).union(view.cell_rect(0, 3)).height)

    def test_07_exit_paths(self):
        scenes = self.app.scenes

        # menu: Esc closes the application
        self.app.running = True
        scenes.reset(MenuScene(self.app))
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertFalse(self.app.running)

        # menu: Quit button
        self.app.running = True
        scenes.reset(MenuScene(self.app))
        self.frame(events=[key(pygame.K_UP), key(pygame.K_RETURN)])   # focus goes to the last one = Quit
        self.assertFalse(self.app.running)

        # game: Q asks, "No" stays in the game, "Yes" returns to the menu
        self.app.running = True
        game = GameScene(self.app, GameSession(CampaignMode(1), events=self.app.events))
        scenes.reset(MenuScene(self.app))
        scenes.push(game)
        self.wait_loaded(game)
        self.frame(events=[key(pygame.K_q, "q")])
        from orderwick.scenes.confirm import ConfirmScene
        self.assertIsInstance(scenes.current, ConfirmScene)
        self.frame(events=[key(pygame.K_RETURN)])                      # podrazumevano "Ne"
        self.assertIs(scenes.current, game)
        self.frame(events=[key(pygame.K_q, "q"), key(pygame.K_DOWN), key(pygame.K_RETURN)])
        self.assertIsInstance(scenes.current, MenuScene)
        self.assertTrue(self.app.running)

        # pause -> Quit game (with confirmation)
        game = GameScene(self.app, GameSession(CampaignMode(1), events=self.app.events))
        scenes.push(game)
        self.wait_loaded(game)
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.frame(events=[key(pygame.K_UP), key(pygame.K_RETURN)])    # last button: Quit game
        self.assertIsInstance(scenes.current, ConfirmScene)
        self.frame(events=[key(pygame.K_DOWN), key(pygame.K_RETURN)])  # Da
        self.assertFalse(self.app.running)

        # closing the window mid-run keeps the score
        self.app.running = True
        game = GameScene(self.app, GameSession(CampaignMode(1), events=self.app.events))
        scenes.reset(MenuScene(self.app))
        scenes.push(game)
        self.wait_loaded(game)
        self.play_solution(game)
        self.assertTrue(game.rnd.won)
        before = len(self.app.leaderboard.top("campaign"))
        scenes.notify_quit()
        after = self.app.leaderboard.top("campaign")
        self.assertEqual(len(after), before + 1)
        self.assertTrue(any(e["name"] == "PLAYER" for e in after))
        scenes.notify_quit()                                           # the second time it does not duplicate
        self.assertEqual(len(self.app.leaderboard.top("campaign")), before + 1)
        self.app.running = True

    def test_08_next_board_is_prefetched_and_used(self):
        """While you play, the next board is built in the background; after a win there is no extra waiting."""
        scenes = self.app.scenes
        game = GameScene(self.app, GameSession(CampaignMode(1), events=self.app.events))
        scenes.reset(MenuScene(self.app))
        scenes.push(game)
        self.wait_loaded(game)
        self.assertIsNotNone(game.prefetch)
        level, task = game.prefetch
        self.assertEqual(level, 2)
        t = time.time()
        while not task.done and time.time() - t < 30:
            time.sleep(0.05)
        self.assertTrue(task.done)
        self.play_solution(game)
        self.assertTrue(game.rnd.won)
        self.frame(events=[key(pygame.K_RETURN)])
        self.frame(2)
        self.assertFalse(game.loading)
        self.assertIs(game.rnd, task.result)              # the pre-built board was used
        self.assertEqual(game.session.level, 2)
        self.assertEqual(game.rnd.level, 2)
        self.assertIsNotNone(game.prefetch)               # the next one is already being built

    def test_09_hud_buttons_work_with_the_mouse(self):
        """Clicking a HUD button does the same as the key; the HUD and the board share the same scale factor."""
        scenes = self.app.scenes
        game = GameScene(self.app, GameSession(CampaignMode(3), events=self.app.events))
        scenes.reset(MenuScene(self.app))
        scenes.push(game)
        self.wait_loaded(game)
        self.frame(2)
        S = game.scale
        self.assertEqual(S, game.view.scale)

        def hud_click(index):
            r = game.hud.button_rects(game._hud_h, 4)[index]
            pos = (game._hud_x + r.centerx * S, r.centery * S)
            self.frame(events=[pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)),
                               pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)])
            self.assertEqual(game.hud_pressed, index if game._hud_enabled()[index] else None)
            self.frame(events=[pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)])

        # "undo" is disabled while there are no moves
        hud_click(0)
        self.assertEqual(game.rnd.moves, 0)
        src, dst = game.rnd.solution[0]
        self.click_loc(game, src)
        self.click_loc(game, dst)
        self.assertEqual(game.rnd.moves, 1)
        hud_click(0)                                         # sada radi
        self.assertIsNone(game.rnd.undo)
        hud_click(1)                                         # spas
        self.wait_idle(game)
        self.assertGreaterEqual(game.rnd.board.n_free, 3)
        hud_click(3)                                         # pauza
        self.assertIsInstance(scenes.current, PauseScene)
        self.frame(events=[key(pygame.K_ESCAPE)])
        self.assertIs(scenes.current, game)

    def wait_idle(self, game, timeout=15):
        t = time.time()
        while game.rescue_task is not None and time.time() - t < timeout:
            self.frame()
            time.sleep(0.01)

    def test_10_win_overlay_buttons_and_layout_at_all_sizes(self):
        scenes = self.app.scenes
        game = GameScene(self.app, GameSession(CampaignMode(2), events=self.app.events))
        scenes.reset(MenuScene(self.app))
        scenes.push(game)
        self.wait_loaded(game)
        for size in ((900, 620), (1180, 780), (1920, 1080)):
            self.app.screen = pygame.display.set_mode(size)
            self.frame(2)
            S = game.scale
            board = game.view.screen_rect
            hud = pygame.Rect(game._hud_x, 0, config.HUD_WIDTH * S, size[1])
            win = pygame.Rect(0, 0, *size)
            self.assertTrue(win.contains(board), size)
            self.assertFalse(board.colliderect(hud), size)             # the board and the HUD do not overlap
            self.assertEqual(S, game.view.scale)
        self.app.screen = pygame.display.set_mode((1180, 780))
        self.frame(2)
        self.play_solution(game)
        self.assertTrue(game.rnd.won)
        self.frame(2)
        r = game._win_rects[1]                                         # "ZAVRSI PARTIJU"
        S = game.scale
        pos = ((game._win_origin[0] + r.centerx) * S, (game._win_origin[1] + r.centery) * S)
        self.frame(events=[pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)])
        self.frame(events=[pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)])
        self.assertTrue(isinstance(scenes.current, (MenuScene, NameEntryScene)))

    def test_05_window_sizes(self):
        game = GameScene(self.app, GameSession(HardMode(), events=self.app.events))
        self.app.scenes.reset(MenuScene(self.app))
        self.app.scenes.push(game)
        self.wait_loaded(game)
        for size in ((900, 620), (1920, 1080), (1180, 780)):
            self.app.screen = pygame.display.set_mode(size)
            self.frame(2)
            self.assertGreaterEqual(game.view.scale, 1)
            rect = game.view.screen_rect
            self.assertTrue(pygame.Rect(0, 0, *size).contains(rect), f"tabla izlazi iz prozora {size}")
        self.shot("40_window_1920")
        self.app.screen = pygame.display.set_mode((1180, 780))


if __name__ == "__main__":
    unittest.main()

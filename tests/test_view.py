"""Board appearance tests (board.png asset, assembly, card families). Headless."""
import ast
import os
import random
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from orderwick import config  # noqa: E402
from orderwick.core.board import Board  # noqa: E402
from orderwick.core.models import LevelSpec, col, slot  # noqa: E402
from orderwick.core.palette import pick_palette  # noqa: E402
from orderwick.engine.assets import AssetManager  # noqa: E402
from orderwick.engine.nine_slice import NineSlice  # noqa: E402
from orderwick.view.hud_view import HudButton, HudData, HudView, WinData  # noqa: E402
from orderwick.view.board_skin import BoardSkin  # noqa: E402
from orderwick.view.board_view import BoardView  # noqa: E402


def same_pixels(a, b):
    return a.get_size() == b.get_size() and pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


class SkinAndPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((100, 100))
        cls.assets = AssetManager(config.SPRITES_DIR)
        cls.image = cls.assets.image(config.BOARD_IMAGE)
        cls.skin = BoardSkin(cls.image)

    def test_full_size_is_identical_to_the_asset(self):
        """10 lanes x 12 rows must be PIXEL-FOR-PIXEL identical to board.png."""
        self.assertEqual(self.image.get_size(), (193, 217))
        self.assertTrue(same_pixels(self.skin.build(10, 12), self.image))

    def test_sizes_follow_the_formula(self):
        for n in (3, 5, 8, 10):
            for k in (2, 4, 6, 9, 12):
                self.assertEqual(self.skin.build(n, k).get_size(), (19 * n + 3, 16 * k + 25), (n, k))

    def test_narrower_board_is_the_left_part_of_the_asset(self):
        """Narrower boards repeat the same lanes: the first n lanes + the right frame."""
        small = self.skin.build(4, 12)
        for y in (5, 100, 200):
            for x in range(0, 3 + 19 * 4 - 3):
                self.assertEqual(small.get_at((x, y)), self.image.get_at((x, y)), (x, y))
        right = small.get_width() - 3
        for dx in range(3):
            self.assertEqual(small.get_at((right + dx, 100)), self.image.get_at((190 + dx, 100)))

    def test_shorter_lane_keeps_caps_and_dashed_edge(self):
        for k in (3, 6, 9):
            surf = self.skin.build(10, k)
            lane_top, lane_h = 22, 16 * k
            for r in range(4):                       # gornji rub trake netaknut
                for x in (3, 10, 18):
                    self.assertEqual(surf.get_at((x, lane_top + r)), self.image.get_at((x, 22 + r)))
            for r in range(4):                       # donji rub netaknut
                for x in (3, 10, 18):
                    self.assertEqual(surf.get_at((x, lane_top + lane_h - 1 - r)),
                                     self.image.get_at((x, 213 - r)))
            for r in range(6, lane_h - 6):           # the dashed edge still alternates every row
                self.assertNotEqual(surf.get_at((3, lane_top + r)), surf.get_at((3, lane_top + r + 1)), (k, r))

    def test_all_cards_load_and_are_16x16(self):
        names = [n for members in config.CARD_FAMILIES.values() for n in members]
        names += [config.HIDDEN_SPRITE, config.BLOCKED_SPRITE]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertEqual(self.assets.sprite(name).get_size(), (16, 16), name)

    def test_palette_uses_distinct_families(self):
        family_of = {n: f for f, members in config.CARD_FAMILIES.items() for n in members}
        for types in range(2, config.MAX_TYPES + 1):
            for seed in range(30):
                names = pick_palette(random.Random(seed), types)
                self.assertEqual(len(names), types)
                self.assertEqual(len({family_of[n] for n in names}), types, (types, seed, names))

    def test_palette_varies_between_boards(self):
        sets = {tuple(sorted(pick_palette(random.Random(s), 9))) for s in range(40)}
        self.assertGreater(len(sets), 30)                      # almost every board is different
        used = {n for s in sets for n in s}
        self.assertGreaterEqual(len(used), 30)                 # most of the 38 types are used

    def test_hit_testing_blocked_slots_gaps_and_columns(self):
        spec = LevelSpec(10, 2, 6)
        board = Board.from_kinds([[0, 1]] * 9 + [[]], spec.free, spec.k)
        view = BoardView(self.assets)
        view.layout(board, pygame.Rect(0, 0, 900, 700))
        self.assertIsNone(view.hit_test(view.cell_rect(0, 0).center))        # locked slot (!)
        self.assertIsNone(view.hit_test(view.cell_rect(7, 0).center))
        self.assertEqual(view.hit_test(view.cell_rect(8, 0).center), slot(0))
        self.assertEqual(view.hit_test(view.cell_rect(9, 0).center), slot(1))
        for c in range(10):
            self.assertEqual(view.hit_test(view.cell_rect(c, 1).center), col(c))
            self.assertEqual(view.hit_test(view.cell_rect(c, spec.k).center), col(c))
        gap = view.cell_rect(3, 3).right + view.scale          # the gap to the right of lane 3
        self.assertEqual(view.hit_test((gap, view.cell_rect(3, 3).centery)), col(3))
        self.assertIsNone(view.hit_test((0, 0)))               # outside the board


def ui_strings():
    """All strings from the source code (without docstrings) - that is the text the game can print."""
    for path in Path(config.ROOT_DIR, "orderwick").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                yield path.name, node.value


class FontAndHud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((100, 100))
        cls.assets = AssetManager(config.SPRITES_DIR)
        cls.hud = HudView(cls.assets)

    def test_font_is_cc0_and_documented(self):
        readme = Path(config.FONT_PATH).with_name("README.txt").read_text(encoding="utf-8")
        self.assertIn("CC0", readme)
        self.assertIn("GGBotNet", readme)

    def test_font_has_every_character_the_game_can_print(self):
        """Every letter and symbol of the game text must exist in the font."""
        font = self.assets.pixel_font(1)
        problems = []
        for fname, text in ui_strings():
            printable = text.upper() if config.UPPERCASE_UI else text
            for ch in set(printable):
                if ch not in "\n\t" and not font.has_glyphs(ch):
                    problems.append((fname, ch, hex(ord(ch))))
        self.assertEqual(problems, [])
        for ch in "ČĆŠŽĐ":                                      # letters players may type in names (Serbian Latin)
            self.assertTrue(font.has_glyphs(ch), ch)

    def test_pixel_font_is_crisp_and_integer_scaled(self):
        for scale in (1, 2, 3):
            img = self.assets.pixel_font(scale).render("TEŽAK ČĆŠŽĐ 15", False, (255, 255, 255))
            alphas = {img.get_at((x, y))[3] for x in range(img.get_width()) for y in range(img.get_height())}
            self.assertEqual(alphas, {0, 255})                   # no smoothing
            self.assertEqual(img.get_width(), 14 * 8 * scale)    # monospace 8 px po slovu
        self.assertEqual(self.assets.font(24).scale, 2)

    def test_uppercase_ui(self):
        a = self.assets.pixel_font(1).render("težak", False, (255, 255, 255))
        b = self.assets.pixel_font(1).render("TEŽAK", False, (255, 255, 255))
        self.assertEqual(pygame.image.tobytes(a, "RGBA"), pygame.image.tobytes(b, "RGBA"))

    def test_hud_assets_have_expected_structure(self):
        a = self.assets
        self.assertEqual(a.image(config.HUD_PANEL).get_size(), (16, 16))
        self.assertEqual(a.image(config.HUD_INSET).get_size(), (12, 12))
        self.assertEqual(a.image(config.HUD_BUTTON).get_size(), (12 * len(config.BUTTON_STATES), 12))
        self.assertEqual(a.image(config.HUD_ICONS).get_size(), (config.ICON_CELL * len(config.ICON_ORDER), 12))

    def test_hud_assets_match_the_generator_script(self):
        """assets/hud/*.png must be exactly what tools/make_hud_assets.py produces."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_hud", Path(config.ROOT_DIR, "tools", "make_hud_assets.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        self.assertEqual(tool.ICON_ORDER, config.ICON_ORDER)
        for name, image in (("panel", tool.make_panel()), ("inset", tool.make_inset()),
                            ("button", tool.make_button()), ("icons", tool.make_icons()),
                            ("divider", tool.make_divider())):
            on_disk = pygame.image.load(str(Path(config.ASSETS_DIR, "hud", f"{name}.png"))).convert_alpha()
            self.assertTrue(same_pixels(image, on_disk), name)

    def test_hud_uses_board_palette(self):
        """The HUD must use the wooden frame colours from board.png."""
        board = self.assets.image(config.BOARD_IMAGE)
        board_colors = {tuple(board.get_at((x, y)))[:3] for x in range(board.get_width()) for y in range(board.get_height())}
        panel = self.assets.image(config.HUD_PANEL)
        panel_colors = {tuple(panel.get_at((x, y)))[:3] for x in range(16) for y in range(16)}
        self.assertTrue({(90, 78, 68), (66, 57, 52), (121, 103, 85), (199, 176, 139)} <= board_colors)
        self.assertTrue({(90, 78, 68), (66, 57, 52), (121, 103, 85), (199, 176, 139)} <= panel_colors)

    def test_nine_slice_keeps_corners_and_checker_pattern(self):
        nine = NineSlice(self.assets.image(config.HUD_PANEL), 6)
        src = self.assets.image(config.HUD_PANEL)
        for size in ((16, 16), (128, 260), (200, 41)):
            out = nine.render(size)
            self.assertEqual(out.get_size(), size)
            for (cx, cy, sx, sy) in ((0, 0, 0, 0), (size[0] - 6, 0, 10, 0), (0, size[1] - 6, 0, 10),
                                     (size[0] - 6, size[1] - 6, 10, 10)):
                for dx in range(6):
                    for dy in range(6):
                        self.assertEqual(out.get_at((cx + dx, cy + dy)), src.get_at((sx + dx, sy + dy)))
            for x in range(6, size[0] - 7):                      # the dashed edge alternates without a break
                self.assertNotEqual(out.get_at((x, 4)), out.get_at((x + 1, 4)), (size, x))

    def _data(self, messages=None):
        return HudData("HARD MODE", "NIVO 15", ["10×13 VRSTA 9", "SLOB. POLJA 1"], "659", "02:45", "2079",
                       messages or [], [HudButton("VRATI POTEZ", "undo", False), HudButton("SPAS", "rescue"),
                                         HudButton("NOVA TABLA", "restart"), HudButton("PAUZA", "pause")])

    def test_hud_renders_for_all_heights_and_clips_long_messages(self):
        long = "x " * 200
        for height in (200, 260, 310, 400):
            surf = self.hud.render(self._data([(long, (255, 255, 255))]), height)
            self.assertEqual(surf.get_size(), (config.HUD_WIDTH, height))
            rects = self.hud.button_rects(height, 4)
            self.assertEqual(len(rects), 4)
            for r in rects:
                self.assertTrue(pygame.Rect(0, 0, config.HUD_WIDTH, height).contains(r))
            for a, b in zip(rects, rects[1:]):
                self.assertFalse(a.colliderect(b))

    def test_hud_button_hit_testing(self):
        height = 260
        for i, r in enumerate(self.hud.button_rects(height, 4)):
            self.assertEqual(self.hud.hit_test(r.center, height, 4), i)
        self.assertIsNone(self.hud.hit_test((2, 2), height, 4))

    def test_hud_text_fits_in_buttons(self):
        for label in ("VRATI POTEZ", "SPAS", "NOVA TABLA", "PAUZA"):
            # icon 12 + gap 2 + edges + text (8 px per letter) must fit in the button (112 px)
            self.assertLessEqual(4 + config.ICON_CELL + 2 + 8 * len(label) + 4, config.HUD_WIDTH - 16)

    def test_win_overlay_layout(self):
        win = WinData("NIVO 15 REŠEN!", [("NIVO", "15", "+1500"), ("POTEZI", "659", "+258"),
                                         ("VREME", "00:22", "+321")], "UKUPNO 2079", "FINALE! IGRAŠ NOVE TABLE.",
                      [HudButton("SLEDEĆI NIVO", ""), HudButton("ZAVRŠI PARTIJU", "")])
        surf, rects = self.hud.render_win(win)
        self.assertEqual(len(rects), 2)
        for r in rects:
            self.assertTrue(pygame.Rect(0, 0, *surf.get_size()).contains(r))
        self.assertFalse(rects[0].colliderect(rects[1]))


if __name__ == "__main__":
    unittest.main()

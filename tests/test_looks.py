"""Card looks: a card = style background + set picture; card sets in palettes; the lent look of a season and of the daily board."""
import json
import os
import random
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ORDERWICK_AUDIO", "off")
os.environ.setdefault("ORDERWICK_HOME", tempfile.mkdtemp(prefix="orderwick_looks_"))

import pygame  # noqa: E402

from orderwick import config  # noqa: E402
from orderwick.core import cardsets  # noqa: E402
from orderwick.core.palette import pick_palette  # noqa: E402
from orderwick.engine.assets import AssetManager  # noqa: E402
from orderwick.online.content import safe_path  # noqa: E402
from tests.test_content import ContentCase, FakeApi, item, png, wait  # noqa: E402

STYLES = ["classic", "gold", "ember", "frost", "wildwood", "neon", "clockwork", "matrix", "storm"]


def make_set(directory: Path, cards=12) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    families = {"gifts": [], "baubles": []}
    for i in range(cards):
        surface = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.circle(surface, (250, 20 + i * 15, 20), (8, 8), 5)
        pygame.image.save(surface, str(directory / f"gift_{i}.png"))
        families["gifts" if i % 2 else "baubles"].append(f"gift_{i}")
    (directory / "families.json").write_text(json.dumps(families))
    return families


class Shipped(unittest.TestCase):
    def test_every_style_and_the_fruits_are_in_the_game(self):
        for style in STYLES:
            self.assertTrue((config.CARD_STYLES_DIR / style / "background.png").is_file(), style)
            if style != "classic":
                for mark in (config.HIDDEN_SPRITE, config.BLOCKED_SPRITE):
                    self.assertTrue((config.CARD_STYLES_DIR / style / f"{mark}.png").is_file(), f"{style}/{mark}")
        names = [n for members in config.CARD_FAMILIES.values() for n in members]
        self.assertEqual(len(names), 38)
        for name in names:
            self.assertTrue((config.ASSETS_DIR / "cards_fg" / f"{name}.png").is_file(), name)


class Compose(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.assets = AssetManager(config.SPRITES_DIR)

    def test_a_card_is_the_background_of_the_style_with_the_picture_on_top(self):
        classic = self.assets.sprite("red_apple").copy()
        self.assets.set_card_style(config.CARD_STYLES_DIR / "ember")
        ember = self.assets.sprite("red_apple")
        self.assertNotEqual(pygame.image.tobytes(ember, "RGBA"), pygame.image.tobytes(classic, "RGBA"))
        bg = pygame.image.load(str(config.CARD_STYLES_DIR / "ember" / "background.png")).convert_alpha()
        fg = pygame.image.load(str(config.ASSETS_DIR / "cards_fg" / "red_apple.png")).convert_alpha()
        want = bg.copy(); want.blit(fg, (0, 0))
        self.assertEqual(pygame.image.tobytes(ember, "RGBA"), pygame.image.tobytes(want, "RGBA"))
        mark = self.assets.sprite(config.HIDDEN_SPRITE)
        self.assertEqual(pygame.image.tobytes(mark, "RGBA"), pygame.image.tobytes(pygame.image.load(str(config.CARD_STYLES_DIR / "ember" / "question_mark.png")).convert_alpha(), "RGBA"), "? and ! belong to the style")

    def test_classic_and_gold_cards_are_unchanged_by_the_new_mechanism(self):
        for style in (None, config.CARD_STYLES_DIR / "gold"):
            self.assets.set_card_style(style)
            for name in ("red_apple", "purple_grape", "yellow_sunflower"):
                baked = pygame.image.load(str((style or config.SPRITES_DIR) / f"{name}.png")).convert_alpha()
                self.assertEqual(pygame.image.tobytes(self.assets.sprite(name), "RGBA"), pygame.image.tobytes(baked, "RGBA"), f"{style}/{name}")

    def test_a_card_set_works_with_every_style(self):
        folder = Path(tempfile.mkdtemp()) / "gifts"
        make_set(folder)
        self.assets.set_card_set(folder)
        seen = set()
        for style in STYLES:
            self.assets.set_card_style(None if style == "classic" else config.CARD_STYLES_DIR / style)
            card = self.assets.sprite("gift_3")
            self.assertEqual(card.get_size(), (16, 16))
            seen.add(pygame.image.tobytes(card, "RGBA"))
        self.assertEqual(len(seen), len(STYLES), "the same picture on nine different backgrounds")
        self.assets.set_card_set(None)
        self.assertEqual(self.assets.sprite("red_apple").get_size(), (16, 16), "back to the fruits")


class Sets(unittest.TestCase):
    def test_families_are_read_checked_and_used_for_the_palette(self):
        folder = Path(tempfile.mkdtemp()) / "gifts"
        families = make_set(folder)
        self.assertEqual(cardsets.load_families(folder), families)
        palette = pick_palette(random.Random(5), 9, unlocked={"red_apple"}, families=families)
        self.assertEqual(len(palette), 9)
        self.assertTrue(all(n.startswith("gift_") for n in palette), "only the set's cards, whatever the player has unlocked")
        self.assertEqual(len(set(palette)), 9)
        both = pick_palette(random.Random(1), 2, families=families)
        self.assertEqual({n.startswith("gift_") for n in both}, {True})
        fruit = pick_palette(random.Random(5), 9)
        self.assertFalse(any(n.startswith("gift_") for n in fruit))
        small = Path(tempfile.mkdtemp()) / "tiny"
        make_set(small, cards=5)
        self.assertIsNone(cardsets.load_families(small), "a set needs at least 12 cards")
        (folder / "families.json").write_text("[]")
        self.assertIsNone(cardsets.load_families(folder))

    def test_paths_of_sets_are_known_shapes(self):
        self.assertTrue(safe_path("card_sets/gifts/families.json"))
        self.assertTrue(safe_path("card_sets/gifts/gift_red.png"))
        self.assertFalse(safe_path("card_sets/gifts/../../x.png"))
        self.assertFalse(safe_path("card_sets/gifts/Bad.png"))


class Lent(ContentCase):
    def _set_item(self, code, cards=12):
        files, blobs = {}, {}
        families = {"gifts": [], "baubles": []}
        for i in range(cards):
            data = png((200, i * 10, 10)); name = f"{code}_{i}"
            files[f"card_sets/{code}/{name}.png"] = data
            families["gifts" if i % 2 else "baubles"].append(name)
        files[f"card_sets/{code}/families.json"] = json.dumps(families).encode()
        self.api.add(item(code, "card_set", files, acquisition="grant", price=0), files)
        return families

    def _style_item(self, code):
        files = {f"card_styles/{code}/{slot}.png": png((5, 5, 40)) for slot in ("background", "question_mark", "exclamation_mark")}
        self.api.add(item(code, "card_style", files, acquisition="grant", price=0), files)

    def test_the_daily_look_is_fetched_for_everybody_and_lent_only_today(self):
        families = self._set_item("gifts")
        self._style_item("cards_ember")
        self.api.owned = []
        today = time.strftime("%Y-%m-%d", time.gmtime())
        self.api.daily_look = {"date": today, "theme": {"code": "emerald"}, "cardStyle": {"code": "cards_ember"}, "cardSet": {"code": "gifts"}}
        store = self.store()
        store.sync_async(force=True)
        self.assertTrue(wait(store))
        look = store.lent_look("daily")
        self.assertEqual((look["theme"], look["style"], look["set"]), ("emerald", "cards_ember", "gifts"))
        self.assertEqual(look["families"], families)
        self.assertEqual(store.card_set_dir("gifts"), self.tmp / "content" / "card_sets" / "gifts")
        self.assertIsNone(store.card_set_dir("fruits"), "the fruits are the game's own")
        self.assertEqual(store.lent_look("campaign"), {}, "other modes lend nothing")
        store.state["daily"]["date"] = "2000-01-01"
        self.assertEqual(store.lent_look("daily"), {}, "yesterday's look is not lent today")

    def test_a_part_that_is_not_ready_is_left_out_not_half_shown(self):
        self._style_item("cards_ember")
        self.api.daily_look = {"date": time.strftime("%Y-%m-%d", time.gmtime()), "theme": {"code": "never_heard"}, "cardStyle": {"code": "cards_ember"}, "cardSet": {"code": "missing_set"}}
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        look = store.lent_look("daily")
        self.assertIsNone(look["theme"])
        self.assertIsNone(look["set"])
        self.assertEqual(look["style"], "cards_ember")

    def test_a_season_lends_its_cards_and_its_background_too(self):
        families = self._set_item("gifts")
        self._style_item("cards_frost")
        theme = {"themes/frost/board/board.png": png((9, 9, 9))}
        self.api.add(item("frost", "board_theme", theme, acquisition="grant", price=0), theme)
        self.api.live = {"code": "winter", "name": "Winter", "theme": {"code": "frost"}, "cardStyle": {"code": "cards_frost"}, "cardSet": {"code": "gifts"}, "remainingSeconds": 3600}
        store = self.store()
        store.sync_async(force=True)
        self.assertTrue(wait(store))
        look = store.lent_look("season")
        self.assertEqual((look["theme"], look["style"], look["set"]), ("frost", "cards_frost", "gifts"))
        self.assertEqual(look["families"], families)
        self.assertTrue((self.tmp / "content" / "card_styles" / "cards_frost" / "background.png").is_file(), "downloaded though not owned")
        again = self.store()                                          # a restart keeps it
        self.assertEqual(again.lent_look("season")["set"], "gifts")


class Trophies(unittest.TestCase):
    def test_long_texts_are_cut_to_the_room_before_the_numbers(self):
        from orderwick.scenes.achievements import AchievementsScene
        from orderwick.view.wood_kit import WoodKit
        pygame.init(); pygame.display.set_mode((1, 1))
        kit = WoodKit(AssetManager(config.SPRITES_DIR))
        scene = AchievementsScene.__new__(AchievementsScene)
        long = "Unlock every other achievement. Prizes: the golden frame and a lot of coins"
        cut = scene._fit(kit, long, 180, body=True)
        self.assertTrue(cut.endswith("..") and kit.body.size(cut)[0] <= 180)
        self.assertEqual(scene._fit(kit, "Solve 10 boards.", 180, body=True), "Solve 10 boards.")


if __name__ == "__main__":
    unittest.main()

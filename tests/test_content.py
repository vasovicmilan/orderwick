"""Server content in the game: download, verification, registration and fallback. No network: a fake API serves the files."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ORDERWICK_AUDIO", "off")
os.environ.setdefault("ORDERWICK_HOME", tempfile.mkdtemp(prefix="orderwick_content_"))

import pygame  # noqa: E402

from orderwick import config  # noqa: E402
from orderwick.core import cosmetics  # noqa: E402
from orderwick.core.collection import Collection  # noqa: E402
from orderwick.data.storage import JsonStore  # noqa: E402
from orderwick.engine.assets import AssetManager  # noqa: E402
from orderwick.online.client import OnlineError  # noqa: E402
from orderwick.online.content import ContentStore, safe_path  # noqa: E402


def png(color=(200, 30, 30)) -> bytes:
    pygame.init()
    surface = pygame.Surface((16, 16), pygame.SRCALPHA)
    surface.fill(color)
    path = Path(tempfile.mkdtemp()) / "x.png"
    pygame.image.save(surface, str(path))
    return path.read_bytes()


def item(code, kind, files, acquisition="shop", price=20, **extra):
    return {"code": code, "kind": kind, "name": code.title(), "description": "", "acquisition": acquisition, "price": price,
            "achievement": None, "files": {rel: {"hash": hashlib.sha256(data).hexdigest(), "size": len(data)} for rel, data in files.items()}, **extra}


class FakeApi:
    def __init__(self):
        self.blobs = {}
        self.items = []
        self.owned = []
        self.schema = 1
        self.down = False
        self.downloads = []

    def add(self, entry, files):
        self.items.append(entry)
        for data in files.values():
            self.blobs[hashlib.sha256(data).hexdigest()] = data

    def content_manifest(self):
        if self.down:
            raise OnlineError("network", "Can't reach the server.")
        return {"schema": self.schema, "version": "v1", "items": self.items}

    def inventory(self):
        return {"owned": self.owned, "currency": {"name": "Coins", "balance": 5}}

    def download(self, file_hash):
        self.downloads.append(file_hash)
        if file_hash not in self.blobs:
            raise OnlineError("http_404", "Not found", 404)
        return self.blobs[file_hash]


def wait(store):
    store.task.join()
    return store.poll()


class ContentCase(unittest.TestCase):
    def setUp(self):
        self.saved = (dict(config.PREMIUM_CARDS), list(config.BOARD_THEMES), list(config.CARD_STYLES), set(cosmetics.OWNED), dict(cosmetics.ITEM_INFO))
        self.tmp = Path(tempfile.mkdtemp())
        self.api = FakeApi()

    def tearDown(self):
        config.PREMIUM_CARDS.clear(); config.PREMIUM_CARDS.update(self.saved[0])
        config.BOARD_THEMES[:] = self.saved[1]; config.CARD_STYLES[:] = self.saved[2]
        cosmetics.OWNED = self.saved[3]
        cosmetics.ITEM_INFO.clear(); cosmetics.ITEM_INFO.update(self.saved[4])

    def store(self):
        return ContentStore(client=self.api, store=JsonStore("content.json", self.tmp), directory=self.tmp)


class Sync(ContentCase):
    def test_songs_from_the_server_are_downloaded_and_offered_to_the_player(self):
        song = {"music/night_train.ogg": b"OggS" + bytes(3000)}
        fake = {"music/fake_song.ogg": b"RIFF" + bytes(3000)}
        self.api.add(item("night_train", "music", song, acquisition="free", price=0), song)
        self.api.add(item("fake_song", "music", fake, acquisition="free", price=0), fake)
        self.api.owned = ["night_train", "fake_song"]
        store = self.store()
        store.sync_async(force=True)
        self.assertTrue(wait(store))
        self.assertEqual([p.name for p in store.music_files()], ["night_train.ogg"], "only a real OGG is kept")
        self.assertTrue(safe_path("music/night_train.ogg"))
        self.assertFalse(safe_path("music/../x.ogg"))

    def test_owned_files_are_downloaded_verified_and_registered(self):
        sprite = {"sprites/gold_pear.png": png()}
        theme = {"themes/ocean/board/board.png": png((1, 2, 3)), "themes/ocean/palette.json": b'{"WOOD":[1,2,3]}'}
        self.api.add(item("gold_pear", "card", sprite), sprite)
        self.api.add(item("ocean", "board_theme", theme, price=100), theme)
        self.api.owned = ["gold_pear"]
        store = self.store()
        self.assertTrue(store.sync_async(force=True))
        self.assertTrue(wait(store))
        self.assertTrue((self.tmp / "content" / "sprites" / "gold_pear.png").is_file())
        self.assertFalse((self.tmp / "content" / "themes").exists(), "files of items the player does not own are not downloaded")
        self.assertIn("gold_pear", config.PREMIUM_CARDS)
        self.assertEqual(store.owned_cards(), ["gold_pear"])
        ids = [row[0] for row in config.BOARD_THEMES]
        self.assertIn("ocean", ids, "an unowned theme is listed, locked, with how to get it")
        self.assertFalse(cosmetics.is_unlocked("item:ocean", set()))
        self.assertIn("Shop: 100", cosmetics.requirement("item:ocean"))
        self.api.owned = ["gold_pear", "ocean"]
        store.sync_async(force=True)
        self.assertTrue(wait(store))
        self.assertTrue(cosmetics.is_unlocked("item:ocean", set()))
        self.assertTrue((store.theme_dir("ocean") / "board" / "board.png").is_file())
        self.assertEqual(store.theme_dir("emerald"), config.THEMES_DIR / "emerald", "built-in looks win")

    def test_a_file_that_does_not_match_its_hash_is_rejected(self):
        good = png()
        entry = item("bad_card", "card", {"sprites/bad_card.png": good})
        self.api.items.append(entry)
        self.api.blobs[entry["files"]["sprites/bad_card.png"]["hash"]] = png((9, 9, 9))      # different content under that hash
        self.api.owned = ["bad_card"]
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        self.assertFalse((self.tmp / "content" / "sprites" / "bad_card.png").exists())
        self.assertEqual(store.owned_cards(), [], "a card without its sprite is never offered")

    def test_a_png_must_be_a_png_and_paths_must_be_known_shapes(self):
        not_png = b"<html>hello</html>"
        self.api.add(item("fake_card", "card", {"sprites/fake_card.png": not_png}), {"x": not_png})
        evil = png()
        self.api.add(item("evil", "card", {"../../escape.png": evil, "sprites/ok_name.exe": evil, "themes/x/../../y.png": evil}), {"x": evil})
        self.api.owned = ["fake_card", "evil"]
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        self.assertFalse((self.tmp / "content" / "sprites" / "fake_card.png").exists())
        self.assertFalse((self.tmp.parent / "escape.png").exists())
        for rel in ("../x.png", "/etc/passwd", "sprites/a.png", "sprites/Bad.png", "themes/ocean/hud/other.png", "sprites/ok.png.exe"):
            self.assertFalse(safe_path(rel), rel)
        for rel in ("sprites/gold_pear.png", "card_styles/gold/red_apple.png", "themes/ocean/hud/panel.png", "themes/ocean/palette.json", "avatars/face_one.png"):
            self.assertTrue(safe_path(rel), rel)

    def test_offline_and_old_clients_keep_what_they_have(self):
        sprite = {"sprites/gold_pear.png": png()}
        self.api.add(item("gold_pear", "card", sprite), sprite)
        self.api.owned = ["gold_pear"]
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        self.api.down = True
        store.sync_async(force=True)
        self.assertFalse(wait(store))
        self.assertEqual(store.owned_cards(), ["gold_pear"], "the cache still works offline")
        again = self.store()                                         # a restart without network
        self.assertIn("gold_pear", config.PREMIUM_CARDS)
        self.assertEqual(again.owned_cards(), ["gold_pear"])
        self.api.down = False
        self.api.schema = 99                                         # a newer server format this build does not know
        store.sync_async(force=True)
        self.assertFalse(wait(store))
        self.assertIn("Update", store.last_error)
        self.assertEqual(store.owned_cards(), ["gold_pear"])

    def test_syncs_are_rate_limited_until_forced(self):
        store = self.store()
        self.assertTrue(store.sync_async())
        store.task.join()
        store.poll()
        self.assertFalse(store.sync_async(), "just synced")
        self.assertTrue(store.sync_async(force=True))


class InTheGame(ContentCase):
    def test_a_server_card_joins_the_collection_and_its_sprite_is_found(self):
        sprite = {"sprites/gold_pear.png": png((250, 200, 0))}
        self.api.add(item("gold_pear", "card", sprite), sprite)
        self.api.owned = ["gold_pear"]
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        collection = Collection({})
        self.assertTrue(collection.grant("gold_pear"))
        self.assertIn("gold_pear", collection.unlocked)
        pygame.display.init()
        pygame.display.set_mode((8, 8))
        assets = AssetManager(config.SPRITES_DIR)
        assets.extra_sprites_dir = store.sprites_dir
        self.assertEqual(assets.sprite("gold_pear").get_size(), (16, 16))
        self.assertEqual(assets.sprite("gold_pear").get_at((0, 0))[:3], (250, 200, 0), "it is the downloaded picture, not the question mark")

    def test_a_card_that_is_gone_from_the_server_no_longer_counts(self):
        sprite = {"sprites/gold_pear.png": png()}
        self.api.add(item("gold_pear", "card", sprite), sprite)
        self.api.owned = ["gold_pear"]
        store = self.store()
        store.sync_async(force=True)
        wait(store)
        collection = Collection({})
        collection.grant("gold_pear")
        saved = collection.to_dict()
        self.api.items.clear()
        store.sync_async(force=True)
        wait(store)
        self.assertNotIn("gold_pear", config.PREMIUM_CARDS)
        self.assertNotIn("gold_pear", Collection(saved).unlocked)


if __name__ == "__main__":
    unittest.main()

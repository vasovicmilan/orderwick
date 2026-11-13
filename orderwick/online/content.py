"""Content that comes from the server: extra cards, card styles and board themes.

The game ships with a complete set of its own and keeps working without a network. When online, it asks the server for the
list of content (the "manifest") and which items this player owns, downloads the files of owned items into a cache folder
next to the save files, and registers them: new cards become premium cards, new styles and themes appear in Settings.

Only DATA is ever loaded (PNG pictures and one small JSON palette per theme), never code. Every file is checked: its path
must be one of the known shapes, its size is capped, its SHA-256 must match the manifest and PNGs must really be PNGs.
Anything that fails is skipped and the game keeps what it had.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from .. import config
from ..core import cosmetics
from ..data.storage import JsonStore, default_data_dir
from ..engine.tasks import BackgroundTask
from .client import OnlineError

SCHEMA = 1                      # manifest format this game understands
MAX_FILE = 600 * 1024
MAX_MUSIC = 6 * 1024 * 1024        # a song (OGG) may be bigger than a picture
OGG_SIGNATURE = b"OggS"
MAX_FILES_PER_SYNC = 400
SYNC_EVERY = 15 * 60            # seconds between automatic syncs
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_NAME = r"[a-z0-9_]{3,40}"
_PATH_RE = re.compile(
    rf"^(sprites/{_NAME}\.png"
    rf"|avatars/{_NAME}\.png"
    rf"|music/{_NAME}\.ogg"
    rf"|card_styles/{_NAME}/[a-z0-9_]{{2,40}}\.png"
    rf"|themes/{_NAME}/(board/board\.png|hud/(panel|inset|button|divider|icons|icons_audio)\.png|palette\.json))$")


def safe_path(rel: str) -> bool:
    return isinstance(rel, str) and bool(_PATH_RE.match(rel))


class ContentStore:
    def __init__(self, client=None, store: JsonStore | None = None, directory: Path | None = None):
        base = directory or default_data_dir()
        self.dir = base / "content"
        self.store = store or JsonStore("content.json", directory)
        self.state = self.store.load({"manifest": {}, "owned": []})
        self.client = client
        self.task: BackgroundTask | None = None
        self.last_sync = -SYNC_EVERY
        self.last_error = ""
        self._cards: set[str] = set()
        self.register()

    # ---- what is known -------------------------------------------------------------------------------------
    @property
    def items(self) -> list[dict]:
        manifest = self.state.get("manifest") or {}
        return manifest.get("items", []) if manifest.get("schema") == SCHEMA else []

    @property
    def owned(self) -> set[str]:
        return set(self.state.get("owned") or [])

    def owned_cards(self) -> list[str]:
        return [i["code"] for i in self.items if i["kind"] == "card" and i["code"] in self.owned and self._present(i)]

    def music_files(self) -> list[Path]:
        """Songs the player owns (free ones included) that are fully downloaded: the game adds them to its playlist."""
        found = []
        for item in self.items:
            if item.get("kind") != "music" or item["code"] not in self.owned or not self._present(item):
                continue
            found += [self.dir / rel for rel in item.get("files", {}) if rel.endswith(".ogg")]
        return sorted(found)

    def _present(self, item: dict) -> bool:
        return all(safe_path(rel) and (self.dir / rel).is_file() for rel in item.get("files", {}))

    # ---- registering into the game --------------------------------------------------------------------------
    def register(self) -> None:
        """Makes the known items visible to the rest of the game. Safe to call again after every sync."""
        for name in self._cards:
            config.PREMIUM_CARDS.pop(name, None)
        self._cards = set()
        for table in (config.BOARD_THEMES, config.CARD_STYLES):
            table[:] = [row for row in table if not str(row[2] or "").startswith("item:")]
        cosmetics.OWNED = set(self.owned)
        cosmetics.ITEM_INFO.clear()
        for item in self.items:
            code, kind = item["code"], item["kind"]
            cosmetics.ITEM_INFO[code] = _how_to_get(item)
            if kind == "card" and code not in config.PREMIUM_CARDS:
                config.PREMIUM_CARDS[code] = ""                      # "" = no achievement in the game itself: the server decides
                self._cards.add(code)
            elif kind == "board_theme":
                config.BOARD_THEMES.append((code, item["name"], f"item:{code}"))
            elif kind == "card_style":
                config.CARD_STYLES.append((code, item["name"], f"item:{code}"))

    def theme_dir(self, theme_id: str) -> Path:
        built_in = config.THEMES_DIR / theme_id
        return built_in if built_in.exists() else self.dir / "themes" / theme_id

    def card_style_dir(self, style_id: str) -> Path:
        built_in = config.CARD_STYLES_DIR / style_id
        return built_in if built_in.exists() else self.dir / "card_styles" / style_id

    @property
    def sprites_dir(self) -> Path:
        return self.dir / "sprites"

    # ---- syncing (the network part runs in a background thread) ---------------------------------------------------------
    def sync_async(self, force: bool = False) -> bool:
        """Starts a sync unless one is running or the last one was recent. Returns True if one was started."""
        if self.client is None or (self.task is not None and not self.task.done):
            return False
        if not force and time.time() - self.last_sync < SYNC_EVERY:
            return False
        self.last_sync = time.time()
        self.task = BackgroundTask(self._work)
        return True

    def _work(self) -> dict:
        manifest = self.client.content_manifest()
        if manifest.get("schema") != SCHEMA:
            raise OnlineError("old_client", "Update the game to get the newest content.")
        inventory = self.client.inventory()
        owned = [c for c in inventory.get("owned", []) if isinstance(c, str)]
        fetched = 0
        for item in manifest.get("items", []):
            if item.get("code") not in owned:
                continue
            for rel, meta in (item.get("files") or {}).items():
                fetched += 1
                if fetched > MAX_FILES_PER_SYNC:
                    break
                self._ensure(rel, meta)
        return {"manifest": manifest, "owned": owned, "currency": inventory.get("currency")}

    def _ensure(self, rel: str, meta: dict) -> bool:
        """Makes sure one file is in the cache with exactly the content the manifest promises. False = skipped."""
        if not safe_path(rel) or not isinstance(meta, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(meta.get("hash", ""))):
            return False
        target = self.dir / rel
        want = meta["hash"]
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == want:
            return True
        try:
            data = self.client.download(want)
        except OnlineError:
            return False
        if len(data) > (MAX_MUSIC if rel.endswith(".ogg") else MAX_FILE) or hashlib.sha256(data).hexdigest() != want:
            return False
        if rel.endswith(".ogg") and not data.startswith(OGG_SIGNATURE):
            return False
        if rel.endswith(".png") and not data.startswith(PNG_SIGNATURE):
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)
        return True

    def poll(self) -> bool:
        """Main thread, every frame. True when a sync just finished with new data (the game then refreshes its looks)."""
        task = self.task
        if task is None or not task.done:
            return False
        self.task = None
        if task.error is not None:
            self.last_error = getattr(task.error, "message", "") or "Content sync failed."
            return False
        result = task.result or {}
        self.last_error = ""
        self.state.update(manifest=result["manifest"], owned=result["owned"])
        self.store.save(self.state)
        self.register()
        return True


def _how_to_get(item: dict) -> str:
    how = item.get("acquisition")
    if how == "shop":
        return f"Shop: {item.get('price', 0)} coins (website)"
    if how == "achievement":
        a = item.get("achievement") or {}
        return f"Trophy: {a.get('title', a.get('code', ''))}"
    if how == "free":
        return ""
    return "A gift from the author"

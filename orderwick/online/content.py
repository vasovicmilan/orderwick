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
import threading
import time
from pathlib import Path

from .. import config
from ..core import cardsets, cosmetics
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
    rf"|card_sets/{_NAME}/([a-z0-9_]{{2,40}}\.png|families\.json)"
    rf"|themes/{_NAME}/(board/board\.png|hud/(panel|inset|button|divider|icons|icons_audio)\.png|palette\.json|frame\.json))$")


def safe_path(rel: str) -> bool:
    return isinstance(rel, str) and bool(_PATH_RE.match(rel))


# The first season songs were published before the naming rule "<theme>_<name>" existed.
LEGACY_SEASON_TRACKS = {"winter_frost": "frost", "christmas_eve": "christmas", "easter_meadow": "easter"}


def is_season_track(code: str, theme: str) -> bool:
    """A song belongs to a board theme when its code is "<theme>_<name>" (or one of the first three, listed above)."""
    return bool(theme) and (str(code).startswith(theme + "_") or LEGACY_SEASON_TRACKS.get(code) == theme)


class ContentStore:
    def __init__(self, client=None, store: JsonStore | None = None, directory: Path | None = None):
        base = directory or default_data_dir()
        self.dir = base / "content"
        self.store = store or JsonStore("content.json", directory)
        self.state = self.store.load({"manifest": {}, "owned": [], "season": None, "daily": None})
        self.client = client
        self.task: BackgroundTask | None = None
        self.lent_task: BackgroundTask | None = None
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

    @property
    def season(self) -> dict | None:
        """The live season as the last sync saw it ({code, name, theme, ends}); None once its time is over."""
        season = self.state.get("season")
        if isinstance(season, dict) and float(season.get("ends", 0)) > time.time():
            return season
        return None

    @property
    def daily(self) -> dict | None:
        """Today's look of the daily board as the last sync saw it ({date, theme, style, set}); None on another day."""
        daily = self.state.get("daily")
        return daily if isinstance(daily, dict) and daily.get("date") == time.strftime("%Y-%m-%d", time.gmtime()) else None

    def _usable(self, kind: str, code: str | None) -> bool:
        """Can this theme / card style / card set be shown right now? (shipped with the game, or its files are on disk)"""
        if not code:
            return False
        if kind == "board_theme" and (config.THEMES_DIR / code).exists():
            return True
        if kind == "card_style" and (config.CARD_STYLES_DIR / code).exists():
            return True
        if kind == "card_set" and code == cardsets.DEFAULT_SET:
            return True
        item = next((i for i in self.items if i["code"] == code and i["kind"] == kind), None)
        return bool(item and self._present(item))

    def lent_look(self, mode_id: str) -> dict:
        """The look every player gets in a Season or Daily run: {"theme", "style", "set"} (each None when there is none or it is not ready)
        plus "families" of the set when it is a downloaded one. {} for other modes."""
        source = self.season if mode_id == "season" else self.daily if mode_id == "daily" else None
        if not source:
            return {}
        look = {"theme": source.get("theme") if self._usable("board_theme", source.get("theme")) else None,
                "style": source.get("style") if self._usable("card_style", source.get("style")) else None,
                "set": source.get("set") if self._usable("card_set", source.get("set")) else None, "families": None,
                "avatar": source.get("avatar") if self.lent_avatar(mode_id) is not None else None}
        if look["set"] and look["set"] != cardsets.DEFAULT_SET:
            look["families"] = cardsets.load_families(self.card_set_dir(look["set"]))
            if look["families"] is None:
                look["set"] = None
        return look

    def lent_avatar(self, mode_id: str):
        """The avatar a Season lends (the speaker during its runs): a Portrait, or None when there is none or its files are not here yet."""
        source = self.season if mode_id == "season" else None
        code = (source or {}).get("avatar")
        if not code or not safe_path(f"avatars/{code}.png"):
            return None
        from .avatar import load_portrait
        for name in (f"{code}_talk.png", f"{code}.png"):          # the talking strip first, a still picture works too
            path = self.dir / "avatars" / name
            try:
                portrait = load_portrait(path.read_bytes()) if path.is_file() else None
            except OSError:
                portrait = None
            if portrait is not None:
                return portrait
        return None

    def card_set_dir(self, set_id: str) -> Path | None:
        return None if set_id in (None, "", cardsets.DEFAULT_SET) else self.dir / "card_sets" / set_id

    def lent_theme(self) -> str | None:
        """The season's board theme, lent to everybody while the season runs (only once its files are on disk)."""
        season = self.season
        if not season:
            return None
        item = next((i for i in self.items if i["code"] == season.get("theme") and i["kind"] == "board_theme"), None)
        return season["theme"] if item and self._present(item) else None

    def season_music_files(self) -> list[Path]:
        """The season's own songs (lent to everybody while it runs, like its board): played instead of the normal playlist in a Season run."""
        season = self.season
        if not season:
            return []
        wanted = set(season.get("music") or [])
        found = []
        for item in self.items:
            if item.get("kind") == "music" and item["code"] in wanted and self._present(item):
                found += [self.dir / rel for rel in item.get("files", {}) if rel.endswith(".ogg")]
        return sorted(found)

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
        cosmetics.OWNED = set(self.owned) | ({self.lent_theme()} if self.lent_theme() else set())
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
        self.lent_task = BackgroundTask(self._lent_work)          # the look of the season / of today's board first: it is small, the owned items can take long
        self.task = BackgroundTask(self._work)
        return True

    def _lent_work(self) -> dict:
        manifest = self.client.content_manifest()
        if manifest.get("schema") != SCHEMA:
            raise OnlineError("old_client", "Update the game to get the newest content.")
        return {"manifest": manifest, "season": self._season_work(manifest), "daily": self._daily_work(manifest)}

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
        season = self._season_work(manifest)
        daily = self._daily_work(manifest)
        return {"manifest": manifest, "owned": owned, "currency": inventory.get("currency"), "season": season, "daily": daily}

    def _season_work(self, manifest: dict) -> dict | None:
        """The live season and its theme: the theme's files are fetched for everybody, owner or not (it is lent)."""
        try:
            live = (self.client.season() or {}).get("active")
        except OnlineError:
            return self.state.get("season")                 # offline: keep what we knew
        if not live:
            return None
        theme = (live.get("theme") or {}).get("code")
        item = next((i for i in manifest.get("items", []) if i.get("code") == theme), None)
        if item is None:
            return None
        for rel, meta in (item.get("files") or {}).items():
            self._ensure(rel, meta)
        music = [i["code"] for i in manifest.get("items", []) if i.get("kind") == "music" and is_season_track(i.get("code", ""), theme)]
        for track in manifest.get("items", []):
            if track.get("code") in music:                   # the songs that belong to the board are lent too
                for rel, meta in (track.get("files") or {}).items():
                    self._ensure(rel, meta)
        ends = time.time() + max(0, int(live.get("remainingSeconds", 0)))
        style, card_set, avatar = (live.get("cardStyle") or {}).get("code"), (live.get("cardSet") or {}).get("code"), (live.get("avatar") or {}).get("code")
        self._fetch_lent(manifest, style, card_set, avatar)
        return {"code": live.get("code", ""), "name": live.get("name", ""), "theme": theme, "style": style, "set": card_set, "avatar": avatar, "ends": ends, "music": music}

    def _fetch_lent(self, manifest: dict, *codes: str | None) -> None:
        """Downloads the files of items that are lent to everybody (the look of a season or of today's daily board), owner or not."""
        for code in codes:
            item = next((i for i in manifest.get("items", []) if i.get("code") == code), None)
            for rel, meta in ((item or {}).get("files") or {}).items():
                self._ensure(rel, meta)

    def _daily_work(self, manifest: dict) -> dict | None:
        """Today's random look of the daily board (theme, card background, card set): fetched for everybody, it is lent for the day."""
        try:
            look = (self.client.daily() or {}).get("look") or {}
        except OnlineError:
            return self.state.get("daily")                  # offline: keep what we knew
        theme, style, card_set = (look.get("theme") or {}).get("code"), (look.get("cardStyle") or {}).get("code"), (look.get("cardSet") or {}).get("code")
        self._fetch_lent(manifest, theme, style, card_set)
        return {"date": look.get("date") or time.strftime("%Y-%m-%d", time.gmtime()), "theme": theme, "style": style, "set": card_set}

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
        tmp = target.with_suffix(f"{target.suffix}.{threading.get_ident()}.part")      # two syncs may fetch the same file at once
        try:
            tmp.write_bytes(data)
            tmp.replace(target)
        except OSError:
            return False
        return True

    def poll(self) -> bool:
        """Main thread, every frame. True when a sync just finished with new data (the game then refreshes its looks)."""
        lent = self.lent_task
        if lent is not None and lent.done:                       # the lent look arrived before the full sync: show it at once
            self.lent_task = None
            if lent.error is None and lent.result and self.task is not None and not self.task.done:
                self.state.update(manifest=lent.result["manifest"], season=lent.result["season"], daily=lent.result["daily"])
                self.register()
                return True
        task = self.task
        if task is None or not task.done:
            return False
        self.task = None
        if task.error is not None:
            self.last_error = getattr(task.error, "message", "") or "Content sync failed."
            return False
        result = task.result or {}
        self.last_error = ""
        self.state.update(manifest=result["manifest"], owned=result["owned"], season=result.get("season"), daily=result.get("daily"))
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

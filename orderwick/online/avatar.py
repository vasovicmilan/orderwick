"""The speaker: the avatar of the player, shown in the HUD where the game "talks" to them.

An avatar is a strip of 32x32 frames (mouth closed, small, wide, small). The game ships with one (works offline); when
online it asks the server for the strip of the avatar the player wears (`/avatar/<name>/talk.png`, or the still picture
when the avatar has no strip) and keeps the last one in the cache folder. Only a PNG of a known size is ever accepted.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pygame

from .. import config
from ..engine.tasks import BackgroundTask
from .client import OnlineError

FRAME = 32
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REFRESH_EVERY = 15 * 60                                  # seconds between checks (the player may change avatars on the website)
TALK_SEQUENCE = (1, 2, 1, 0, 2, 1, 2, 0)                 # frames while speaking: a calm, uneven mouth
TALK_FPS = 11


class Portrait:
    """The frames of one avatar. A single still picture works too (it just does not move its mouth)."""

    def __init__(self, sheet: pygame.Surface):
        count = max(1, sheet.get_width() // FRAME)
        self.frames = [sheet.subsurface(pygame.Rect(i * FRAME, 0, FRAME, FRAME)).copy() for i in range(count)]

    def frame(self, talking: bool, now: float) -> pygame.Surface:
        if not talking or len(self.frames) < 3:
            return self.frames[0]
        index = TALK_SEQUENCE[int(now * TALK_FPS) % len(TALK_SEQUENCE)]
        return self.frames[min(index, len(self.frames) - 1)]


def load_portrait(data: bytes) -> Portrait | None:
    """A portrait from PNG bytes, or None when it is not exactly a 32x32 picture or a 128x32 strip."""
    if not data.startswith(PNG_SIGNATURE) or len(data) > 64 * 1024:
        return None
    try:
        sheet = pygame.image.load(io.BytesIO(data)).convert_alpha()
    except (pygame.error, ValueError):
        return None
    return Portrait(sheet) if sheet.get_size() in ((FRAME, FRAME), (4 * FRAME, FRAME)) else None


class AvatarVoice:
    def __init__(self, cache_dir: Path | None = None):
        self.cache = cache_dir / "avatar_talk.png" if cache_dir else None
        self.task: BackgroundTask | None = None
        self.last_try = 0.0
        self.portrait = self._default()
        if self.cache and self.cache.is_file():
            try:
                cached = load_portrait(self.cache.read_bytes())
            except OSError:
                cached = None
            if cached:
                self.portrait = cached

    @staticmethod
    def _default() -> Portrait:
        try:
            found = load_portrait(config.AVATAR_DEFAULT.read_bytes())
        except OSError:
            found = None
        if found is None:                                  # never leave the game without a speaker
            blank = pygame.Surface((4 * FRAME, FRAME), pygame.SRCALPHA)
            found = Portrait(blank)
        return found

    override: Portrait | None = None                      # a Season lends its own avatar for the run: it beats the player's

    @property
    def shown(self) -> Portrait:
        return self.override or self.portrait

    def refresh_async(self, client, nickname: str, force: bool = False) -> bool:
        """nickname "" = ask the server who the key belongs to first (an AI agent never saves its nickname locally)."""
        if client is None or (self.task is not None and not self.task.done):
            return False
        if not force and time.time() - self.last_try < REFRESH_EVERY:
            return False
        self.last_try = time.time()
        self.task = BackgroundTask(self._fetch, client, nickname)
        return True

    @staticmethod
    def _fetch(client, nickname: str):
        """Asks the server who the key belongs to (the name may have been changed on the website, and the avatar code
        keeps a cached picture from hiding a new one), then downloads the pictures."""
        try:
            me = client.me()
            nickname, version = me.get("nickname") or nickname, me.get("avatar") or ""
        except OnlineError:
            version = ""
            if not nickname:
                raise
        return client.avatar_pictures(nickname, version)

    def poll(self) -> bool:
        """Main thread, every frame. True when a new picture arrived."""
        task = self.task
        if task is None or not task.done:
            return False
        self.task = None
        if task.error is not None or not task.result:
            return False
        strip, still = task.result
        for data in (strip, still):
            portrait = load_portrait(data) if data else None
            if portrait is not None:
                self.portrait = portrait
                if self.cache is not None:
                    try:
                        self.cache.parent.mkdir(parents=True, exist_ok=True)
                        self.cache.write_bytes(data)
                    except OSError:
                        pass
                return True
        return False

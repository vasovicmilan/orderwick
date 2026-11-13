"""Sound: effects with slight pitch variations + music in random order with pauses.

Against fatigue: every effect has several "pitch" variants (a different one is picked each time), card
pairing plays a climbing pentatonic scale, and the music switches songs with silence in between. If there is no
sound card (or the mixer does not work), every function is silent and the game runs without sound.
"""
from __future__ import annotations

import functools
import os
import random
import re
from pathlib import Path

import pygame

from .. import config
from .logs import log_error


def _safe(fn):
    """Sound must never crash the game: every error goes to crash.log, and after 3 errors the sound is turned off."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if not self.ready:
            return None
        try:
            return fn(self, *args, **kwargs)
        except Exception as exc:                      # pygame.error, MemoryError from the mixer, ...
            self.errors += 1
            log_error(f"audio.{fn.__name__} failed ({self.errors})", exc)
            if self.errors >= 3:
                self.ready = False
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
            return None
    return wrapper


def _gain(percent: int) -> float:
    """0-100 -> amplitude (square curve: the volume feels more even)."""
    return max(0.0, min(1.0, percent / 100.0)) ** 2


class Audio:
    GAP = (2.0, 6.0)              # silence between two songs (seconds)
    MUSIC_GAIN = 0.4              # background music stays well under the effects

    def __init__(self) -> None:
        self.ready = False
        self.settings = dict(config.DEFAULT_SETTINGS)
        self.sfx: dict[str, list[pygame.mixer.Sound]] = {}
        self.tracks: list[Path] = []
        self._last: dict[str, int] = {}
        self._bag: list[Path] = []
        self._last_track: Path | None = None
        self._last_timbre = ""
        self._gap = 1.5
        self._playing = False
        self.rng = random.Random()
        self.errors = 0

    # ---- pokretanje ---------------------------------------------------------------------------
    def init(self, directory: Path, settings: dict) -> bool:
        self.settings = settings
        if os.environ.get("ORDERWICK_NO_AUDIO"):          # switch: python main.py --no-audio
            self.ready = False
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 1024)       # bigger buffer: no crackling when a Python thread is busy
            pygame.mixer.set_num_channels(16)
        except Exception as exc:
            log_error("mixer init failed", exc)
            self.ready = False
            return False
        sfx_dir = Path(directory) / "sfx"
        groups: dict[str, list[tuple[int, Path]]] = {}
        for f in sorted(sfx_dir.glob("*.wav")):
            m = re.match(r"(.+)_(\d+)$", f.stem)
            if m:
                groups.setdefault(m.group(1), []).append((int(m.group(2)), f))
        for name, files in groups.items():
            try:
                self.sfx[name] = [pygame.mixer.Sound(str(p)) for _i, p in sorted(files)]
            except pygame.error:
                continue
        self.directory = Path(directory)
        self.tracks = sorted((Path(directory) / "music").glob("*.ogg"))
        self.ready = True
        self.apply()
        return self.ready

    def shutdown(self) -> None:
        """Stops everything and closes the mixer cleanly (quitting with music still streaming can crash some audio backends)."""
        if not pygame.mixer.get_init():
            self.ready = False
            return
        self.ready = False                                  # no more play()/update() calls from now on
        for step in (pygame.mixer.music.stop, getattr(pygame.mixer.music, "unload", None), pygame.mixer.stop,
                     pygame.mixer.quit):
            if step is None:
                continue
            try:
                step()
            except Exception as exc:                        # keep going: the next step may still work
                log_error(f"audio shutdown step failed: {getattr(step, '__name__', step)}", exc)

    # ---- podesavanja ------------------------------------------------------------------------------
    @_safe
    def apply(self) -> None:
        """Applies volume and on/off (called after every change in settings)."""
        if not self.ready:
            return
        s = self.settings
        pygame.mixer.music.set_volume(_gain(s["music_vol"]) * self.MUSIC_GAIN if s["music_on"] else 0.0)
        if not s["music_on"] and self._playing:
            pygame.mixer.music.fadeout(400)
            self._playing = False
        elif s["music_on"] and not self._playing:
            self._gap = min(self._gap, 1.0)

    # ---- efekti ------------------------------------------------------------------------------------
    def _pick(self, name: str) -> pygame.mixer.Sound | None:
        variants = self.sfx.get(name)
        if not variants:
            return None
        idx = self.rng.randrange(len(variants))
        if len(variants) > 1 and idx == self._last.get(name):
            idx = (idx + 1 + self.rng.randrange(len(variants) - 1)) % len(variants)
        self._last[name] = idx
        return variants[idx]

    @_safe
    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.ready or not self.settings["sfx_on"]:
            return
        snd = self._pick(name)
        if snd is not None:
            snd.set_volume(_gain(self.settings["sfx_vol"]) * config.SFX_GAIN.get(name, 1.0) * volume)
            snd.play()

    @_safe
    def play_pair(self, step: int) -> None:
        """Card pairing: a note of the pentatonic scale (step grows with a series of consecutive pairings)."""
        if not self.ready or not self.settings["sfx_on"]:
            return
        timbres = [n for n in ("pairA", "pairB", "pairC") if self.sfx.get(n)]
        if not timbres:
            return
        pick = self.rng.choice([t for t in timbres if t != self._last_timbre] or timbres)
        self._last_timbre = pick
        notes = self.sfx[pick]
        period = 2 * (len(notes) - 1)                       # the scale goes up and then back down (no getting stuck at the top)
        pos = step % period
        idx = pos if pos < len(notes) else period - pos
        snd = notes[idx]
        jitter = self.rng.uniform(0.7, 1.0)                 # every note at a slightly different volume
        snd.set_volume(_gain(self.settings["sfx_vol"]) * config.SFX_GAIN["pair"] * jitter)
        snd.play()

    # ---- muzika --------------------------------------------------------------------------------------
    def set_extra_tracks(self, paths) -> None:
        """Songs that came from the server join the built-in ones (the playlist is reshuffled when the set changes)."""
        built_in = sorted((Path(self.directory) / "music").glob("*.ogg")) if getattr(self, "directory", None) else self.tracks
        wanted = built_in + [Path(p) for p in paths if Path(p).is_file()]
        if wanted != self.tracks:
            self.tracks = wanted
            self._bag = []

    def _next_track(self) -> Path | None:
        if not self.tracks:
            return None
        if not self._bag:
            self._bag = self.tracks[:]
            self.rng.shuffle(self._bag)
            if len(self._bag) > 1 and self._bag[-1] == self._last_track:
                self._bag[0], self._bag[-1] = self._bag[-1], self._bag[0]
        self._last_track = self._bag.pop()
        return self._last_track

    @_safe
    def update(self, dt: float) -> None:
        if not self.ready or not self.settings["music_on"]:
            return
        if self._playing and pygame.mixer.music.get_busy():
            return
        if self._playing:                                   # the song ended: silence, then the next one
            self._playing = False
            self._gap = self.rng.uniform(*self.GAP)
        self._gap -= dt
        if self._gap > 0:
            return
        track = self._next_track()
        if track is None:
            return
        try:
            pygame.mixer.music.load(str(track))
            pygame.mixer.music.play(fade_ms=2500)
            self._playing = True
        except pygame.error as exc:                         # broken file: skip the song, do not crash the game
            log_error(f"cannot play {track.name}", exc)
            self._gap = 2.0


class RemoteAudio:
    """What the game talks to: the same API as `Audio`, but the sound itself runs in a separate process (audio_worker.py).

    * every call only puts a small message into a queue, so the game never waits for audio;
    * if the worker dies (crash, no sound card, ...) `ready` becomes False and the game continues without sound;
    * ORDERWICK_AUDIO=off disables sound, =inproc plays inside the game process (debugging only).
    """

    def __init__(self) -> None:
        self.ready = False
        self.settings = dict(config.DEFAULT_SETTINGS)
        self._local: Audio | None = None
        self._proc = None
        self._queue = None
        self._since_check = 0.0

    def init(self, directory: Path, settings: dict) -> bool:
        self.settings = settings
        mode = os.environ.get("ORDERWICK_AUDIO", "")
        if os.environ.get("ORDERWICK_NO_AUDIO") or mode == "off":
            return False
        if mode == "inproc":
            self._local = Audio()
            self.ready = self._local.init(directory, settings)
            return self.ready
        try:
            import multiprocessing
            import queue
            import threading
            from ..audio_worker import run
            ctx = multiprocessing.get_context("spawn")
            parent, child = ctx.Pipe()
            self._proc = ctx.Process(target=run, args=(child, str(directory), dict(settings)), daemon=True)
            self._proc.start()
            child.close()
            self._queue = queue.Queue()
            threading.Thread(target=self._writer, args=(parent, self._queue), daemon=True).start()
            self.ready = True
        except Exception as exc:                                     # noqa: BLE001
            log_error("cannot start the audio process", exc)
            self.ready = False
        return self.ready

    def _writer(self, conn, q) -> None:
        """Sends queued messages; the only place that can block, and it is a background thread."""
        while True:
            msg = q.get()
            if msg is None:
                break
            try:
                conn.send(msg)
            except (OSError, EOFError, ValueError):
                self.ready = False                                   # worker is gone
                break

    def _send(self, *msg) -> None:
        if self.ready and self._queue is not None:
            self._queue.put(msg)

    # ---- same API as Audio ----------------------------------------------------------------------
    def apply(self) -> None:
        if self._local is not None:
            self._local.apply()
        else:
            self._send("settings", dict(self.settings))

    def play(self, name: str, volume: float = 1.0) -> None:
        if self._local is not None:
            self._local.play(name, volume)
        elif self.settings.get("sfx_on", True):
            self._send("play", name, volume)

    def play_pair(self, step: int) -> None:
        if self._local is not None:
            self._local.play_pair(step)
        elif self.settings.get("sfx_on", True):
            self._send("pair", step)

    def set_extra_tracks(self, paths) -> None:
        paths = [str(p) for p in paths]
        if self._local is not None:
            self._local.set_extra_tracks(paths)
        else:
            self._send("tracks", paths)

    def update(self, dt: float) -> None:
        if self._local is not None:
            self._local.update(dt)
            return
        self._since_check += dt
        if self.ready and self._since_check > 1.0:
            self._since_check = 0.0
            if self._proc is not None and not self._proc.is_alive():
                self.ready = False
                log_error(f"audio process ended (exit code {self._proc.exitcode}); the game continues without sound")

    def shutdown(self) -> None:
        """Ends the sound process (politely, then by force). Never raises, never waits long."""
        was_ready, self.ready = self.ready, False
        if self._local is not None:
            self._local.shutdown()
            return
        if self._queue is not None:
            self._queue.put(("quit",) if was_ready else None)
            self._queue.put(None)
        proc = self._proc
        if proc is not None:
            try:
                proc.join(0.4)
                if proc.is_alive():
                    proc.kill()
                    proc.join(0.5)
            except Exception as exc:                                 # noqa: BLE001
                log_error("audio process shutdown", exc)
            self._proc = None


audio = RemoteAudio()

"""The sound process. All audio (mixer, music, effects) lives HERE, not in the game process.

Why: native audio libraries (SDL_mixer, PulseAudio/PipeWire, ALSA) can crash or hang while starting a song or while shutting down.
In a separate process such a crash cannot take the game with it: the game just notices that the worker is gone and plays on
silently. On exit the game simply ends this process.

Protocol (multiprocessing pipe, tuples): ("play", name, volume) · ("pair", step) · ("settings", dict) · ("tracks", [paths]) · ("quit",)
The worker answers once with ("ready",) or ("failed",).
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def run(conn, directory: str, settings: dict) -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")               # no window is ever needed here
    from .engine.audio import Audio
    from .engine.logs import log_error

    audio = Audio()
    try:
        ok = audio.init(Path(directory), dict(settings))
    except Exception as exc:                                         # noqa: BLE001
        log_error("audio worker: init failed", exc)
        ok = False
    try:
        conn.send(("ready",) if ok else ("failed",))
    except (OSError, EOFError):
        os._exit(0)
    if ok:
        last = time.monotonic()
        try:
            while True:
                if conn.poll(0.05):
                    msg = conn.recv()
                    cmd = msg[0]
                    if cmd == "quit":
                        break
                    if cmd == "play":
                        audio.play(msg[1], msg[2])
                    elif cmd == "pair":
                        audio.play_pair(msg[1])
                    elif cmd == "tracks":
                        audio.set_extra_tracks(msg[1])
                    elif cmd == "settings":
                        audio.settings.update(msg[1])
                        audio.apply()
                now = time.monotonic()
                audio.update(now - last)                             # music playlist
                last = now
        except (EOFError, OSError):                                  # the game is gone: stop making noise
            pass
        except Exception as exc:                                     # noqa: BLE001
            log_error("audio worker crashed", exc)
        try:
            audio.shutdown()
        except Exception:                                            # noqa: BLE001
            pass
    os._exit(0)                                                      # no interpreter finalisation in the worker either

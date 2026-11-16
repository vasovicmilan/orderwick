"""Tiny HTTP client for the Orderwick server (standard library only, so the build does not grow)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

TIMEOUT = 10


class OnlineError(Exception):
    """A failed call. `code` is the server's error code or "network"; `message` is safe to show to the player."""

    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class ApiClient:
    def __init__(self, base_url: str, key: Callable[[], str], version: str, platform: str):
        self.base = base_url.rstrip("/")
        self.key = key
        self.agent = f"Orderwick/{version} ({platform})"
        self.version, self.platform = version, platform
        self.on_auth_lost: Callable[[], bool] | None = None      # called once on 401; True = a new account was made, retry

    # ---- transport ---------------------------------------------------------------------------------
    def request(self, method: str, path: str, body: dict | None = None, auth: bool = True, _retry: bool = True) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"User-Agent": self.agent, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            key = self.key()
            if not key and auth != "optional":
                raise OnlineError("no_account", "Online features are not set up yet.")
            if key:
                headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read()).get("error", {})
            except (ValueError, AttributeError):
                err = {}
            if auth and e.code == 401 and _retry and self.on_auth_lost is not None and self.on_auth_lost():
                return self.request(method, path, body, auth, _retry=False)
            raise OnlineError(err.get("code", f"http_{e.code}"), err.get("message", f"Server error {e.code}."), e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise OnlineError("network", "Can't reach the server.") from None
        except ValueError:
            raise OnlineError("bad_response", "The server answered something unexpected.") from None

    # ---- API ------------------------------------------------------------------------------------------
    def register(self, nickname: str | None = None) -> dict:
        return self.request("POST", "/api/v1/players", {"nickname": nickname} if nickname else {}, auth=False)

    def activate(self, code: str, install_id: str) -> dict:
        """Checks the activation key from the website account. The player key (if any) is sent too, so the server links them."""
        return self.request("POST", "/api/v1/activation", {"code": code, "installId": install_id, "platform": self.platform}, auth="optional")

    def claim(self, code: str, install_id: str) -> dict | None:
        """Takes over the player of the account this key belongs to, with a key made for this install. None = the account has no player yet."""
        out = self.request("POST", "/api/v1/players/claim", {"code": code, "installId": install_id, "platform": self.platform}, auth=False)
        return (out or {}).get("player")

    def me(self) -> dict:
        return self.request("GET", "/api/v1/players/me")

    def progress(self) -> dict:
        """Achievements with progress, statistics and the coin balance, as the server counts them."""
        return self.request("GET", "/api/v1/players/me/progress")

    def content_manifest(self) -> dict:
        """The list of server content (cards, styles, themes): public, no player data."""
        return self.request("GET", "/api/v1/content/manifest", auth=False)

    def inventory(self) -> dict:
        """What this player owns (free items included) and the coin balance."""
        return self.request("GET", "/api/v1/players/me/inventory")

    def download(self, file_hash: str, limit: int = 600 * 1024) -> bytes:
        """One content file by its SHA-256. The caller verifies the hash; the size is capped here."""
        req = urllib.request.Request(f"{self.base}/api/v1/content/files/{file_hash}", headers={"User-Agent": self.agent})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read(limit + 1)
        except urllib.error.HTTPError as e:
            raise OnlineError(f"http_{e.code}", f"Server error {e.code}.", e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise OnlineError("network", "Can't reach the server.") from None
        if len(data) > limit:
            raise OnlineError("too_big", "A file was larger than allowed.")
        return data

    def public_png(self, path: str, limit: int = 64 * 1024) -> bytes | None:
        """A public picture (no sign-in): the bytes, or None when the server has none (404)."""
        req = urllib.request.Request(self.base + path, headers={"User-Agent": self.agent})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read(limit + 1)[:limit + 1]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise OnlineError(f"http_{e.code}", f"Server error {e.code}.", e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise OnlineError("network", "Can't reach the server.") from None

    def avatar_pictures(self, nickname: str, version: str = "") -> tuple[bytes | None, bytes | None]:
        """(talking strip, still picture) of the avatar this player wears; a missing strip is None.
        `version` (the avatar's code) is added to the address so a change made on the website is not hidden by a cached picture."""
        who = urllib.parse.quote(nickname, safe="")
        tag = f"?v={urllib.parse.quote(version, safe='')}" if version else ""
        return self.public_png(f"/avatar/{who}/talk.png{tag}"), self.public_png(f"/avatar/{who}.png{tag}")

    def rename(self, nickname: str) -> dict:
        return self.request("PATCH", "/api/v1/players/me", {"nickname": nickname})

    def export(self) -> dict:
        return self.request("GET", "/api/v1/players/me/export")

    def erase(self) -> dict:
        return self.request("DELETE", "/api/v1/players/me")

    def start_run(self, mode: str, start_level: int) -> dict:
        return self.request("POST", "/api/v1/runs", {"mode": mode, "startLevel": start_level})

    def round(self, run_id: str) -> dict:
        return self.request("GET", f"/api/v1/runs/{run_id}/round")

    def submit_round(self, run_id: str, events: list[str], elapsed: float) -> dict:
        return self.request("POST", f"/api/v1/runs/{run_id}/rounds", {"events": events, "elapsed": round(elapsed, 2)})

    def restart(self, run_id: str, events: list[str]) -> dict:
        return self.request("POST", f"/api/v1/runs/{run_id}/restart", {"events": events})

    def finish(self, run_id: str, events: list[str] | None = None, elapsed: float = 0.0) -> dict:
        """Closes the run. For a daily board ended before it was solved the moves go along: the server keeps the attempt with the
        points for the columns sorted so far."""
        body = {"events": events, "elapsed": round(elapsed, 2)} if events is not None else {}
        return self.request("POST", f"/api/v1/runs/{run_id}/finish", body)

    def leaderboard(self, mode: str, who: str = "all") -> dict:
        return self.request("GET", f"/api/v1/leaderboard/{mode}?who={who}&limit=20", auth=False)

    def daily(self) -> dict:
        return self.request("GET", "/api/v1/daily")

    def season(self) -> dict:
        return self.request("GET", "/api/v1/season")

    def season_seen(self) -> dict:
        return self.request("POST", "/api/v1/season/rewards/seen", {})

    def latest_version(self) -> dict:
        return self.request("GET", f"/api/v1/version/latest?platform={self.platform}&current={self.version}", auth=False)

"""Tiny HTTP client for the Orderwick server (standard library only, so the build does not grow)."""
from __future__ import annotations

import json
import urllib.error
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

    def finish(self, run_id: str) -> dict:
        return self.request("POST", f"/api/v1/runs/{run_id}/finish", {})

    def leaderboard(self, mode: str, who: str = "all") -> dict:
        return self.request("GET", f"/api/v1/leaderboard/{mode}?who={who}&limit=20", auth=False)

    def latest_version(self) -> dict:
        return self.request("GET", f"/api/v1/version/latest?platform={self.platform}&current={self.version}", auth=False)

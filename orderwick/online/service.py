"""OnlineService: the player's online identity and the switch for online features. One instance lives on the app."""
from __future__ import annotations

import json
import os
import secrets
import sys

from .. import config
from ..data.storage import JsonStore, default_data_dir
from .client import ApiClient, OnlineError
from .remote import RemoteRun

ONLINE_MODES = ("campaign", "hard", "daily")


def platform_name() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


class OnlineService:
    def __init__(self, store: JsonStore | None = None, url: str | None = None, client=None):
        self.url = (config.SERVER_URL if url is None else url).rstrip("/")
        self.store = store or JsonStore("online.json")
        self.state = self.store.load({"consent": 0, "player_id": "", "key": "", "nickname": "", "install_id": "", "activation": "", "account_name": "", "progress": {}})
        self.agent_key = os.environ.get("ORDERWICK_AGENT_KEY", "")          # an AI agent plays with an operator-issued key
        self.client = client or (ApiClient(self.url, self._key, config.VERSION, platform_name()) if self.url else None)
        self.last_error = ""
        self.events = None
        if isinstance(self.client, ApiClient):
            self.client.on_auth_lost = self._recover

    # ---- state -----------------------------------------------------------------------------------------
    def _key(self) -> str:
        return self.agent_key or self.state.get("key", "")

    @property
    def available(self) -> bool:
        """Is this build able to go online at all (a server address is configured; never in developer mode)?"""
        return bool(self.client) and not config.DEV

    @property
    def enabled(self) -> bool:
        """Online features are on: the player consented (or an operator-issued agent key is in use) and an account exists."""
        if not self.available:
            return False
        if self.agent_key:
            return True
        return self.state.get("consent", 0) >= config.ONLINE_CONSENT_VERSION and bool(self.state.get("key")) and self.activated

    @property
    def activated(self) -> bool:
        """The activation key from the website account was accepted on this computer (agents use an operator key instead)."""
        return bool(self.agent_key) or bool(self.state.get("activation"))

    @property
    def account_name(self) -> str:
        return self.state.get("account_name", "")

    @property
    def is_agent(self) -> bool:
        return bool(self.agent_key)

    @property
    def nickname(self) -> str:
        return self.state.get("nickname", "")

    def _save(self) -> None:
        self.store.save(self.state)

    # ---- account (blocking: run these from a BackgroundTask) -----------------------------------------------
    def _install_id(self) -> str:
        """A random id made once per installation. The server stores only a hash and counts how many installs use one key."""
        if not self.state.get("install_id"):
            self.state["install_id"] = secrets.token_urlsafe(18)
            self._save()
        return self.state["install_id"]

    def activate(self, code: str) -> str:
        """Checks the key from the website account. On success it is remembered here and the account name is returned."""
        if not self.available:
            raise OnlineError("unavailable", "Online features are not available in this build.")
        code = (code or "").strip()
        if not code:
            raise OnlineError("bad_key", "Enter the activation key from your account page.")
        out = self.client.activate(code, self._install_id())
        self.state.update(activation=code.upper(), account_name=out.get("name", ""))
        self._save()
        return self.account_name

    def deactivate(self) -> None:
        """Forgets the key on this computer (the server keeps counting this install until it is reset on the website)."""
        self.state.update(activation="", account_name="")
        self._save()

    def _send_activation(self, strict: bool) -> None:
        """Sends the saved key again. With `strict` a key the server no longer accepts is forgotten and the error is raised;
        a network problem never locks anybody out."""
        if self.agent_key or not self.state.get("activation"):
            return
        try:
            self.client.activate(self.state["activation"], self._install_id())
        except OnlineError as e:
            if strict and e.code in ("not_found", "forbidden", "bad_key", "activation_limit"):
                self.deactivate()
                raise

    def enable(self) -> str:
        """The player agreed. Creates the anonymous online account (a random id and key, an automatic nickname)."""
        if not self.available:
            raise OnlineError("unavailable", "Online features are not available in this build.")
        if not self.activated:
            raise OnlineError("not_activated", "Enter your activation key first (it is on your account page).")
        if not self.state.get("key"):
            reg = self.client.register()
            self.state.update(player_id=reg["playerId"], key=reg["key"], nickname=reg["nickname"])
        self.state["consent"] = config.ONLINE_CONSENT_VERSION
        self._save()
        self._send_activation(strict=False)          # now that a player key exists the server can link player and account
        return self.nickname

    def _recover(self) -> bool:
        """The server does not know our key (its database was reset, or the address now points to another server).
        Make a fresh anonymous account, keeping the nickname if it is free. Never for operator-issued agent keys."""
        if self.agent_key or not self.state.get("key"):
            return False
        old = self.state.get("nickname", "")
        try:
            try:
                reg = self.client.register(old or None)
            except OnlineError as e:
                if e.code not in ("nickname_taken", "conflict") and e.status != 409:
                    raise
                reg = self.client.register()
        except OnlineError:
            return False
        self.state.update(player_id=reg["playerId"], key=reg["key"], nickname=reg["nickname"])
        self._save()
        return True

    def disable(self) -> None:
        """Turns online features off. The account stays (switch back on any time); nothing more is sent."""
        self.state["consent"] = 0
        self._save()

    def refresh_me(self) -> dict:
        self._send_activation(strict=True)           # a revoked key is noticed here, when the Online screen opens
        me = self.client.me()
        if not self.agent_key and me.get("nickname") != self.state.get("nickname"):
            self.state["nickname"] = me["nickname"]
            self._save()
        return me

    def rename(self, nickname: str) -> str:
        out = self.client.rename(nickname)
        self.state["nickname"] = out["nickname"]
        self._save()
        return out["nickname"]

    def export_to_file(self) -> str:
        data = self.client.export()
        path = default_data_dir() / "my-online-data.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def erase(self) -> None:
        """Deletes the online account and all its data on the server, then forgets it here."""
        self.client.erase()
        self.state.update(consent=0, player_id="", key="", nickname="", progress={})      # the activation stays: it belongs to the website account
        self._save()

    # ---- achievements and coins: the server counts them, this is only a copy ---------------------------------------------
    @property
    def cached_progress(self) -> dict:
        """The last progress the server sent (empty until the first sync). Used to draw the list without waiting."""
        return self.state.get("progress") or {}

    def sync_progress(self) -> dict:
        """Blocking. Fetches the real state from the server, remembers it and tells the game so it can overwrite local trophies."""
        data = self.client.progress()
        self.state["progress"] = data
        self._save()
        if self.events is not None:
            self.events.emit("server_progress", progress=data)
        return data

    def note_progress(self, earned: dict | None) -> None:
        """A solved board came back with what it earned. Keeps the cached copy current without another request."""
        if not earned:
            return
        cache = self.state.get("progress") or {}
        if "balance" in earned and cache.get("currency"):
            cache["currency"]["balance"] = earned["balance"]
        unlocked = {a["code"] for a in earned.get("unlocked", [])}
        for item in cache.get("achievements", []):
            if item["code"] in unlocked:
                item["unlocked"] = True
                item["progress"] = item["threshold"]
        self.state["progress"] = cache
        self._save()
        if self.events is not None and unlocked:
            self.events.emit("server_progress", progress=cache)
        if self.events is not None and any(a.get("items") for a in earned.get("unlocked", [])):
            self.events.emit("server_items")             # an achievement came with an item: fetch it now

    # ---- runs ---------------------------------------------------------------------------------------------------
    def new_remote(self, mode) -> RemoteRun | None:
        if not self.enabled or mode.id not in ONLINE_MODES:
            return None
        start = 1 if mode.id == "daily" else mode.initial_level()
        remote = RemoteRun(self.client, mode.id, start)
        remote.on_progress = self.note_progress
        return remote

    def attach(self, events) -> None:
        """Hooks the run life cycle: a solved board is submitted, a finished run is closed."""
        self.events = events

        def on_won(session=None, **_):
            if session is not None and session.remote is not None:
                session.remote.submit_async(session, session.round)

        def on_finished(session=None, **_):
            if session is not None and session.remote is not None:
                session.remote.finish_async()
        events.subscribe("round_won", on_won)
        events.subscribe("run_finished", on_finished)

    # ---- misc -------------------------------------------------------------------------------------------------------
    def leaderboard(self, mode: str, who: str = "all") -> list[dict]:
        return self.client.leaderboard(mode, who)["entries"]

    def latest_version(self) -> dict:
        return self.client.latest_version()

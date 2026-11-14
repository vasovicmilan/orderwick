"""OrderwickGame: the App with game-specific data."""
from __future__ import annotations

from . import config
from .data.leaderboard import Leaderboard
from .data.progress import Progress
from .data.settings import Settings
from .engine.audio import audio
from .engine.app import App


class OrderwickGame(App):
    def __init__(self) -> None:
        super().__init__(
            title=config.APP_NAME + (" [DEV]" if config.DEV else ""),
            size=config.WINDOW_SIZE,
            sprites_dir=config.SPRITES_DIR,
            min_size=config.MIN_WINDOW_SIZE,
            fps=config.FPS,
            icon=config.ICON_PATH,
        )
        self.leaderboard = Leaderboard()
        from .online.content import ContentStore
        self.content = ContentStore()                         # registers cached server cards/looks BEFORE progress is loaded
        self.assets.extra_sprites_dir = self.content.sprites_dir
        self.progress = Progress(self.events)
        from .data.daily import DailyChallenges
        self.daily = DailyChallenges(self.events, self.progress)
        self.settings = Settings()
        from .online.service import OnlineService
        self.online = OnlineService()
        self.online.attach(self.events)
        self.content.client = self.online.client
        from .online.avatar import AvatarVoice
        self.avatar = AvatarVoice(self.content.dir)           # the speaker in the HUD: the avatar the player wears (a built-in one offline)
        self.events.subscribe("server_items", lambda **_: (self.content.sync_async(force=True),
                                                           self.avatar.refresh_async(self.online.client, self.online.nickname, force=True)))
        self.progress.grant_server_cards(self.content.owned_cards())
        self.apply_appearance()
        audio.init(config.AUDIO_DIR, self.settings.data)
        audio.set_extra_tracks(self.content.music_files())    # songs downloaded earlier
        from .audio_events import SfxDirector
        self.sfx_director = SfxDirector(self.events)
        from .view.toasts import ToastManager
        self.toasts = ToastManager(self)

    def apply_appearance(self) -> None:
        """Applies the chosen board theme and card style (falls back to the defaults if one is locked/unknown)."""
        from .core import cosmetics
        trophies = self.progress.tracker.unlocked
        data = self.settings.data
        theme = cosmetics.resolve(cosmetics.BOARD, data.get("board_theme", ""), trophies)
        style = cosmetics.resolve(cosmetics.CARDS, data.get("card_style", ""), trophies)
        data["board_theme"], data["card_style"] = theme, style                   # the player's own choice stays as it is
        if self.season_look and self.content.lent_theme():                       # in a Season run the season's board is always used
            theme = self.content.lent_theme()
        self.assets.set_theme(None if theme == cosmetics.default_id(cosmetics.BOARD) else self.content.theme_dir(theme))
        self.assets.set_card_style(None if style == cosmetics.default_id(cosmetics.CARDS)
                                   else self.content.card_style_dir(style))
        from .view import colors
        colors.apply(self.assets.theme_palette)                  # text / UI colours follow the theme
        from .view.board_view import BoardView
        BoardView.fit_margin = BoardView.FRAME_FIT_MARGIN if self.assets.theme_frame else 0
        self._wood_kit = None                                    # menus/dialogs are rebuilt in the new style

    season_look = False
    _season_sent = None

    def _season_run_open(self) -> bool:
        return any(getattr(getattr(getattr(s, "session", None), "mode", None), "id", "") == "season" for s in self.scenes._stack)

    def sync_season_look(self) -> None:
        """A Season run always uses the season's board and only the season's songs, whatever the player chose; afterwards everything goes back."""
        want = self._season_run_open() and bool(self.content.lent_theme())
        tracks = self.content.season_music_files() if want else []
        if want != self.season_look:
            self.season_look = want
            self.apply_appearance()
        sent = tuple(str(t) for t in tracks) if want and tracks else None
        if sent != self._season_sent:                                            # only when it changes (every call is a message to the audio process)
            self._season_sent = sent
            audio.set_season_tracks(list(sent) if sent else None)

    def new_session(self, mode):
        """A new run: only unlocked cards appear."""
        from .core.session import GameSession
        session = GameSession(mode, events=self.events, unlocked=self.progress.collection.unlocked)
        session.remote = self.online.new_remote(mode)          # None unless the player turned online features on
        return session

    def on_shutdown(self) -> None:
        audio.shutdown()

    def update_overlay(self, dt: float) -> None:
        if self.content.poll():                                  # a sync finished: new cards and looks may have arrived
            self.progress.grant_server_cards(self.content.owned_cards())
            self.apply_appearance()
            audio.set_extra_tracks(self.content.music_files())    # new songs join the playlist
        elif self.online.enabled and not self.online.is_agent:
            self.content.sync_async()                            # at start and every 15 minutes
            self.avatar.refresh_async(self.online.client, self.online.nickname)
        self.avatar.poll()
        self.sync_season_look()
        self.toasts.update(dt)
        audio.update(dt)

    def draw_overlay(self, surface) -> None:
        self.toasts.draw(surface)

    def start(self) -> None:
        from .scenes.menu import MenuScene
        self.run(MenuScene(self))

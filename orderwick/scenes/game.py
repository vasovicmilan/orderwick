"""Main game screen: board, info panel, moves, rescue, win."""
from __future__ import annotations

import pygame

from .. import config
from ..core.levels import LevelCatalog
from ..core.models import Loc, col, slot
from ..core.scoring import Scoring, format_time
from ..core.session import GameSession
from ..engine.audio import audio
from ..engine.scene import Scene
from ..engine.tasks import BackgroundTask
from ..engine.ui import dim_background, draw_text
from ..view.board_view import BoardView
from ..view.hud_view import BAD, CREAM, GOLD, TAN, MIN_HUD_HEIGHT, HudButton, HudData, HudView, WinData
from .common import clear

PREFETCH_BUDGET = 6.0      # seconds of deeper shuffling for a board built while you play
PREFETCH_PAUSE = 0.04


class GameScene(Scene):
    def __init__(self, app, session: GameSession):
        super().__init__(app)
        self.session = session
        self.view = BoardView(app.assets)
        self.selected: Loc | None = None
        self.cursor_index = 0
        self.use_cursor = False
        self.hover: Loc | None = None
        self.msg = ""
        self.msg_ttl = 0.0
        self.restart_confirm = 0.0
        self.load_task: BackgroundTask | None = None
        self.rescue_task: BackgroundTask | None = None
        self.prefetch: tuple[int, BackgroundTask] | None = None   # (level, task) of the next board
        self.anim = 0.0
        self._closed = False        # the run is already finished/saved

        self.hud = HudView(app.assets)
        self.scale = 1
        self.hud_hover: int | None = None
        self.hud_pressed: int | None = None
        self.win_hover: int | None = None
        self.win_pressed: int | None = None
        self._hud_x = 0                    # left edge of the HUD on screen
        self._hud_h = 0                    # HUD height in asset pixels
        self._win_origin = (0, 0)
        self._win_rects: list[pygame.Rect] = []

    # ---- zivotni ciklus --------------------------------------------------------
    def on_enter(self) -> None:
        self._begin_load()

    def _begin_load(self) -> None:
        self.selected = None
        self.rescue_task = None
        pre, self.prefetch = self.prefetch, None
        if pre is not None and pre[0] == self.session.level:
            self.load_task = pre[1]                     # already being built (or finished) - just wait
        else:
            self.load_task = BackgroundTask(self.session.create_round)

    def _start_prefetch(self) -> None:
        """While you play the current board, the next one is built in the background (with deeper shuffling)."""
        if self.session.mode.id == "daily":                 # one board a day: there is no next one
            return
        if self.session.remote is not None:                 # ranked online: the server gives the next board once this one is solved
            return
        level = self.session.mode.next_level(self.session.level)
        self.prefetch = (level, BackgroundTask(
            self.session.create_round, level, PREFETCH_BUDGET, PREFETCH_PAUSE))

    @property
    def loading(self) -> bool:
        return self.load_task is not None

    # ---- helpers ------------------------------------------------------------------
    def _say(self, text: str, ttl: float = 4.5) -> None:
        self.msg, self.msg_ttl = text, ttl

    @property
    def rnd(self):
        return self.session.round

    def _targets(self) -> list[Loc]:
        board = self.rnd.board
        return [slot(i) for i in range(board.n_free)] + [col(i) for i in range(board.n_cols)]

    # ---- akcije ---------------------------------------------------------------------
    def _activate(self, loc: Loc) -> None:
        if self.loading or self.rescue_task or self.rnd.won:
            return
        board = self.rnd.board
        if self.selected is None:
            if board.is_empty_at(loc):
                self._say("There is no card there.")
                audio.play("invalid", 0.7)
                return
            self.selected = loc
            audio.play("pick")
            self.msg = ""
            return
        src, self.selected = self.selected, None
        if src == loc:
            return
        result = self.session.move(src, loc)
        self.msg = result.message
        self.msg_ttl = 4.5
        if not result.ok:
            audio.play("invalid")

    def _undo(self) -> None:
        if self.loading or self.rescue_task or self.rnd.won:
            return
        result = self.session.undo()
        self.selected = None
        self._say(result.message)

    def _rescue(self) -> None:
        if self.loading or self.rescue_task or self.rnd.won:
            return
        blocker = self.session.rescue_blocker()
        if blocker is not None:
            if blocker:
                self._say(blocker)
            return
        if self.session.rescue_needs_check():
            self._say("Checking whether a solution still exists...", 60)
            self.rescue_task = BackgroundTask(self.session.solution_exists,
                                              self.session.rescue_check_args())
        else:
            self._do_rescue()

    def _do_rescue(self) -> None:
        self.session.apply_rescue()
        self.selected = None
        if self.session.mode.ranked:
            self._say(f"RESCUE: level {self.session.level}, one free slot added. "
                      f"Solve this board to get back to level {self.session.level + 1}.", 8)
        else:
            self._say("RESCUE: one free slot added.", 6)

    def _restart(self) -> None:
        if self.loading or self.rescue_task:
            return
        if self.session.mode.id == "daily":                 # the same board again, from the start (no penalty)
            if not self.rnd.won:
                self._begin_load()
                self._say("Daily board restarted.")
            return
        if self.restart_confirm > 0:
            self.restart_confirm = 0
            self.session.penalize_restart()
            self._begin_load()
            self._say(f"New board (-{config.RESTART_PENALTY} points).")
        else:
            self.restart_confirm = 4.0
            self._say(f"Press R again for a new board (-{config.RESTART_PENALTY} points).", 4.0)

    def _pause(self) -> None:
        from .pause import PauseScene
        self.app.scenes.push(PauseScene(self.app, self))

    def _next_level(self) -> None:
        if self.rnd and self.rnd.won:
            self.session.advance()
            self._begin_load()

    def _finish(self) -> None:
        """End of the run: statistics, then the leaderboard if the score is good enough."""
        s = self.session
        board = self.app.leaderboard
        self._closed = True
        if s.mode.id != "daily":
            board.record_game(s.peak)
        self.app.events.emit("run_finished", session=s)
        if s.mode.ranked and board.qualifies(s.mode.id, s.score):
            from .name_entry import NameEntryScene
            self.app.scenes.replace(NameEntryScene(self.app, s))
        else:
            self.app.scenes.pop()

    def _ask_finish(self) -> None:
        from .confirm import ConfirmScene
        s = self.session
        self.app.scenes.push(ConfirmScene(
            self.app, "End the run?", f"Score {s.score}   Level {s.peak}",
            "Yes, end it", self._finish))

    def on_quit(self) -> None:
        """Closing the window mid-run: the score is not lost (name = PLAYER if it makes the list)."""
        if self._closed:
            return
        self._closed = True
        s = self.session
        board = self.app.leaderboard
        if s.mode.id != "daily":
            board.record_game(s.peak)
        self.app.events.emit("run_finished", session=s)
        if s.mode.ranked and board.qualifies(s.mode.id, s.score):
            board.add(s.mode.id, "PLAYER", s.result())

    # ---- raspored ----------------------------------------------------------------------
    def _layout(self) -> pygame.Rect:
        """Computes the shared scale factor (board + HUD + cards) and returns the space for the board."""
        w, h = self.app.screen.get_size()
        if self.rnd is not None:
            cols, cap = self.rnd.board.n_cols, self.rnd.board.capacity
        else:
            spec = self.session.mode.spec_for(self.session.level)
            cols, cap = spec.cols, spec.k
        self.scale = BoardView.fit_scale(cols, cap, w, h, extra_native_w=config.HUD_WIDTH,
                                         min_native_h=MIN_HUD_HEIGHT)
        hud_w = config.HUD_WIDTH * self.scale
        self._hud_x = w - hud_w
        self._hud_h = -(-h // self.scale)
        area = pygame.Rect(0, 0, self._hud_x, h)
        if self.rnd is not None:
            self.view.layout(self.rnd.board, area, self.scale)
        return area

    def _hud_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """Mouse position in asset pixels inside the HUD (or None if outside)."""
        if pos[0] < self._hud_x:
            return None
        return (pos[0] - self._hud_x) // self.scale, pos[1] // self.scale

    def _hud_actions(self):
        return [self._undo, self._rescue, self._restart, self._pause]

    # ---- ulaz -------------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.loading:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                self._finish()
            return
        board_area = self._layout()
        rnd = self.rnd

        if rnd.won:
            self._handle_win_event(event)
            return

        if event.type == pygame.MOUSEMOTION:
            self.use_cursor = False
            hp = self._hud_pos(event.pos)
            self.hud_hover = self.hud.hit_test(hp, self._hud_h, 4) if hp else None
            self.hover = self.view.hit_test(event.pos) if board_area.collidepoint(event.pos) else None
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.selected = None
            elif event.button == 1:
                hp = self._hud_pos(event.pos)
                if hp is not None:
                    idx = self.hud.hit_test(hp, self._hud_h, 4)
                    if idx is not None and self._hud_enabled()[idx]:
                        self.hud_pressed = idx
                    return
                loc = self.view.hit_test(event.pos)
                if loc is not None:
                    self.use_cursor = False
                    self._activate(loc)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pressed, self.hud_pressed = self.hud_pressed, None
            hp = self._hud_pos(event.pos)
            if pressed is not None and hp is not None and self.hud.hit_test(hp, self._hud_h, 4) == pressed:
                self._hud_actions()[pressed]()
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event)

    def _handle_win_event(self, event: pygame.event.Event) -> None:
        daily = self.session.mode.id == "daily"
        actions = [self._finish] if daily else [self._next_level, self._finish]

        def local(pos):
            return pos[0] // self.scale - self._win_origin[0], pos[1] // self.scale - self._win_origin[1]

        def which(pos):
            lp = local(pos)
            return next((i for i, r in enumerate(self._win_rects) if r.collidepoint(lp)), None)

        if event.type == pygame.MOUSEMOTION:
            self.win_hover = which(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.win_pressed = which(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pressed, self.win_pressed = self.win_pressed, None
            if pressed is not None and which(event.pos) == pressed:
                actions[pressed]()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._finish() if daily else self._next_level()
            elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                self._finish()

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        board = self.rnd.board
        ch = event.unicode.lower() if event.unicode else ""
        if key == pygame.K_ESCAPE:
            if self.selected is not None:
                self.selected = None
            else:
                self._pause()
        elif key == pygame.K_p:
            self._pause()
        elif ch == "q":
            self._ask_finish()
        elif ch == "u":
            self._undo()
        elif ch == "x":
            self._rescue()
        elif ch == "r":
            self._restart()
        elif ch == "?" or key == pygame.K_F1:
            from .help import HelpScene
            self.app.scenes.push(HelpScene(self.app))
        elif ch and ch in config.COL_KEYS and config.COL_KEYS.index(ch) < board.n_cols:
            idx = config.COL_KEYS.index(ch)
            self.cursor_index = board.n_free + idx
            self.use_cursor = False
            self._activate(col(idx))
        elif ch and ch in config.FREE_KEYS and config.FREE_KEYS.index(ch) < board.n_free:
            idx = config.FREE_KEYS.index(ch)
            self.cursor_index = idx
            self.use_cursor = False
            self._activate(slot(idx))
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            targets = self._targets()
            step = 1 if key == pygame.K_RIGHT else -1
            self.cursor_index = (self.cursor_index + step) % len(targets)
            self.use_cursor = True
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            targets = self._targets()
            self.use_cursor = True
            self._activate(targets[self.cursor_index % len(targets)])

    # ---- update --------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.anim += dt
        if self.msg_ttl > 0:
            self.msg_ttl -= dt
            if self.msg_ttl <= 0:
                self.msg = ""
        if self.restart_confirm > 0:
            self.restart_confirm = max(0.0, self.restart_confirm - dt)

        if self.load_task is not None:
            if not self.load_task.done:
                return
            task, self.load_task = self.load_task, None
            if task.error is not None:
                raise task.error
            self.session.start_round(task.result)
            self.cursor_index = 0
            self._start_prefetch()
            if self.session.remote is not None:               # first board: "ranked online" or why this run is offline
                note = self.session.remote.poll(self.session)
                if note:
                    self._say(note, 8)
            return

        if self.rescue_task is not None and self.rescue_task.done:
            task, self.rescue_task = self.rescue_task, None
            if task.result is True:
                self._say("A solution still exists! Keep going, or undo a move.")
            else:
                self._do_rescue()
            return

        self.session.tick(dt)
        if self.session.remote is not None:                  # the server's verdict on a solved board, or a note that the run went offline
            note = self.session.remote.poll(self.session)
            if note:
                self._say(note, 8)

    # ---- drawing -------------------------------------------------------------------------
    def _hud_enabled(self) -> list[bool]:
        rnd = self.rnd
        if self.loading or rnd is None or rnd.won:
            return [False] * 4
        return [rnd.undo is not None, True, True, True]

    def _hud_data(self) -> HudData:
        s = self.session
        rnd = self.rnd
        spec = rnd.spec if rnd is not None else s.mode.spec_for(s.level)
        n_free = rnd.board.n_free if rnd is not None else spec.free
        label = s.mode.level_label(s.level)
        enabled = self._hud_enabled()
        messages: list[tuple[str, tuple]] = []
        if rnd is not None and not self.loading and not rnd.won and not rnd.board.has_moves():
            messages.append(("NO MOVES LEFT! U = undo, R = restart the board." if s.mode.id == "daily"
                             else "NO MOVES LEFT! X = rescue, U = undo, R = new board.", BAD))
        if self.msg:
            messages.append((self.msg, GOLD))
        if not messages and rnd is not None and not self.loading and not rnd.won:
            messages.append(("Pick a card, then a target.", TAN))
        return HudData(
            mode_title=s.mode.short_title,
            heading=f"LEVEL {label}" if s.mode.ranked or s.mode.id == "daily" else "BOARD",
            info=[f"{spec.cols}×{spec.rows} TYPES {spec.types}", f"FREE SLOTS {n_free}"],
            moves=str(rnd.moves) if rnd is not None and not self.loading else "0",
            time=format_time(rnd.elapsed) if rnd is not None and not self.loading else "00:00",
            score=str(s.score),
            messages=messages,
            buttons=[HudButton("UNDO MOVE", "undo", enabled[0]), HudButton("RESCUE", "rescue", enabled[1]),
                     HudButton("RESTART" if s.mode.id == "daily" else "NEW BOARD", "restart", enabled[2]), HudButton("PAUSE", "pause", enabled[3])],
        )

    def draw(self, surface: pygame.Surface) -> None:
        clear(surface)
        board_area = self._layout()
        S = self.scale
        hud = self.hud.render(self._hud_data(), self._hud_h, self.hud_hover, self.hud_pressed)
        hud_screen = pygame.transform.scale(hud, (hud.get_width() * S, hud.get_height() * S))
        surface.blit(hud_screen, (self._hud_x, 0))

        if self.loading or self.rnd is None:
            dots = "." * (1 + int(self.anim * 3) % 3)
            draw_text(surface, f"BUILDING BOARD{dots}", self.app.assets.pixel_font(max(2, S - 1)),
                      CREAM, board_area.center, "center", shadow=True)
            return

        rnd = self.rnd
        cursor = None
        if self.use_cursor:
            targets = self._targets()
            cursor = targets[self.cursor_index % len(targets)]
        self.view.draw(surface, rnd.board, rnd.palette, self.selected, cursor, self.hover)
        if rnd.won:
            self._draw_win(surface, board_area)

    # ---- pobeda ---------------------------------------------------------------------------
    def _win_data(self) -> WinData:
        rnd, s = self.rnd, self.session
        rows = []
        if s.mode.ranked:
            rows.append(("LEVEL", str(rnd.level), f"+{Scoring.LEVEL_POINTS * rnd.level}"))
        rows.append(("MOVES", str(rnd.moves), f"+{Scoring.move_bonus(rnd.spec, rnd.moves)}"))
        rows.append(("TIME", format_time(rnd.elapsed), f"+{Scoring.time_bonus(rnd.spec, rnd.elapsed)}"))
        final = s.mode.ranked and s.level >= LevelCatalog.final_level()
        return WinData(
            title=("DAILY BOARD SOLVED!" if s.mode.id == "daily" else
                   f"LEVEL {s.mode.level_label(rnd.level)} SOLVED!" if s.mode.ranked else "BOARD SOLVED!"),
            rows=rows,
            total=f"TOTAL {s.score}",
            note="FINALE! NEW BOARDS KEEP COMING." if final else "",
            buttons=([HudButton("BACK TO MENU", "")] if s.mode.id == "daily" else
                     [HudButton("NEXT LEVEL" if s.mode.ranked else "NEXT BOARD", ""), HudButton("END RUN", "")]),
        )

    def _draw_win(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        S = self.scale
        dim_background(surface, 150)
        box, rects = self.hud.render_win(self._win_data(), self.win_hover, self.win_pressed)
        self._win_rects = rects
        w, h = surface.get_size()
        ox = (w // S - box.get_width()) // 2
        oy = (h // S - box.get_height()) // 2
        self._win_origin = (ox, oy)
        surface.blit(pygame.transform.scale(box, (box.get_width() * S, box.get_height() * S)), (ox * S, oy * S))

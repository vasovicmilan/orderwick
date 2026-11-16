"""The part of the Claude player that needs the game (window, scenes). Started by `Orderwick --agent`: see agent_player.py."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pygame  # noqa: E402

from orderwick import agent_player, config  # noqa: E402
from orderwick.core.autoplayer import VisiblePlayer, observe  # noqa: E402
from orderwick.game import OrderwickGame  # noqa: E402
from orderwick.scenes.game import GameScene  # noqa: E402
from orderwick.scenes.menu import MenuScene  # noqa: E402


class Driver:
    """Runs a script written as a generator: `yield seconds` waits, `yield callable` waits until it returns True."""

    def __init__(self, app, script):
        self.app, self.gen, self.wait, self.cond = app, script, 0.0, None

    def key(self, key: int, char: str = "") -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=char, mod=0, scancode=0))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0, scancode=0))

    def type_char(self, ch: str) -> None:
        self.key(ord(ch.lower()) if ch.isalnum() else {"-": pygame.K_MINUS}.get(ch, ord(ch)), ch)

    def tick(self, dt: float) -> bool:
        if self.cond is not None:
            if not self.cond():
                return True
            self.cond = None
        if self.wait > 0:
            self.wait -= dt
            return True
        try:
            step = next(self.gen)
        except StopIteration:
            return False
        if callable(step):
            self.cond = step
        else:
            self.wait = float(step or 0)
        return True


def run(args) -> int:
    from orderwick.agent_player import say
    agent_player.open_log(Path(os.environ["ORDERWICK_HOME"]) / "agent.log")
    app = OrderwickGame()
    try:
        width, height = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        width, height = 1280, 800
    app.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    if args.brain == "sampling":
        from orderwick.core.sampling_player import SamplingPlayer
        player = SamplingPlayer(seed=args.seed, samples=8, candidates=2)
    else:
        player = VisiblePlayer(seed=args.seed)
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    stats = {"boards": 0, "moves": 0, "undo": 0, "rescue": 0, "restart": 0}
    d = Driver(app, None)

    def shot(name: str) -> None:
        if shots:
            pygame.image.save(app.screen, str(shots / f"{name}.png"))

    def scene():
        return app.scenes.current

    def press(k, ch=""):
        d.key(k, ch)

    def menu_to(index: int):
        """Moves the menu focus to an item the way a player would: key presses, the shortest way round."""
        grp = scene().group
        n = len(grp.widgets)
        down = (index - grp.focus) % n
        step, count = (pygame.K_DOWN, down) if down <= n - down else (pygame.K_UP, n - down)
        for _ in range(count):
            press(step); yield 0.3

    def visit(index: int, dwell: float, name: str, extra=None):
        """Opens a menu screen, shows it for a moment, goes back."""
        yield from menu_to(index)
        press(pygame.K_RETURN); yield 1.2
        shot(name); yield dwell
        if extra:
            yield from extra()
        press(pygame.K_ESCAPE); yield 1.0

    def tour_all():
        say("tour: the other screens")
        yield from visit(2, 3.0, "tour_daily")               # Daily: the board is marked as solved
        yield from visit(4, 3.0, "tour_trophies")
        yield from visit(5, 3.0, "tour_leaderboard", lambda: _tab())
        yield from visit(6, 2.0, "tour_online", lambda: _online_board())
        yield from visit(7, 2.5, "tour_settings")
        yield from visit(8, 2.5, "tour_help")
        yield from visit(9, 2.5, "tour_about")
        yield from to_menu()

    def to_menu():
        for _ in range(6):
            if isinstance(scene(), MenuScene):
                return
            press(pygame.K_ESCAPE); yield 1.2

    def script():
        yield 2.5
        shot("menu")
        if args.key:
            say("opening the Online screen and typing the activation key")
            for _ in range(14):                                  # down the menu to the Online button (found by its text: the menu has grown before)
                grp = getattr(scene(), "group", None)
                if grp is not None and "online" in str(getattr(grp.widgets[grp.focus], "text", "")).lower():
                    break
                press(pygame.K_DOWN); yield 0.35
            press(pygame.K_RETURN); yield 1.0                    # open the Online screen
            if not app.online.activated:
                press(pygame.K_RETURN); yield 1.0                # "Enter activation key"
                for ch in args.key:
                    d.type_char(ch); yield 0.12
                shot("key")
                yield 0.6
                press(pygame.K_RETURN)
                yield lambda: app.online.activated
                say("activated for", app.online.account_name)
                yield 1.5
            if not app.online.enabled:
                press(pygame.K_RETURN)                           # "Turn on online"
                yield lambda: app.online.enabled
            say("online is on as", app.online.nickname or "?")
            yield 1.5
            if args.nick:
                for _ in range(8):                                    # walk down to the "Change nickname" button
                    grp = getattr(scene(), "group", None)
                    if grp is not None and grp.widgets[grp.focus].text == "Change nickname":
                        break
                    press(pygame.K_DOWN); yield 0.4
                press(pygame.K_RETURN); yield 0.8                 # "Change nickname"
                for _ in range(16):
                    press(pygame.K_BACKSPACE); yield 0.04
                for ch in args.nick:
                    d.type_char(ch); yield 0.1
                shot("nick")
                press(pygame.K_RETURN)
                t_end = time.time() + 8
                yield lambda: app.online.nickname == args.nick or time.time() > t_end
                shot("nick_done")
                say("nickname is now", app.online.nickname, "|", getattr(scene(), "status", ""))
                yield 1.2
                for _ in range(8):
                    grp = getattr(scene(), "group", None)
                    if grp is None or grp.focus == 0:
                        break
                    press(pygame.K_UP); yield 0.4
            shot("online")
            yield from to_menu()                                 # Escape until the main menu is there again
            for _ in range(14):                                  # back to the top of the menu
                grp = getattr(scene(), "group", None)
                if grp is None or grp.focus == 0:
                    break
                press(pygame.K_UP); yield 0.25
        else:
            yield 0.5
        if args.mode == "tour":
            yield from tour_all()
            yield 2.0
            app.quit()
            return
        if args.mode == "daily":
            yield from menu_to(2)
            press(pygame.K_RETURN); yield 1.5                    # the Daily screen: today's three tasks
            shot("daily"); yield 3.0
            press(pygame.K_RETURN)                                # "Play today's board"
        elif args.mode == "season":
            yield from menu_to(3)
            press(pygame.K_RETURN); yield 1.5                    # the Season screen
            shot("season"); yield 3.0
            press(pygame.K_RETURN)                                # "Play the Season"
        elif args.mode == "hard":
            press(pygame.K_DOWN); yield 0.4 if not args.key else 0.01
            press(pygame.K_RETURN)
        else:
            press(pygame.K_RETURN); yield 1.0
            press(pygame.K_RETURN)
        from orderwick.scenes.confirm import ConfirmScene
        yield lambda: isinstance(scene(), ConfirmScene) or (isinstance(scene(), GameScene) and not scene().loading)
        if isinstance(scene(), ConfirmScene):                        # the server refused the board (daily: one attempt a day)
            say("the server did not give a board:", scene().detail)
            shot("refused")
            stats["refused"] = True
            return 2
        say("board is ready, level", scene().rnd.level)
        shot("start")

        t_board = time.time()
        tried = {}                                                   # (board, move) -> how many times the same move was played from the same position
        while stats["boards"] < args.boards:
            gs = scene()
            if args.give_up_after and time.time() - t_board > args.give_up_after and not gs.rnd.won:
                say("giving up: no solution found in", int(args.give_up_after), "seconds"); break
            if not isinstance(gs, GameScene):
                say("left the game scene:", type(gs).__name__); return
            if gs.loading or gs.rescue_task is not None:
                yield 0.1; continue
            rnd = gs.rnd
            if rnd.won:
                stats["boards"] += 1
                say(f"board {stats['boards']} solved: level {rnd.level}, {rnd.moves} moves, {rnd.elapsed:.0f}s, score {gs.session.score}")
                shot(f"won_{stats['boards']}")
                yield 5.0
                if args.mode == "daily" or stats["boards"] >= args.boards:
                    break
                press(pygame.K_RETURN)
                yield 0.5
                yield lambda: not scene().loading
                player.new_board()
                continue
            board = rnd.board
            can_rescue = board.n_free < board.max_free and args.mode not in ("daily", "season")      # the daily board has no rescue
            act = player.decide(observe(board), rnd.undo is not None, can_rescue)
            if args.debug and stats["moves"] < 14:
                say("DEBUG", act, "sel", gs.selected, "free", board.free, "n", [len(c) for c in board.columns], gs.msg)
            if act.kind == "move":
                key = (repr([list(map(str, c)) for c in board.columns]), repr(board.free), str(act.src), str(act.dst))
                tried[key] = tried.get(key, 0) + 1
                if args.repeat_limit and tried[key] > args.repeat_limit:
                    say(f"giving up: the same move from the same position for the {tried[key]}th time"); break
                pk = lambda loc: (config.COL_KEYS if loc.kind == "col" else config.FREE_KEYS)[loc.index]  # noqa: E731
                press(ord(pk(act.src)), pk(act.src)); yield args.pace
                press(ord(pk(act.dst)), pk(act.dst)); yield args.pace
                stats["moves"] += 1
                if stats["moves"] % 100 == 0:
                    say(f"{stats['moves']} moves, level {rnd.level}, score {gs.session.score}")
            elif act.kind == "undo":
                say("stuck:", act.why); press(ord("u"), "u"); stats["undo"] += 1; yield 0.8
            elif act.kind == "rescue":
                say("stuck:", act.why); before = board.n_free
                if args.debug:
                    o = observe(board); say("DEBUG obs", o.hidden, o.up, o.free, "moves", stats["moves"])
                press(ord("x"), "x"); yield 0.3
                yield lambda: scene().rescue_task is None
                yield 0.5
                if board.n_free > before:
                    stats["rescue"] += 1; shot("rescue")
                else:
                    say("rescue refused (a solution still exists): keep searching")
                yield 1.0
            elif act.kind == "restart":
                say("stuck:", act.why)
                press(ord("r"), "r"); yield 0.5; press(ord("r"), "r"); stats["restart"] += 1
                yield 1.0
                yield lambda: not scene().loading
                player.new_board()
            else:
                say("giving up:", act.why); break
        shot("end")
        say("finishing the run")
        if args.mode == "daily":
            gs_now = scene()
            if getattr(getattr(gs_now, "rnd", None), "won", False):
                press(pygame.K_RETURN); yield 2.0                    # "Back to menu" on the result screen
            else:                                                    # not solved: end the run so the attempt is sent to the server
                press(ord("q"), "q"); yield 1.5                      # "End the run?"
                shot("end_confirm")
                press(pygame.K_DOWN); yield 1.0                      # focus is on "No, go back": move to "Yes, end it"
                press(pygame.K_RETURN); yield 3.0
            yield from to_menu()
            if args.tour:
                yield from tour_all()
            yield 3.0
            app.quit()
            return
        press(pygame.K_ESCAPE); yield 1.5
        if not isinstance(scene(), (MenuScene, GameScene)):          # leaderboard name entry
            press(pygame.K_RETURN); yield 1.5
        yield 3.0
        app.quit()

    def _tab():
        press(pygame.K_RIGHT); yield 2.0

    def _online_board():
        press(pygame.K_RETURN); yield 2.0                            # "Online leaderboard"
        for _ in range(2):                                           # Hard mode -> Campaign -> Daily: today's result
            press(pygame.K_RIGHT); yield 0.8
        yield 2.5
        shot("tour_online_board"); yield 5.0
        press(pygame.K_ESCAPE); yield 1.0

    d.gen = script()
    app.running = True
    app.scenes.reset(MenuScene(app))
    while app.running:
        dt = min(app.clock.tick(app.fps) / 1000.0, 0.1)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.quit()
            else:
                app.scenes.handle_event(event)
        app.scenes.update(dt)
        app.update_overlay(dt)
        if not d.tick(dt):
            app.quit()
        app.scenes.draw(app.screen)
        app.draw_overlay(app.screen)
        pygame.display.flip()
    app.scenes.notify_quit()
    app.on_shutdown()
    say("done:", stats)
    pygame.quit()
    return 0 if (stats["boards"] >= args.boards or args.mode == "tour") else 1


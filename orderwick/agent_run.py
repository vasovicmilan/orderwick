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
    app.screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
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

    def script():
        yield 2.5
        shot("menu")
        if args.key:
            say("opening the Online screen and typing the activation key")
            for _ in range(6):                                   # Campaign, Hard, Daily, Custom, Trophies, Leaderboard -> Online
                press(pygame.K_DOWN); yield 0.35
            press(pygame.K_RETURN); yield 1.0
            press(pygame.K_RETURN); yield 1.0                    # "Enter activation key"
            for ch in args.key:
                d.type_char(ch); yield 0.12
            shot("key")
            yield 0.6
            press(pygame.K_RETURN)
            yield lambda: app.online.activated
            say("activated for", app.online.account_name)
            yield 1.5
            press(pygame.K_RETURN)                               # "Turn on online"
            yield lambda: app.online.enabled
            say("online is on as", app.online.nickname or "?")
            yield 1.5
            if args.nick:
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
                press(pygame.K_UP); yield 0.4
            shot("online")
            press(pygame.K_ESCAPE); yield 1.2
            for _ in range(6):
                press(pygame.K_UP); yield 0.25
        else:
            yield 0.5
        if args.mode == "hard":
            press(pygame.K_DOWN); yield 0.4 if not args.key else 0.01
            press(pygame.K_RETURN)
        else:
            press(pygame.K_RETURN); yield 1.0
            press(pygame.K_RETURN)
        yield lambda: isinstance(scene(), GameScene)
        yield lambda: not scene().loading
        say("board is ready, level", scene().rnd.level)
        shot("start")

        while stats["boards"] < args.boards:
            gs = scene()
            if not isinstance(gs, GameScene):
                say("left the game scene:", type(gs).__name__); return
            if gs.loading or gs.rescue_task is not None:
                yield 0.1; continue
            rnd = gs.rnd
            if rnd.won:
                stats["boards"] += 1
                say(f"board {stats['boards']} solved: level {rnd.level}, {rnd.moves} moves, {rnd.elapsed:.0f}s, score {gs.session.score}")
                shot(f"won_{stats['boards']}")
                yield 4.0
                if stats["boards"] >= args.boards:
                    break
                press(pygame.K_RETURN)
                yield 0.5
                yield lambda: not scene().loading
                player.new_board()
                continue
            board = rnd.board
            act = player.decide(observe(board), rnd.undo is not None, board.n_free < board.max_free)
            if args.debug and stats["moves"] < 14:
                say("DEBUG", act, "sel", gs.selected, "free", board.free, "n", [len(c) for c in board.columns], gs.msg)
            if act.kind == "move":
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
        press(pygame.K_ESCAPE); yield 1.5
        if not isinstance(scene(), (MenuScene, GameScene)):          # leaderboard name entry
            press(pygame.K_RETURN); yield 1.5
        yield 3.0
        app.quit()

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
    return 0 if stats["boards"] >= args.boards else 1


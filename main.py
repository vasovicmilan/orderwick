"""Launch the game:  python main.py   (--no-audio = no sound, --dev = developer mode with everything unlocked)"""
import faulthandler
import os
import sys


def selftest() -> int:
    """Runs the game without a window or sound: loads everything, draws every screen, checks the cards. 0 = OK."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("ORDERWICK_AUDIO", "off")
    # A hang must never block a build for hours: after 90 s print where every thread is stuck and stop with an error.
    try:
        faulthandler.dump_traceback_later(90, exit=True, file=sys.__stderr__ or sys.stderr)
    except Exception:                                      # a windowed Windows exe may have no stderr at all
        pass
    import tempfile
    os.environ.setdefault("ORDERWICK_HOME", tempfile.mkdtemp())
    import pygame
    from orderwick import config
    from orderwick.game import OrderwickGame
    from orderwick.scenes import (about, achievements, custom, daily, help as help_, leaderboard,
                                 level_select, menu, online, online_leaderboard, settings)
    print("selftest: starting", flush=True)
    app = OrderwickGame()
    print("selftest: game created", flush=True)
    app.screen = pygame.display.set_mode((960, 600))
    for name in [n for names in config.CARD_FAMILIES.values() for n in names]:
        assert app.assets.sprite(name).get_size() == (16, 16), name
    for make in (menu.MenuScene, level_select.LevelSelectScene, custom.CustomScene, help_.HelpScene,
                 leaderboard.LeaderboardScene, achievements.AchievementsScene, settings.SettingsScene,
                 about.AboutScene, daily.DailyScene, online.OnlineScene, online_leaderboard.OnlineLeaderboardScene):
        make(app).draw(app.screen)
    print("selftest OK", config.APP_NAME, config.VERSION)
    return 0


def agent(argv) -> int:
    """`Orderwick --agent ...`: Claude plays the real game through its own keyboard input (see orderwick/agent_player.py)."""
    from orderwick import agent_player
    args = agent_player.prepare(argv)                       # the environment must be set before the game is imported
    from orderwick import agent_run
    return agent_run.run(args)


def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()                        # needed so frozen builds can start the sound process
    if "--agent" in sys.argv:
        code = 1
        try:
            code = agent(sys.argv[1:])
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)                                  # no interpreter teardown: same reason as the selftest below
    if "--dev" in sys.argv:                                 # local testing: everything unlocked, separate save folder
        os.environ["ORDERWICK_DEV"] = "1"
    if "--no-audio" in sys.argv:
        os.environ["ORDERWICK_NO_AUDIO"] = "1"
    from orderwick.engine.logs import log_error, log_path
    try:                                                   # a native crash (segfault) leaves a trace in crash.log
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        faulthandler.enable(open(path, "a", encoding="utf-8"), all_threads=True)
    except Exception:
        pass
    if "--selftest" in sys.argv:                            # for CI: does the build start at all and load every resource
        code = selftest()
        # Leave without interpreter finalisation, exactly like the real game does: tearing down SDL/pygame during a normal
        # Python exit segfaulted in the Linux build AFTER "selftest OK" had already been printed.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    from orderwick.game import OrderwickGame
    try:
        OrderwickGame().start()
    except Exception as exc:
        log_error("unhandled exception", exc)
        raise
    # Everything is saved and pygame is closed. Leave without interpreter finalisation: background threads (board
    # generation) and native audio libraries can otherwise crash the process while it is shutting down.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

"""Random keys/clicks over all screens (headless) - looks for exceptions and hangs.

    python tools/monkey_test.py [number_of_events] [seed]
"""
import os
import random
import sys
import tempfile
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["ORDERWICK_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from orderwick.game import OrderwickGame
from orderwick.scenes.menu import MenuScene

KEYS = [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE,
        pygame.K_TAB, pygame.K_u, pygame.K_x, pygame.K_r, pygame.K_p, pygame.K_q, pygame.K_PAGEUP, pygame.K_PAGEDOWN,
        pygame.K_BACKSPACE] + [ord(c) for c in "1234567890asdfghjkl"]


def main(n: int = 20000, seed: int = 1) -> int:
    rng = random.Random(seed)
    app = OrderwickGame()
    app.running = True
    sizes = [(1180, 780), (900, 620), (640, 400), (1920, 1080), (1280, 720)]
    app.screen = pygame.display.set_mode(sizes[0])
    app.scenes.reset(MenuScene(app))
    errors = 0
    visited: set[str] = set()
    for i in range(n):
        w, h = app.screen.get_size()
        r = rng.random()
        if r < 0.45:
            k = rng.choice(KEYS)
            ev = pygame.event.Event(pygame.KEYDOWN, key=k, unicode=chr(k) if 32 <= k < 127 else "", mod=0)
        elif r < 0.75:
            ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(rng.randrange(w), rng.randrange(h)),
                                    button=rng.choice([1, 1, 1, 3, 4, 5]))
        elif r < 0.88:
            ev = pygame.event.Event(pygame.MOUSEMOTION, pos=(rng.randrange(w), rng.randrange(h)), rel=(0, 0), buttons=(0, 0, 0))
        elif r < 0.92:
            ev = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(rng.randrange(w), rng.randrange(h)), button=1)
        elif r < 0.95:
            ev = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=rng.choice([-1, 1]))
        else:
            ev = None
            app.screen = pygame.display.set_mode(rng.choice(sizes))
        try:
            if ev is not None:
                app.scenes.handle_event(ev)
            app.scenes.update(1 / 30)
            app.update_overlay(1 / 30)
            app.scenes.draw(app.screen)
            app.draw_overlay(app.screen)
        except Exception:                     # noqa: BLE001
            errors += 1
            import traceback
            print(f"EVENT {i}: {ev}\n", traceback.format_exc())
            if errors > 3:
                break
        if app.scenes.current is not None:
            visited.add(type(app.scenes.current).__name__)
        if not app.running:                   # "Quit" from the menu: continue
            app.running = True
            app.scenes.reset(MenuScene(app))
        if len(app.scenes) == 0:
            app.scenes.reset(MenuScene(app))
        if i % 500 == 0:
            time.sleep(0.02)                  # let background threads run (the board generator)
    print(f"events={n} errors={errors} scenes_left={len(app.scenes)} visited={sorted(visited)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000, int(sys.argv[2]) if len(sys.argv) > 2 else 1))

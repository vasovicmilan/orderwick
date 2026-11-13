"""Imports your Aseprite sources: renames them to the in-game names and exports every PNG the game needs.

    python tools/import_aseprite.py path/to/folder_with_aseprite_files

CARDS (16x16, 2 frames: frame 0 = classic card, frame 1 = gold card; bottom layer = background, top layer = fruit)
  assets/sprites/<name>.png                 classic card (what the game uses)
  assets/card_styles/gold/<name>.png        gold card
  assets/aseprite/cards/<name>.aseprite     your source, renamed to the in-game name
  export/classic|gold|transparent/<name>.png  loose copies; "transparent" = the fruit layer alone, no background
BOARD (board.aseprite: 193x217, layer 1 of a frame is the board; the other layers are only mock-ups)
  frame 0 = wood board (the default), frame 3 = emerald board  (change with --board-frame id:frame)
  assets/themes/<id>/board/board.png + the matching HUD/dialog/icon assets (tools/make_theme.py)
  export/board/board_<id>.png
Old file names (bannana, eqlamtion, ...) are understood; files that already have the in-game name work too.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from aseprite_io import read_aseprite  # noqa: E402
from orderwick import config  # noqa: E402

OLD_TO_NEW = {
    "bannana": "yellow_banana", "beets": "purple_beet", "blueapple": "blue_apple", "buleberry": "blue_berry",
    "carrot": "orange_carrot", "carrotpurple": "purple_carrot", "carrotwhite": "white_carrot", "chary": "red_cherry",
    "charyblue": "blue_cherry", "charypurple": "purple_cherry", "charyyellow": "yellow_cherry",
    "coconout": "brown_coconut", "coockie": "tan_cookie", "eggplant": "purple_eggplant",
    "eggplanteyellow": "yellow_eggplant", "eggplantgreen": "green_eggplant", "eqlamtion": "exclamation_mark",
    "exclamationmark": "exclamation_mark", "grape": "purple_grape", "grapeblue": "blue_grape",
    "grapegreen": "green_grape", "grapeorange": "orange_grape", "grapered": "red_grape",
    "grapeyellow": "yellow_grape", "greenapple": "green_apple", "greenbery": "green_berry", "kiwi": "brown_kiwi",
    "mango": "orange_mango", "peerblue": "blue_pear", "peergreen": "green_pear", "peerred": "red_pear",
    "peeryellow": "yellow_pear", "pumkin": "orange_pumpkin", "questionmark": "question_mark",
    "raddishwhite": "white_radish", "redapple": "red_apple", "redberry": "red_berry",
    "sunflower": "yellow_sunflower", "wattermallon": "red_watermelon", "yelllowapple": "yellow_apple",
    "yellowbery": "yellow_berry",
}
CARD_NAMES = [n for fam in config.CARD_FAMILIES.values() for n in fam] + [config.HIDDEN_SPRITE, config.BLOCKED_SPRITE]


def to_surface(rgba: bytes, w: int, h: int) -> pygame.Surface:
    return pygame.image.frombytes(rgba, (w, h), "RGBA")


def save(surface: pygame.Surface, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))


def import_cards(src: Path) -> list[str]:
    notes, done = [], []
    for f in sorted(src.glob("*.aseprite")):
        if f.stem == "board":
            continue
        name = OLD_TO_NEW.get(f.stem, f.stem)
        if name not in CARD_NAMES:
            notes.append(f"skipped {f.name}: not a known card name")
            continue
        s = read_aseprite(f)
        if (s.width, s.height) != (16, 16) or s.frame_count < 2 or len(s.layers) < 2:
            notes.append(f"{f.name}: expected 16x16, 2 frames and 2 layers (got {s.width}x{s.height}, {s.frame_count} frames, "
                         f"{len(s.layers)} layers)")
            continue
        classic, gold = to_surface(s.flatten(0), 16, 16), to_surface(s.flatten(1), 16, 16)
        fruit = pygame.Surface((16, 16), pygame.SRCALPHA)
        cel = s.cels[(0, len(s.layers) - 1)]
        fruit.blit(to_surface(cel.rgba, cel.width, cel.height), (cel.x, cel.y))
        for surface, rel in ((classic, f"assets/sprites/{name}.png"), (gold, f"assets/card_styles/gold/{name}.png"),
                             (classic, f"export/classic/{name}.png"), (gold, f"export/gold/{name}.png"),
                             (fruit, f"export/transparent/{name}.png")):
            save(surface, ROOT / rel)
        dst = ROOT / "assets" / "aseprite" / "cards" / f"{name}.aseprite"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        done.append(name)
    missing = sorted(set(CARD_NAMES) - set(done))
    if missing:
        notes.append("no source found for: " + ", ".join(missing))
    for n in notes:
        print("NOTE", n)
    print(f"cards: {len(done)} imported (classic + gold + transparent)")
    return done


def import_board(src: Path, boards: list[str]) -> None:
    f = src / "board.aseprite"
    if not f.exists():
        print("NOTE no board.aseprite in the folder; board skipped")
        return
    s = read_aseprite(f)
    if (s.width, s.height) != (193, 217):
        print(f"NOTE board.aseprite is {s.width}x{s.height}, expected 193x217; board skipped")
        return
    dst = ROOT / "assets" / "aseprite" / "board.aseprite"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(f, dst)
    for spec in boards:
        theme_id, frame = spec.split(":")
        cel = s.cels[(int(frame), 0)]
        board = to_surface(cel.rgba, cel.width, cel.height)
        save(board, ROOT / "export" / "board" / f"board_{theme_id}.png")
        default = config.ASSETS_DIR / config.BOARD_IMAGE
        if theme_id == config.BOARD_THEMES[0][0]:
            same = pygame.image.tobytes(board, "RGBA") == pygame.image.tobytes(pygame.image.load(str(default)), "RGBA")
            print(f"board '{theme_id}' (frame {frame}):", "identical to assets/board/board.png" if same else
                  "DIFFERS from assets/board/board.png (copy export/board/board_%s.png over it if intended)" % theme_id)
        else:
            subprocess.run([sys.executable, str(ROOT / "tools" / "make_theme.py"), theme_id, "--board",
                            str(ROOT / "export" / "board" / f"board_{theme_id}.png"), "--rederive"], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--board-frame", action="append", default=None, metavar="ID:FRAME",
                    help="which frame of board.aseprite is which board (default wood:0 emerald:3)")
    args = ap.parse_args()
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    import_cards(args.folder)
    import_board(args.folder, args.board_frame or ["wood:0", "emerald:3"])


if __name__ == "__main__":
    main()

"""Builds a BOARD THEME: your board drawing + HUD, dialog and icon assets in the board's own palette.

    python tools/make_theme.py emerald --board path/to/emerald_board.png

What it does
  1. copies the board to assets/themes/<id>/board/board.png (must be 193 x 217, same layout as assets/board/board.png);
  2. reads the palette of the new board by comparing it pixel by pixel with the default board (the same pixel in both
     boards tells which new colour plays the role of WOOD, DARK, MID, PLANK, PLANK_L, TAN, CREAM);
  3. writes assets/themes/<id>/palette.json (roles you can edit by hand) and generates panel, inset, button (4 states),
     divider, icons and icons_audio in that palette with the SAME generators as the default look (tools/make_hud_assets.py).
Re-run without --board to regenerate the HUD after editing palette.json; add --rederive to read the palette from the board again.
Anything you draw by hand later simply replaces the generated file.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_audio_icons as audio_icons  # noqa: E402
import make_hud_assets as hud  # noqa: E402

BASE_ROLES = ["WOOD", "DARK", "MID", "PLANK", "PLANK_L", "TAN", "CREAM"]


def lum(c) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def derive_palette(default_board: pygame.Surface, new_board: pygame.Surface) -> dict:
    """Role colours of the new board: the most common colour found at the pixels where the default board has the role colour."""
    pairs: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for y in range(default_board.get_height()):
        for x in range(default_board.get_width()):
            pairs[tuple(default_board.get_at((x, y)))[:3]][tuple(new_board.get_at((x, y)))[:3]] += 1
    palette = {}
    for role in BASE_ROLES:
        key = tuple(hud.DEFAULT_PALETTE[role])
        if key not in pairs:
            raise SystemExit(f"the default board has no pixel of colour {role} {key}")
        palette[role] = pairs[key].most_common(1)[0][0]
    # roles that do not exist as separate colours on the board are derived from the base ones
    white = (255, 255, 255)
    p = palette
    palette["BTN_LIGHT"] = p["TAN"] if lum(p["TAN"]) > lum(p["PLANK_L"]) + 10 else mix(p["PLANK_L"], white, 0.45)
    palette["BTN_HOVER_LIGHT"] = (p["CREAM"] if lum(p["CREAM"]) > lum(palette["BTN_LIGHT"]) + 10
                                  else mix(p["PLANK_L"], white, 0.75))
    palette["BTN_HOVER_BODY"] = mix(p["PLANK_L"], white, 0.2)
    palette["BTN_DISABLED_BODY"] = mix(p["WOOD"], p["MID"], 0.35)
    palette["ICON_LIGHT"] = max((p["CREAM"], palette["BTN_HOVER_LIGHT"], p["PLANK_L"]), key=lum)
    palette["ICON_MID"] = palette["BTN_LIGHT"]
    # text / UI colours (read by orderwick/view/colors.py): light buttons get dark labels with a light shadow
    light_buttons = lum(p["PLANK_L"]) > 170
    palette["TEXT"] = palette["ICON_LIGHT"]
    palette["TEXT_DIM"] = mix(palette["TEXT"], p["PLANK"], 0.3)
    palette["TEXT_SHADOW"] = p["DARK"]
    palette["BTN_TEXT"] = mix(p["DARK"], (0, 0, 0), 0.3) if light_buttons else palette["TEXT"]
    palette["BTN_TEXT_SHADOW"] = palette["BTN_HOVER_LIGHT"] if light_buttons else p["DARK"]
    palette["DISABLED_TEXT"] = mix(p["PLANK"], p["WOOD"], 0.4)
    palette["UI_DIM"] = p["MID"]
    palette["HIGHLIGHT"] = mix(p["WOOD"], (255, 205, 80), 0.35)
    if light_buttons:                                         # row values must be readable on light buttons
        palette["BTN_VALUE"] = mix((255, 205, 80), (0, 0, 0), 0.65)
        palette["BTN_GOOD"] = (16, 98, 48)
        palette["BTN_BAD"] = (150, 36, 36)
    return palette


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("theme_id")
    ap.add_argument("--board", help="the board PNG of the theme (193x217)")
    ap.add_argument("--rederive", action="store_true", help="read the palette from the board again (overwrites palette.json)")
    args = ap.parse_args()
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    theme = ROOT / "assets" / "themes" / args.theme_id
    board_path = theme / "board" / "board.png"
    if args.board:
        board_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.board, board_path)
    if not board_path.exists():
        raise SystemExit("no board yet: pass --board path/to/board.png")
    new_board = pygame.image.load(str(board_path)).convert_alpha()
    default_board = pygame.image.load(str(ROOT / "assets" / "board" / "board.png")).convert_alpha()
    if new_board.get_size() != default_board.get_size():
        raise SystemExit(f"the board must be {default_board.get_size()}, it is {new_board.get_size()}")
    palette_path = theme / "palette.json"
    if palette_path.exists() and not args.rederive:
        palette = {k: tuple(v) for k, v in json.loads(palette_path.read_text()).items()}
    else:
        palette = derive_palette(default_board, new_board)
        palette_path.write_text(json.dumps({k: list(v) for k, v in palette.items()}, indent=2))
    hud.set_palette(palette)
    out = theme / "hud"
    out.mkdir(parents=True, exist_ok=True)
    made = {"panel": hud.make_panel(), "inset": hud.make_inset(), "button": hud.make_button(),
            "divider": hud.make_divider(), "icons": hud.make_icons(), "icons_audio": audio_icons.make_sheet()}
    for name, image in made.items():
        pygame.image.save(image, str(out / f"{name}.png"))
    print("theme", args.theme_id, "palette:", {k: v for k, v in palette.items()})
    print("wrote", ", ".join(f"hud/{n}.png" for n in made), "and board/board.png")


if __name__ == "__main__":
    main()

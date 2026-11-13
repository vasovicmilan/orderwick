"""Icons for sound/menu (12x12, same style as the HUD icons): music, sound, mute, gear, trophy, cards.

Creates assets/hud/icons_audio.png (a 72x12 strip) and assets/aseprite/icons_audio.aseprite (one frame per icon).
The order must match config.AUDIO_ICON_ORDER.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pygame
import make_hud_assets as hud

ICONS = {
    "music": [
        "..xxxxx.", "..xxxxx.", "..x...x.", "..x...x.", "..x...x.", ".xx..xx.", "xxx.xxx.", ".x...x..",
    ],
    "sound": [
        "...x....", "..xx..x.", "xxxx...x", "xxxx.x.x", "xxxx.x.x", "xxxx...x", "..xx..x.", "...x....",
    ],
    "mute": [
        "...x....", "..xx.r.r", "xxxx..r.", "xxxx.r.r", "xxxx....", "xxxx....", "..xx....", "...x....",
    ],
    "gear": [
        "...xx...", "x.xxxx.x", ".xxppxx.", "xxxppxxx", "xxxppxxx", ".xxppxx.", "x.xxxx.x", "...xx...",
    ],
    "trophy": [
        "gggggggg", "gggggggg", "g.gggg.g", ".gggggg.", "..gggg..", "...gg...", "...gg...", ".gggggg.",
    ],
    "cards": [
        "..oooooo", "..oxxxxo", "ooooxxxo", "oxxoxxxo", "oxxoooo.", "oxxxxxo.", "oxxxxxo.", "ooooooo.",
    ],
}
ORDER = list(ICONS)


def make_cell(name: str) -> pygame.Surface:
    rows = ICONS[name]
    mask = {(x, y): hud.COLORS[ch] for y, row in enumerate(rows) for x, ch in enumerate(row) if ch != "."}
    cell = hud.surf(12, 12)
    for (x, y) in mask:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n not in mask:
                    cell.set_at((n[0] + 2, n[1] + 2), hud.DARK)
    for (x, y), c in mask.items():
        cell.set_at((x + 2, y + 2), c)
    return cell


def make_sheet() -> pygame.Surface:
    sheet = hud.surf(12 * len(ORDER), 12)
    for i, name in enumerate(ORDER):
        sheet.blit(make_cell(name), (i * 12, 0))
    return sheet


def main() -> None:
    root = hud.ROOT
    sys.path.insert(0, str(root))
    from orderwick import config
    assert ORDER == config.AUDIO_ICON_ORDER
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    sheet = make_sheet()
    pygame.image.save(sheet, str(root / "assets" / config.AUDIO_ICONS))
    from aseprite_io import Cel, Layer, Sprite, Tag, surface_to_rgba, write_aseprite
    import export_aseprite as ex
    sp = Sprite(12, 12, layers=[Layer("HUD")], palette=ex._palette())
    for i, name in enumerate(ORDER):
        sp.durations.append(100)
        sp.cels[(i, 0)] = Cel(0, 0, 12, 12, surface_to_rgba(sheet.subsurface(pygame.Rect(i * 12, 0, 12, 12)).copy()))
        sp.tags.append(Tag(name, i, i))
    write_aseprite(root / "assets" / "aseprite" / "icons_audio.aseprite", sp)
    print("icons_audio.png", sheet.get_size())


if __name__ == "__main__":
    main()

"""Exports the HUD elements as .aseprite (source files for drawing) to assets/aseprite/.

panel.aseprite   16x16, slice 'panel' 9-patch (edge 6)
inset.aseprite   12x12, slice 'inset' 9-patch (edge 4)
button.aseprite  12x12, 4 frames (normal/hover/pressed/disabled), tags, slice 'button' 9-patch (edge 4)
icons.aseprite   12x12, 8 frames, one tag per icon
divider.aseprite 4x2
After drawing: File > Export Sprite Sheet > Horizontal strip (no spacing, no trim) -> PNG in assets/hud/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pygame
import make_hud_assets as m
from aseprite_io import Cel, Layer, Slice, SliceKey, Sprite, Tag, surface_to_rgba, write_aseprite

OUT = m.ROOT / "assets" / "aseprite"


def _palette():
    colors = [(0, 0, 0, 0)]
    for c in (m.DARK, m.WOOD, m.MID, m.PLANK, m.PLANK_L, m.TAN, m.CREAM, m.GOLD, m.GOLD_D, m.GREEN,
              m.GREEN_D, m.RED, m.BLUE):
        colors.append((*c, 255))
    return colors


def _sprite(w, h, frames, layer="HUD", durations=100):
    sp = Sprite(w, h, layers=[Layer(layer)], palette=_palette())
    for i, surf in enumerate(frames):
        sp.durations.append(durations)
        sp.cels[(i, 0)] = Cel(0, 0, w, h, surface_to_rgba(surf))
    return sp


def _nine(name, w, h, edge):
    return Slice(name, [SliceKey(0, 0, 0, w, h, (edge, edge, w - 2 * edge, h - 2 * edge))])


def main():
    """python tools/export_aseprite.py [theme_id]  - the default look, or a theme's HUD (assets/aseprite/themes/<id>/)."""
    global OUT
    import json
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    if len(sys.argv) > 1:
        theme = sys.argv[1]
        m.set_palette({k: v for k, v in json.loads((m.ROOT / "assets" / "themes" / theme / "palette.json").read_text()).items()})
        OUT = m.ROOT / "assets" / "aseprite" / "themes" / theme
    OUT.mkdir(parents=True, exist_ok=True)

    sp = _sprite(16, 16, [m.make_panel()]); sp.slices.append(_nine("panel", 16, 16, 6))
    write_aseprite(OUT / "panel.aseprite", sp)

    sp = _sprite(12, 12, [m.make_inset()]); sp.slices.append(_nine("inset", 12, 12, 4))
    write_aseprite(OUT / "inset.aseprite", sp)

    sheet = m.make_button()
    states = ["normal", "hover", "pressed", "disabled"]
    frames = [sheet.subsurface(pygame.Rect(i * 12, 0, 12, 12)).copy() for i in range(4)]
    sp = _sprite(12, 12, frames)
    sp.tags = [Tag(s, i, i) for i, s in enumerate(states)]
    sp.slices.append(_nine("button", 12, 12, 4))
    write_aseprite(OUT / "button.aseprite", sp)

    sheet = m.make_icons()
    frames = [sheet.subsurface(pygame.Rect(i * 12, 0, 12, 12)).copy() for i in range(len(m.ICON_ORDER))]
    sp = _sprite(12, 12, frames)
    sp.tags = [Tag(n, i, i) for i, n in enumerate(m.ICON_ORDER)]
    write_aseprite(OUT / "icons.aseprite", sp)

    write_aseprite(OUT / "divider.aseprite", _sprite(4, 2, [m.make_divider()]))
    for p in sorted(OUT.glob("*.aseprite")):
        print(p.name, p.stat().st_size, "B")


if __name__ == "__main__":
    main()

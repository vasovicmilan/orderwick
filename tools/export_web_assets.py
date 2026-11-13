"""Exports what the browser version needs to draw EXACTLY like the desktop game: the HUD/board art and bitmap copies of
the two pixel fonts (rendered by pygame itself, unsmoothed, so every letter is the same pixels as on the desktop).

    python tools/export_web_assets.py ../orderwick-server/src/public/game
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame  # noqa: E402

from orderwick import config  # noqa: E402

CHARS = "".join(chr(c) for c in range(32, 127)) + "×·—…←→"


def export_font(path: Path, out_png: Path, out_json: Path) -> None:
    font = pygame.font.Font(str(path), 8)
    chars = [c for c in CHARS if font.metrics(c)[0] is not None]
    adv = [font.size(c)[0] for c in chars]
    heights = [font.render(c, False, (255, 255, 255)).get_height() for c in chars]
    h = max(heights)
    cell = max(adv + [1])
    sheet = pygame.Surface((cell * len(chars), h), pygame.SRCALPHA)
    for i, c in enumerate(chars):
        if c == " ":
            continue
        img = font.render(c, False, (255, 255, 255)).convert_alpha()
        sheet.blit(img, (i * cell, 0))
    pygame.image.save(sheet, str(out_png))
    out_json.write_text(json.dumps({"chars": "".join(chars), "adv": adv, "cell": cell, "h": h,
                                    "line": font.get_height()}), encoding="utf-8")


def main(dest: str) -> None:
    pygame.font.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    out = Path(dest)
    (out / "hud").mkdir(parents=True, exist_ok=True)
    (out / "board").mkdir(parents=True, exist_ok=True)
    (out / "fonts").mkdir(parents=True, exist_ok=True)
    assets = config.ASSETS_DIR
    for rel in (config.HUD_PANEL, config.HUD_INSET, config.HUD_BUTTON, config.HUD_ICONS, config.BOARD_IMAGE):
        shutil.copyfile(assets / rel, out / rel)
    export_font(config.FONT_PATH, out / "fonts" / "pixel8.png", out / "fonts" / "pixel8.json")
    export_font(config.BODY_FONT_PATH, out / "fonts" / "body8.png", out / "fonts" / "body8.json")
    print("exported to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "web_assets")

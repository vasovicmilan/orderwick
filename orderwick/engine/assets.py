"""Loading and caching resources (images, fonts)."""
from __future__ import annotations

from pathlib import Path

import pygame

from .. import config
from .pixel_font import PixelFont


class AssetManager:
    def __init__(self, sprites_dir: Path):
        self.sprites_dir = Path(sprites_dir)
        self._sprites: dict[str, pygame.Surface] = {}
        self._fonts: dict[int, PixelFont] = {}
        self.theme_dir: Path | None = None          # assets/themes/<id> (None = default look)
        self.style_dir: Path | None = None          # assets/card_styles/<id> (None = classic cards)
        self.theme_palette: dict = {}               # text/UI colour roles of the theme (palette.json), {} = defaults
        self.theme_frame: dict | None = None        # animated frame around the board (frame.json of the theme), None = no frame
        self.extra_sprites_dir: Path | None = None  # cards that came from the server (looked up after the built-in ones)

    # ---- looks (see config.BOARD_THEMES / CARD_STYLES) ---------------------------------------------------
    def set_theme(self, directory: Path | None) -> None:
        if directory != self.theme_dir:
            self.theme_dir = directory
            self._sprites.clear()                   # everything cached may have come from the old look
        self.theme_palette = {}
        self.theme_frame = self._read_frame(directory)
        if directory is not None and (directory / "palette.json").exists():
            import json
            try:
                self.theme_palette = {k: tuple(v) for k, v in json.loads((directory / "palette.json").read_text()).items()}
            except (OSError, ValueError, TypeError):
                self.theme_palette = {}

    @staticmethod
    def _read_frame(directory: Path | None) -> dict | None:
        """frame.json: {"style": "flames" | "vines" | "storm", "fps": 4..30}. Anything invalid means no frame."""
        if directory is None or not (directory / "frame.json").exists():
            return None
        import json
        from ..view import frame_fx
        try:
            raw = json.loads((directory / "frame.json").read_text())
            style = raw.get("style")
            fps = float(raw.get("fps", 10))
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        if style not in frame_fx.STYLES:
            return None
        return {"style": style, "fps": max(4.0, min(30.0, fps))}

    def set_card_style(self, directory: Path | None) -> None:
        if directory != self.style_dir:
            self.style_dir = directory
            self._sprites.clear()

    def _load(self, path: Path) -> pygame.Surface:
        return pygame.image.load(str(path)).convert_alpha()

    def sprite(self, name: str) -> pygame.Surface:
        """A card sprite at its original (unscaled) size, from the selected card style (classic if the style lacks it)."""
        surf = self._sprites.get(name)
        if surf is None:
            candidates = []
            if self.style_dir is not None:
                candidates.append(self.style_dir / f"{name}.png")
            candidates.append(self.sprites_dir / f"{name}.png")
            if self.extra_sprites_dir is not None:
                candidates.append(self.extra_sprites_dir / f"{name}.png")
            for path in candidates:
                try:
                    surf = self._load(path)
                    break
                except (FileNotFoundError, pygame.error):
                    continue
            if surf is None:                                  # image missing: show a question mark instead of crashing
                from .logs import log_error
                log_error(f"missing sprite {name}")
                surf = self._sprites.get(config.HIDDEN_SPRITE) or self._load(self.sprites_dir / f"{config.HIDDEN_SPRITE}.png")
            self._sprites[name] = surf
        return surf

    def image(self, rel_path: str) -> pygame.Surface:
        """Image relative to the `assets` directory (e.g. "board/board.png"); the selected theme may override it."""
        key = "img:" + rel_path
        surf = self._sprites.get(key)
        if surf is None:
            path = self.sprites_dir.parent / rel_path
            if self.theme_dir is not None and (self.theme_dir / rel_path).exists():
                path = self.theme_dir / rel_path
            surf = self._sprites[key] = self._load(path)
        return surf

    @staticmethod
    def scale_for_size(size: int) -> int:
        """Converts the requested "size" (letter height in px) into an integer scale factor of the pixel font."""
        if size < 17:
            return 1
        if size < 39:
            return 2
        if size < 57:
            return 3
        if size < 81:
            return 4
        return 6

    def pixel_font(self, scale: int) -> PixelFont:
        font = self._fonts.get(scale)
        if font is None:
            font = self._fonts[scale] = PixelFont(config.FONT_PATH, scale)
        return font

    def font(self, size: int, bold: bool = False) -> PixelFont:
        """Pixel font of roughly the requested `size` (bold is ignored: the font has a single weight)."""
        return self.pixel_font(self.scale_for_size(size))

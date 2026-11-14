"""Drawing the board.

The board is assembled from the `board.png` asset (BoardSkin), cards are drawn over it at the original pixel-art
resolution, and then the WHOLE picture is scaled by an integer factor (nearest neighbour). So the frame, lane and cards
scale by the same factor.
"""
from __future__ import annotations

import pygame

from .. import config
from ..core.board import Board
from ..core.models import COL, FREE, Loc, col, slot
from ..engine.assets import AssetManager
from ..engine.ui import draw_text
from . import frame_fx, lane_fx
from .board_skin import BORDER, CELL, GAP, PITCH, BoardSkin
from .colors import GOLD, TAN

LABEL_GAP = 6          # gap between the board and the labels (screen px)
LABEL_HEIGHT = 8       # label height in font pixels (scaled by the same factor as the board)


class BoardView:
    # An animated frame (board theme with frame.json) is frame_fx.MARGIN px wide on every side. When fitting the board into
    # the window only FRAME_FIT_MARGIN of it is reserved, so a frame does not shrink the board on a tight window: the
    # outer flames/vines may then be cut by the window edge.
    FRAME_FIT_MARGIN = 8
    fit_margin = 0                                 # set by the game when the theme has a frame

    def __init__(self, assets: AssetManager):
        self.assets = assets
        self._frame_key: tuple | None = None
        self._frame_native: list[pygame.Surface] = []
        self._frame_shown: tuple | None = None
        self._lane_fx: lane_fx.LaneFx | None = None
        self._lane_key: tuple | None = None
        self.skin = BoardSkin(assets.image(config.BOARD_IMAGE))
        self.scale = 1
        self.origin = (0, 0)
        self.n_cols = 0
        self.n_free = 0
        self.capacity = 0

    # ---- raspored ----------------------------------------------------------------
    @staticmethod
    def native_size(n_cols: int, capacity: int) -> tuple[int, int]:
        return BoardSkin.native_size(n_cols, capacity)

    @staticmethod
    def fit_scale(n_cols: int, capacity: int, width: int, height: int, extra_native_w: int = 0,
                  min_native_h: int = 0) -> int:
        """The largest integer S at which the board (n_cols x capacity), `extra_native_w` asset pixels at the
        side (e.g. the HUD) and the labels (letters above/below the board, LABEL_HEIGHT * S tall) fit."""
        bw, bh = BoardSkin.native_size(n_cols, capacity)
        bw, bh = bw + 2 * BoardView.fit_margin, bh + 2 * BoardView.fit_margin
        for s in range(config.MAX_SCALE, 0, -1):
            if ((bw + extra_native_w + 8) * s <= width and min_native_h * s <= height
                    and bh * s + 2 * (LABEL_HEIGHT * s + LABEL_GAP) <= height):
                return s
        return 1

    def layout(self, board: Board, area: pygame.Rect, scale: int | None = None) -> None:
        self.n_cols, self.n_free, self.capacity = board.n_cols, board.n_free, board.capacity
        w, h = self.native_size(self.n_cols, self.capacity)
        if scale is None:
            scale = self.fit_scale(self.n_cols, self.capacity, area.width, area.height)
        self.scale = max(1, min(config.MAX_SCALE, scale))
        self.origin = (area.centerx - w * self.scale // 2, area.centery - h * self.scale // 2)

    @property
    def screen_rect(self) -> pygame.Rect:
        w, h = self.native_size(self.n_cols, self.capacity)
        return pygame.Rect(self.origin, (w * self.scale, h * self.scale))

    def cell_rect(self, c: int, r: int) -> pygame.Rect:
        """r = 0: a slot in the free-slot row; r = 1..k: card rows from top to bottom."""
        s = self.scale
        x, y = self.skin.row_pos(c, r)
        return pygame.Rect(self.origin[0] + x * s, self.origin[1] + y * s, CELL * s, CELL * s)

    def _slot_grid_col(self, index: int) -> int:
        return self.n_cols - self.n_free + index

    def loc_rect(self, loc: Loc) -> pygame.Rect:
        if loc.kind == FREE:
            return self.cell_rect(self._slot_grid_col(loc.index), 0)
        return self.cell_rect(loc.index, 1).union(self.cell_rect(loc.index, self.capacity))

    def _run_rect(self, board: Board, ci: int) -> pygame.Rect:
        """The top card and the run of IDENTICAL REVEALED cards below it.

        Hidden cards are deliberately not included: otherwise the frame would reveal that the cards below are the same type.
        """
        column = board.columns[ci]
        top_row = self.capacity - (len(column) - 1)
        run = 0
        for card in reversed(column):
            if card.kind != column[-1].kind or not card.up:
                break
            run += 1
        return self.cell_rect(ci, top_row).union(self.cell_rect(ci, top_row + max(run, 1) - 1))

    # ---- misa -------------------------------------------------------------------
    def hit_test(self, pos: tuple[int, int]) -> Loc | None:
        s = self.scale
        x = (pos[0] - self.origin[0]) // s
        y = (pos[1] - self.origin[1]) // s
        w, h = self.native_size(self.n_cols, self.capacity)
        if not (0 <= x < w and 0 <= y < h):
            return None
        c = min(max((x - BORDER) // PITCH, 0), self.n_cols - 1)      # the gap to the right of a lane belongs to that lane
        if y < BORDER + CELL + GAP // 2 + 1:                         # the free-slot row
            index = c - (self.n_cols - self.n_free)
            return slot(index) if index >= 0 else None              # locked slots cannot be picked
        return col(c)

    # ---- drawing ------------------------------------------------------------------
    def _render_native(self, board: Board, palette: list[str]) -> pygame.Surface:
        base = self.skin.build(self.n_cols, self.capacity)
        surf = base.copy()
        self._blit_lane_fx(surf, base)
        assets = self.assets
        for c in range(self.n_cols - self.n_free):                    # locked slots
            surf.blit(assets.sprite(config.BLOCKED_SPRITE), self.skin.slot_pos(c))
        for i, kind in enumerate(board.free):
            if kind is not None:
                surf.blit(assets.sprite(palette[kind]), self.skin.slot_pos(self._slot_grid_col(i)))
        for ci, column in enumerate(board.columns):
            complete = board.is_complete(ci)
            for j, card in enumerate(column):                         # j = 0 is the bottom card
                name = palette[card.kind] if (card.up or complete) else config.HIDDEN_SPRITE
                surf.blit(assets.sprite(name), self.skin.card_pos(ci, j, self.capacity))
        return surf

    @staticmethod
    def _outline(surface: pygame.Surface, rect: pygame.Rect, color, thickness: int, pad: int) -> None:
        pygame.draw.rect(surface, color, rect.inflate(2 * pad, 2 * pad), thickness)

    def draw(self, surface: pygame.Surface, board: Board, palette: list[str],
             selected: Loc | None = None, cursor: Loc | None = None, hover: Loc | None = None) -> None:
        self.layout_from_board(board)
        native = self._render_native(board, palette)
        w, h = native.get_size()
        surface.blit(pygame.transform.scale(native, (w * self.scale, h * self.scale)), self.origin)
        self._draw_frame(surface, w, h)

        s = self.scale
        thick = max(2, s)
        for ci in range(board.n_cols):
            if board.is_complete(ci):
                self._outline(surface, self.loc_rect(col(ci)), config.COLOR_GOOD, max(2, s // 2 + 1), s)
        if hover is not None and hover != selected:
            self._outline(surface, self.loc_rect(hover), (255, 255, 255), max(1, s // 2), s)
        if cursor is not None:
            self._outline(surface, self.loc_rect(cursor), config.COLOR_CURSOR, thick, s)
        if selected is not None:
            if selected.kind == COL and board.columns[selected.index]:
                rect = self._run_rect(board, selected.index)
            else:
                rect = self.loc_rect(selected)
            self._outline(surface, rect, config.COLOR_SELECT, thick + 1, s)
        self._draw_labels(surface, board, cursor, selected)

    def _blit_lane_fx(self, surf: pygame.Surface, base: pygame.Surface) -> None:
        """A themed board with an animated frame also moves a little inside its lanes (under the cards)."""
        spec = self.assets.theme_frame
        if not spec:
            self._lane_fx = self._lane_key = None
            return
        key = (spec["style"], id(base), str(self.assets.theme_dir))
        if key != self._lane_key:
            try:
                self._lane_fx, self._lane_key = lane_fx.LaneFx(spec["style"], base), key
            except Exception as error:                              # decoration is a bonus: never break the game for it
                from ..engine.logs import log_error
                log_error(f"lane fx {spec['style']}: {error}")
                self._lane_fx, self._lane_key = None, key
        fx = self._lane_fx
        if fx is None:
            return
        if not fx.complete:
            start = pygame.time.get_ticks()
            while not fx.complete and (not fx.frames or pygame.time.get_ticks() - start < 6):
                fx.build_next()
        index = int(pygame.time.get_ticks() * spec["fps"] / 1000) % lane_fx.LOOP
        surf.blit(fx.frames[index % len(fx.frames)], (0, 0))

    def _draw_frame(self, surface: pygame.Surface, w: int, h: int) -> None:
        """The animated frame of the theme around the board (nothing if the theme has none)."""
        spec = self.assets.theme_frame
        if not spec:
            self._frame_key = None
            return
        key = (spec["style"], w, h, self.scale)
        if key != self._frame_key:
            self._frame_key, self._frame_native, self._frame_shown = key, [], None      # frames are drawn one by one (below)
        if len(self._frame_native) < frame_fx.FRAME_COUNT:
            start = pygame.time.get_ticks()
            try:
                while len(self._frame_native) < frame_fx.FRAME_COUNT and (not self._frame_native or pygame.time.get_ticks() - start < 10):
                    self._frame_native.append(frame_fx.build_frame(spec["style"], w, h, len(self._frame_native)).surf)
            except Exception as error:                              # a broken frame must never break the game
                from ..engine.logs import log_error
                log_error(f"frame {spec['style']}: {error}")
                self.assets.theme_frame = None
                return
        index = int(pygame.time.get_ticks() * spec["fps"] / 1000) % frame_fx.FRAME_COUNT
        index %= len(self._frame_native)                            # while the rest is still being built the first frames loop
        if self._frame_shown is None or self._frame_shown[0] != index:
            f = self._frame_native[index]
            self._frame_shown = (index, pygame.transform.scale(f, (f.get_width() * self.scale, f.get_height() * self.scale)))
        m = frame_fx.MARGIN * self.scale
        surface.blit(self._frame_shown[1], (self.origin[0] - m, self.origin[1] - m))

    def layout_from_board(self, board: Board) -> None:
        """The number of free slots changes during the game (rescue) - refresh without changing the size."""
        self.n_free = board.n_free

    def _draw_labels(self, surface, board: Board, cursor: Loc | None, selected: Loc | None) -> None:
        font = self.assets.pixel_font(self.scale)            # the same factor as the board
        rect = self.screen_rect
        for ci in range(board.n_cols):
            r = self.cell_rect(ci, self.capacity)
            active = cursor == col(ci) or selected == col(ci)
            self._label_chip(surface, config.COL_KEYS[ci], font, r.centerx, rect.bottom + LABEL_GAP, "midtop")
            draw_text(surface, config.COL_KEYS[ci], font,
                      GOLD if active else TAN,
                      (r.centerx, rect.bottom + LABEL_GAP), "midtop")
        for i in range(board.n_free):
            r = self.cell_rect(self._slot_grid_col(i), 0)
            active = cursor == slot(i) or selected == slot(i)
            self._label_chip(surface, config.FREE_KEYS[i], font, r.centerx, rect.top - LABEL_GAP, "midbottom")
            draw_text(surface, config.FREE_KEYS[i], font,
                      GOLD if active else TAN,
                      (r.centerx, rect.top - LABEL_GAP), "midbottom")

    def _label_chip(self, surface, text, font, x, y, anchor) -> None:
        """A dark plate behind a key label so it stays readable on top of a frame's animation."""
        if not self.assets.theme_frame:
            return
        w, h = font.size(text) if hasattr(font, "size") else (len(text) * 6 * self.scale, LABEL_HEIGHT * self.scale)
        pad = self.scale
        rect = pygame.Rect(0, 0, w + 4 * pad, h + 2 * pad)
        rect.midtop = (x, y - pad) if anchor == "midtop" else (x, y - rect.height + pad)
        chip = pygame.Surface(rect.size, pygame.SRCALPHA)
        chip.fill((14, 13, 24, 205))
        surface.blit(chip, rect)

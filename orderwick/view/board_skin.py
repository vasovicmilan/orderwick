"""Assembles the board image from the `board.png` asset (10 lanes x 12 rows, 193 x 217 px).

The asset has: a 3 px outer frame, a row of free slots (16 px), a 3 px gap, then lanes (16 px wide,
12 x 16 px tall) separated by 3 px gaps. All lanes and slots are identical, so a board of another
size is built by repeating lanes (width) and shortening a lane (height). When shortening, the
four top and four bottom rows of the lane stay untouched, and the middle part (the gradient) is squeezed so that
the alternating (checkered) dashed edge is preserved.
"""
from __future__ import annotations

import pygame

CELL = 16
BORDER = 3          # spoljni okvir
GAP = 3             # gap between lanes and between the free-slot row and the lanes
PITCH = CELL + GAP  # 19: step between lanes
LANE_TOP = BORDER + CELL + GAP   # 22: where the lane starts (y)
SRC_ROWS = 12       # broj redova u originalnom assetu
SRC_COLS = 10       # broj traka u originalnom assetu
CAP = 4             # top/bottom lane rows that are not touched


class BoardSkin:
    def __init__(self, image: pygame.Surface):
        self.image = image
        self._cache: dict[tuple[int, int], pygame.Surface] = {}
        self.src_lane_h = SRC_ROWS * CELL
        expected_h = LANE_TOP + self.src_lane_h + BORDER
        if image.get_height() != expected_h:
            raise ValueError(f"board.png treba da bude visine {expected_h}, a jeste {image.get_height()}")

    # ---- geometrija (u pikselima asseta, pre uvecanja) ---------------------------------
    @staticmethod
    def native_size(n_cols: int, k: int) -> tuple[int, int]:
        return PITCH * n_cols + BORDER, LANE_TOP + CELL * k + BORDER

    @staticmethod
    def slot_pos(c: int) -> tuple[int, int]:
        return BORDER + PITCH * c, BORDER

    @staticmethod
    def card_pos(c: int, j: int, k: int) -> tuple[int, int]:
        """j = 0 is the bottom card of column c; columns are k cards tall."""
        return BORDER + PITCH * c, LANE_TOP + CELL * (k - 1 - j)

    @staticmethod
    def row_pos(c: int, r: int) -> tuple[int, int]:
        """r = 0 is the free-slot row, r = 1..k are the card rows from top to bottom."""
        if r == 0:
            return BORDER + PITCH * c, BORDER
        return BORDER + PITCH * c, LANE_TOP + CELL * (r - 1)

    # ---- sklapanje -------------------------------------------------------------------------
    def build(self, n_cols: int, k: int) -> pygame.Surface:
        key = (n_cols, k)
        surf = self._cache.get(key)
        if surf is None:
            surf = self._cache[key] = self._build(n_cols, k)
        return surf

    def _src_row(self, r: int, h: int) -> int:
        """Which row of the original lane goes into row r of the new lane of height h."""
        src_h = self.src_lane_h
        if r < CAP:
            return r
        if r >= h - CAP:
            return src_h - (h - r)
        span_new, span_old = h - 2 * CAP, src_h - 2 * CAP
        s = CAP + round((r - CAP) * (span_old - 1) / max(1, span_new - 1))
        if (s - r) % 2:                                  # sacuvaj naizmenicnost isprekidanog ruba
            s += 1 if s + 1 < src_h - CAP else -1
        return s

    def _build(self, n: int, k: int) -> pygame.Surface:
        w, h_total = self.native_size(n, k)
        src = self.image
        full_h = src.get_height()
        # 1) horizontal: left frame + n lanes (with gaps) + right frame, at the full original height.
        #    Every lane is taken from the SAME place in the source (there are 10), because the small checkered pattern at the bottom
        #    depends on the parity of the x position, and the 19 px step is odd.
        if n > SRC_COLS:
            raise ValueError(f"asset board.png ima {SRC_COLS} traka, a trazeno je {n}")
        wide = pygame.Surface((w, full_h), pygame.SRCALPHA)
        wide.blit(src, (0, 0), pygame.Rect(0, 0, BORDER, full_h))
        for i in range(n):
            x = BORDER + PITCH * i
            wide.blit(src, (x, 0), pygame.Rect(x, 0, CELL + (GAP if i < n - 1 else 0), full_h))
        right_src_x = src.get_width() - BORDER
        wide.blit(src, (w - BORDER, 0), pygame.Rect(right_src_x, 0, BORDER, full_h))
        for x in range(w - BORDER, w):                    # parnost sahovskog uzorka u poslednja dva reda
            for y in (LANE_TOP + self.src_lane_h - 1, LANE_TOP + self.src_lane_h):
                wide.set_at((x, y), src.get_at((x % 2, y)))
        # 2) vertical: the top part (frame + free slots) stays, the lane is shortened, the bottom frame stays
        out = pygame.Surface((w, h_total), pygame.SRCALPHA)
        out.blit(wide, (0, 0), pygame.Rect(0, 0, w, LANE_TOP))
        lane_h = CELL * k
        for r in range(lane_h):
            sy = LANE_TOP + self._src_row(r, lane_h)
            out.blit(wide, (0, LANE_TOP + r), pygame.Rect(0, sy, w, 1))
        out.blit(wide, (0, LANE_TOP + lane_h), pygame.Rect(0, LANE_TOP + self.src_lane_h, w, BORDER))
        return out

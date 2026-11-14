"""Slow, quiet life inside the lanes of a board theme that has an animated frame (frame.json).

The decoration painted into the lanes (lava cracks and sparks, moss and spores, electric rungs) is found in the board
picture itself (pixels that differ from the lane gradient) and re-coloured frame by frame; a few extra pixels (rising
embers, a bolt of lightning) are added on top. Everything repeats every LOOP frames and something noticeable happens only
once per loop (a surge of heat, a breeze, a flash), so it stays calm. The overlay is drawn between the board and the cards.
"""
from __future__ import annotations

import math
from collections import Counter

import pygame

from .board_skin import BORDER, CELL, LANE_TOP, PITCH
from .frame_fx import TAU, draw_gear, teeth_for

LOOP = 48                                   # frames per loop (at 10 fps: about 5 seconds)


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


def _lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def _hash01(*key) -> float:
    h = 2166136261
    for k in key:
        h = ((h ^ (int(k) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
        h ^= h >> 15
    return (h % 100003) / 100003.0


def find_decoration(base: pygame.Surface) -> tuple[list[tuple], int, int]:
    """[(x, y, colour, lane gradient colour at that row, phase, brighter)] for every lane pixel that is not plain gradient, plus (n lanes, k rows)."""
    w, h = base.get_size()
    n = (w - BORDER) // PITCH
    k = (h - LANE_TOP - BORDER) // CELL
    top, bottom = LANE_TOP, LANE_TOP + CELL * k
    modal = {}
    for y in range(top, bottom):
        counts = Counter(tuple(base.get_at((BORDER + PITCH * c + dx, y)))[:3] for c in range(n) for dx in range(3, 13))
        modal[y] = counts.most_common(1)[0][0]
    out = []
    for c in range(n):
        x0 = BORDER + PITCH * c
        for y in range(top + 2, bottom - 2):
            for dx in range(CELL):
                colour = tuple(base.get_at((x0 + dx, y)))[:3]
                if abs(_lum(colour) - _lum(modal[y])) > 14:
                    out.append((x0 + dx, y, colour, modal[y], _hash01(x0 + dx, y), _lum(colour) > _lum(modal[y])))
    return out, n, k


def _recolour(style, colour, grad, x, phase, brighter, t01, depth):
    """The colour of one decoration pixel at time t01 (0..1); depth = 0 at the top of the lane, 1 at the bottom."""
    if style == "flames":
        flick = 0.5 + 0.5 * math.sin(2 * math.pi * (t01 * 3 + phase))
        out = _mix(colour, (255, 214, 96), 0.22 * flick) if brighter else _mix(colour, grad, 0.25 * flick)
        front = 1.12 - t01 * 1.45                                           # the surge runs from the bottom to the top once per loop
        glow = math.exp(-((depth - front) ** 2) / 0.012)
        return _mix(out, (255, 240, 168), 0.7 * glow) if brighter else _mix(out, (160, 70, 40), 0.4 * glow)
    if style == "vines":
        if brighter:
            glow = max(0.0, math.sin(2 * math.pi * (t01 * 2 + phase))) ** 8       # specks glow like fireflies, each at its own time
            return _mix(colour, (238, 255, 160), 0.85 * glow)
        breeze = 0.5 + 0.5 * math.sin(2 * math.pi * (t01 - x / 90.0))             # dark strokes sway with a breeze going along the board
        return _mix(colour, grad, 0.4 * breeze)
    if style == "storm":
        flash = 0.0
        for centre, width in ((0.0, 0.035), (0.09, 0.03)):                       # a double flash once per loop
            d = min(abs(t01 - centre), 1 - abs(t01 - centre))
            flash = max(flash, math.exp(-(d * d) / (width * width)))
        hum = 0.5 + 0.5 * math.sin(2 * math.pi * (t01 * 2 + phase))
        out = _mix(colour, (170, 224, 255), 0.18 * hum) if brighter else _mix(colour, grad, 0.2 * hum)
        return _mix(out, (226, 242, 255), 0.6 * flash) if brighter else _mix(out, (60, 90, 170), 0.4 * flash)
    lane = max(0, (x - BORDER) // PITCH)
    if style == "gears":                                                       # a brass glint sweeps down the lanes, lane after lane
        front = t01 * 1.5 - 0.25 - lane * 0.045
        glow = math.exp(-((depth - front) ** 2) / 0.006)
        return _mix(colour, (255, 240, 190), 0.75 * glow) if brighter else _mix(colour, grad, 0.25 * glow)
    if style == "neon":                                                        # data pulses run down the lanes, pink in odd lanes and cyan in even ones
        front = ((t01 + _hash01(lane, 3)) % 1.0) * 1.5 - 0.2
        d = depth - front
        hot = (0, 236, 255) if lane % 2 == 0 else (255, 70, 190)
        if brighter:
            k = 1.0 if abs(d) < 0.02 else max(0.0, 1 + d / 0.3) if d < 0 else 0.0
            return _mix(colour, (236, 255, 255) if abs(d) < 0.02 else hot, 0.85 * k)
        return _mix(colour, grad, 0.3 * (0.5 + 0.5 * math.sin(2 * math.pi * (t01 * 2 + phase))))
    if style == "matrix":                                                      # rain: a bright head falls through the code of every lane
        k = 1 + (lane % 2)
        front = ((t01 * k + _hash01(lane, 4)) % 1.0) * 1.5 - 0.2
        d = front - depth                                                      # > 0: below the head's trail start (already passed)
        if brighter:
            if 0 <= d < 0.03:
                return (214, 255, 224)
            if 0.03 <= d < 0.4:
                return _mix(colour, (70, 255, 120), 0.9 * (1 - d / 0.4))
            return _mix(colour, grad, 0.3)
        return colour
    if style in ("frost", "christmas", "easter"):
        glow = max(0.0, math.sin(2 * math.pi * (t01 * 2 + phase))) ** 8        # every speck twinkles at its own time
        if style == "frost":
            if brighter:
                return _mix(colour, (255, 255, 255), 0.9 * glow)
            shimmer = 0.5 + 0.5 * math.sin(2 * math.pi * (t01 - depth * 0.6 - x / 140.0))      # a cold shimmer sweeps along
            return _mix(colour, grad, 0.35 * shimmer)
        if style == "christmas":
            if brighter:
                return _mix(colour, (255, 252, 214), 0.85 * glow)
            return _mix(colour, grad, 0.2 * glow)
        if brighter:                                                           # easter: flowers nod in a spring breeze
            breeze = max(0.0, math.sin(2 * math.pi * (t01 - x / 100.0))) ** 4
            return _mix(colour, (255, 255, 236), 0.6 * breeze)
        return colour
    return colour


def _snow(overlay, n, top, bottom, t01, count, colours):
    height = bottom - top
    for c in range(n):
        x0 = BORDER + PITCH * c
        for j in range(count):
            seed = _hash01(c, j, 41)
            u = (t01 + seed) % 1.0                                              # falls from the top (0) to the bottom (1)
            y = top + 3 + round(u * (height - 8))
            x = x0 + 3 + int(_hash01(c, j, 42) * 10) + round(1.5 * math.sin(2 * math.pi * (t01 + seed)))
            if 0.04 < u < 0.96:
                overlay.set_at((x, y), colours[(c + j) % len(colours)] + (255,))


def _extras(style, overlay, n, k, f):
    t01 = f / LOOP
    top, bottom = LANE_TOP, LANE_TOP + CELL * k
    height = bottom - top
    if style == "flames":                                                       # embers rising along the lanes
        for c in range(n):
            x0 = BORDER + PITCH * c
            for j in range(2):
                seed = _hash01(c, j, 7)
                u = (t01 + seed) % 1.0                                         # 0 at the bottom .. 1 at the top
                y = bottom - 3 - round(u * (height - 8))
                x = x0 + 3 + int(_hash01(c, j, 3) * 10) + round(1.6 * math.sin(2 * math.pi * (t01 * 2 + seed)))
                if u < 0.08 or u > 0.92:
                    continue
                colour = (255, 226, 110) if u < 0.45 else (255, 150, 50) if u < 0.75 else (190, 70, 40)
                overlay.set_at((x, y), colour + (255,))
    elif style == "vines":                                                      # spores drifting up
        for c in range(n):
            x0 = BORDER + PITCH * c
            seed = _hash01(c, 11)
            u = (t01 + seed) % 1.0
            y = bottom - 3 - round(u * (height - 8))
            x = x0 + 3 + int(_hash01(c, 5) * 10) + round(2 * math.sin(2 * math.pi * (t01 + seed)))
            if 0.05 < u < 0.95:
                overlay.set_at((x, y), (214, 244, 140, 255) if u < 0.6 else (150, 200, 100, 255))
    elif style == "storm":                                                      # one bolt in one lane, a few frames per loop
        if f in (0, 1, 2, 4, 5):
            lane = 1 + int(_hash01(n, k, 9) * max(1, n - 2))
            x0 = BORDER + PITCH * lane
            x = x0 + 8
            for y in range(top + 1, top + int(height * 0.72)):
                x += (-1, 0, 0, 1)[int(_hash01(lane, y, f // 3) * 4)]
                x = max(x0 + 3, min(x0 + 12, x))
                overlay.set_at((x, y), (255, 255, 214, 255) if f != 5 else (150, 220, 255, 255))
                for gx in (x - 1, x + 1):
                    if overlay.get_at((gx, y))[3] == 0:
                        overlay.set_at((gx, y), (120, 190, 255, 200))


    elif style == "gears":                                                      # a few small cogs turning slowly in the lanes
        for c in range(n):
            if _hash01(c, 21) > 0.55:
                continue
            cx = BORDER + PITCH * c + 8.0
            cy = top + height * (0.2 + 0.6 * _hash01(c, 22))
            rot = (1 if c % 2 else -1) * TAU / 8 * t01 + _hash01(c, 23) * TAU
            pal = [(212, 164, 92), (170, 120, 62), (128, 84, 44), (88, 56, 32), (52, 34, 24)]
            draw_gear(lambda x, y, col: overlay.set_at((x, y), col + (200,)), cx, cy, 4.5, teeth_for(4.5), rot, pal)
    elif style == "neon":                                                       # a scan line down the board and a glitch in one lane
        sy = top + int(height * ((t01 * 1.2) % 1.0))
        for c in range(n):
            x0 = BORDER + PITCH * c
            for dx in range(CELL):
                overlay.set_at((x0 + dx, sy), (120, 240, 255, 70))
        if f in (30, 31, 32):
            lane = int(_hash01(f // 3, n, 5) * n)
            x0 = BORDER + PITCH * lane
            gy = top + int(height * (0.2 + 0.6 * _hash01(lane, 6)))
            off = (-2, 2, 0)[f - 30]
            for dx in range(CELL):
                xx = x0 + (dx + off) % CELL
                overlay.set_at((xx, gy), (255, 60, 180, 230))
                overlay.set_at((x0 + dx, gy + 1), (0, 236, 255, 200))
    elif style == "frost":                                                      # snow falling through the lanes
        _snow(overlay, n, top, bottom, t01, 2, [(255, 255, 255), (206, 236, 255)])
    elif style == "christmas":                                                  # snow and one gold sparkle per loop
        _snow(overlay, n, top, bottom, t01, 1, [(255, 255, 255), (255, 244, 200)])
        if f < 6:
            lane = int(_hash01(n, k, 77) * n)
            cx, cy = BORDER + PITCH * lane + 8, top + int(height * 0.3)
            arm = (0, 1, 2, 2, 1, 0)[f]
            for i in range(arm + 1):
                for dx, dy in ((i, 0), (-i, 0), (0, i), (0, -i)):
                    overlay.set_at((cx + dx, cy + dy), (255, 236, 130, 255) if i else (255, 255, 240, 255))
    elif style == "easter":                                                     # petals drift down, two butterflies flutter up the lanes
        _snow(overlay, n, top, bottom, t01, 1, [(255, 190, 214), (255, 255, 240)])
        for j, (col, lane_seed) in enumerate(((  (255, 214, 80), 1), ((255, 140, 190), 2))):
            lane = int(_hash01(n, k, 90 + j) * n)
            u = (t01 * 1 + j * 0.5) % 1.0
            y = bottom - 4 - round(u * (height - 10))
            x = BORDER + PITCH * lane + 8 + round(4 * math.sin(2 * math.pi * (t01 * 3 + j * 0.3)))
            if 0.05 < u < 0.95:
                overlay.set_at((x, y), (60, 40, 60, 255))
                wings = ((-1, 0), (1, 0), (-2, -1), (2, -1)) if (f // 2) % 2 == 0 else ((-1, 0), (1, 0))
                for (a, b) in wings:
                    overlay.set_at((x + a, y + b), col + (255,))
    elif style == "matrix":                                                     # the falling head itself, so the rain shows even where the lane has no code
        for c in range(n):
            x0 = BORDER + PITCH * c
            k = 1 + (c % 2)
            front = ((t01 * k + _hash01(c, 4)) % 1.0) * 1.5 - 0.2
            y = top + int(front * height)
            xs = x0 + 2 + int(_hash01(c, 31) * 9)
            for j in range(0, 7):
                yy = y - j * 2
                if top < yy < top + height:
                    col = (214, 255, 224, 255) if j == 0 else (70, 255, 120, 255 - j * 34)
                    for dx in range(3):
                        if _hash01(c, j, dx, f // 4) > 0.25:
                            overlay.set_at((xs + dx, yy), col)


class LaneFx:
    """The overlays of one board picture, built a few at a time (a whole loop at once would stall the game for a moment)."""

    def __init__(self, style: str, base: pygame.Surface):
        self.style, self.size = style, base.get_size()
        self.deco, self.n, self.k = find_decoration(base)
        self.frames: list[pygame.Surface] = []

    @property
    def complete(self) -> bool:
        return len(self.frames) >= LOOP

    def build_next(self) -> None:
        f = len(self.frames)
        overlay = pygame.Surface(self.size, pygame.SRCALPHA)
        t01 = f / LOOP
        top, height = LANE_TOP, CELL * self.k
        style = self.style
        for x, y, colour, grad, phase, brighter in self.deco:
            overlay.set_at((x, y), _recolour(style, colour, grad, x, phase, brighter, t01, (y - top) / height) + (255,))
        _extras(style, overlay, self.n, self.k, f)
        self.frames.append(overlay)


def build_overlays(style: str, base: pygame.Surface) -> list[pygame.Surface]:
    """All LOOP transparent overlays (the size of the board) for the given frame style."""
    fx = LaneFx(style, base)
    while not fx.complete:
        fx.build_next()
    return fx.frames

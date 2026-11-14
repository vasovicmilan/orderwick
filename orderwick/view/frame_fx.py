"""Animated decorative frames around the board (flames / vines / storm), generated for any board size.

A board theme may contain `frame.json` ({"style": "flames" | "vines" | "storm", "fps": 10}); the game then draws the
animated frame around the board. The art is generated in code (no per-size image files), so it fits every board size.
Layout: a 4 px rim touches the board, 24 px of animation around it (MARGIN = 28 px on every side), 8 frames.
"""
from __future__ import annotations

import math
import random

import pygame

MARGIN = 28
M = MARGIN
RIM, FX, P, N, CORN = 4, 24, 48, 8, 7
STYLES = ("flames", "vines", "storm")
FRAME_COUNT = N


class _Px:
    """img.load()-like pixel access on a pygame surface."""
    def __init__(self, surf: pygame.Surface):
        self.surf = surf

    def __setitem__(self, pos, color):
        self.surf.set_at(pos, color)

    def __getitem__(self, pos):
        return tuple(self.surf.get_at(pos))


class _Img:
    def __init__(self, w, h):
        self.surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self.size = (w, h)

    def load(self):
        return _Px(self.surf)


# ---------------------------------------------------------------- helpers
def wrapd(a, b, period=P):
    d = (a - b) % period
    return d - period if d > period / 2 else d


class Local:
    """Edge canvas: u along the edge (from -M to long), v outward (0..FX-1)."""
    def __init__(self, ulen):
        self.u0 = -M
        self.w, self.h = ulen + M, FX
        self.px = {}

    def put(self, u, v, c, over=True):
        if 0 <= v < FX and self.u0 <= u < self.u0 + self.w:
            if over or (u, v) not in self.px:
                self.px[(u, v)] = c


# ---------------------------------------------------------------- EMBER
FLAME = [(255, 247, 200), (255, 218, 88), (255, 158, 40), (232, 88, 30), (168, 40, 36), (92, 26, 44)]
TONGUES = [(7, 6, 21, 0.0), (17, 4, 12, 1.7), (25, 6, 23, 3.1), (35, 4, 14, 4.4), (42, 5, 18, 5.6)]


def ember_edge(t, ulen, lean=0.0, blen=10**6):
    L = Local(ulen)
    ph_t = 2 * math.pi * t / N
    for u in range(L.u0, L.u0 + L.w):
        for v in range(FX):
            best = None
            for c, bw, ln, ph in TONGUES:
                taper = max(0.0, min(1.0, (min(u, blen - 1 - u) + 1) / 20.0))
                l = ln * (0.88 + 0.12 * math.sin(ph_t + ph)) * taper
                if l < 2:
                    continue
                h = v / l
                if h >= 1:
                    continue
                sway = 3.0 * math.sin(ph_t + ph * 1.3) * h ** 1.4 + lean * h ** 1.2
                du = wrapd(u, c) - sway
                w = bw * (1 - h) ** 0.75 + 0.5
                if abs(du) <= w:
                    d = 0.55 * h + 0.55 * abs(du) / (w + 0.01)
                    if best is None or d < best:
                        best = d
            if best is not None:
                idx = 0 if best < .16 else 1 if best < .34 else 2 if best < .55 else 3 if best < .74 else 4 if best < .92 else 5
                L.put(u, v, FLAME[idx] + (255,))
            elif v <= 1:
                L.put(u, v, (150, 36, 34, 255) if v == 0 else (104, 28, 40, 255))
    # sparks: loop exactly every N frames
    sparks = [(8, 4), (19, 10), (29, 2), (38, 8), (45, 13), (13, 12)]
    for i, (su, sv) in enumerate(sparks):
        v = (sv + 2 * t) % FX
        u = su + round(1.5 * math.sin(ph_t + i * 1.3))
        if v < 6:
            continue
        col = FLAME[1] if v < 11 else FLAME[2] if v < 14 else FLAME[3]
        for rep in range(-1, ulen // P + 2):
            if (u + rep * P, v) not in L.px:
                L.put(u + rep * P, v, col + (255,))
    return L


RIM_EMBER = [(30, 24, 36), (66, 58, 76), (98, 88, 108), (30, 24, 36)]   # outer ... next to the board


def ember_rim(img, W, H, t):
    ph_t = 2 * math.pi * t / N
    draw_ring(img, W, H, RIM_EMBER)
    # glowing cracks in the rim
    for side in range(4):
        for u in range(0, 400):
            if (u * 7 + side * 3) % 13 == 0:
                glow = 0.5 + 0.5 * math.sin(ph_t + u * 0.7)
                col = (255, 150, 44) if glow > .55 else (214, 84, 34) if glow > .2 else (130, 40, 36)
                ring_set(img, W, H, side, u, 1 + (u // 13) % 2, col)


# ---------------------------------------------------------------- WILDWOOD
RIM_WOOD = [(36, 24, 22), (84, 58, 40), (122, 88, 54), (40, 28, 24)]


def wood_edge(t, ulen, lean=0.0, blen=10**6):
    L = Local(ulen)
    L.stem = set()
    ph_t = 2 * math.pi * t / N
    STEM, STEM_HI, STEM_DK = (52, 98, 52, 255), (96, 160, 72, 255), (34, 70, 44, 255)
    LEAF, LEAF_HI, LEAF_DK = (62, 150, 64, 255), (118, 200, 88, 255), (34, 98, 50, 255)

    def vs_at(u):
        return 3 + round(2.0 * math.sin(2 * math.pi * u / 24))

    def leaf(o, lu, base_v, ln, sw, width):
        for dv in range(0, ln):
            h = dv / ln
            half = round(width * math.sin(math.pi * min(1.0, 0.25 + h * 0.85)) ** 0.9)
            if dv == ln - 1:
                half = 0
            shift = round(sw * h * 1.6)
            for du in range(-half, half + 1):
                c = LEAF_HI if du < 0 else LEAF
                if du == 0 and 0 < dv < ln - 1:
                    c = LEAF_DK
                L.put(o + lu + du + shift, base_v + dv, c)

    for rep in range(-1, ulen // P + 2):
        o = rep * P
        for u in range(P):
            vs = vs_at(u)
            for dv, c in ((-1, STEM_DK), (0, STEM), (1, STEM_HI), (2, STEM)):
                L.put(o + u, vs + dv, c)
                L.stem.add((o + u, vs + dv))
        # big leaves on both layers
        for i, lu in enumerate([3, 12, 22, 31, 40]):
            vs = vs_at(lu)
            sw = math.sin(ph_t + i * 1.1)
            ln = 8 + (i % 3) * 2
            leaf(o, lu, vs + 2, ln, sw, 2)
        # long hanging tendrils with leaves along them
        for tu, tl, ph in [(6, 22, 0.4), (19, 15, 1.3), (31, 21, 2.2), (43, 16, 3.5)]:
            vs = vs_at(tu)
            path = []
            for v in range(vs + 2, tl):
                du = round(2.2 * math.sin(ph_t + v * 0.5 + ph) * (v - vs) / 12)
                path.append((tu + du, v))
                L.put(o + tu + du, v, STEM_HI if v % 3 else STEM)
            for k in (len(path) // 2, len(path) - 1):
                pu, pv = path[k]
                side = -1 if k % 2 else 1
                for (a_, b_) in [(0, 0), (side, 0), (side * 2, 0), (side, 1), (side * 2, 1), (side * 3, 1)]:
                    L.put(o + pu + a_, pv + b_, LEAF_HI if a_ * side < 2 else LEAF)
            pu, pv = path[-1]
            L.put(o + pu, pv + 1, (228, 70, 80, 255))        # berry on the tip
            L.put(o + pu, pv + 2, (170, 40, 60, 255))
        # flowers
        for fu, fv in [(13, 11), (37, 13)]:
            vs = vs_at(fu)
            for v in range(vs + 2, fv):
                L.put(o + fu, v, STEM)
            pet = (244, 130, 176, 255) if fu == 13 else (240, 240, 250, 255)
            for (a_, b_) in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, 2)]:
                L.put(o + fu + a_, fv + b_, pet)
            L.put(o + fu, fv, (255, 226, 90, 255) if (t + fu) % 4 < 2 else (255, 176, 60, 255))
        # fireflies
        for i, (fu, fv) in enumerate([(10, 17), (26, 19), (45, 14)]):
            u = fu + round(3 * math.sin(ph_t + i * 2.1))
            v = fv + round(1.6 * math.sin(2 * ph_t + i * 1.7))
            if math.sin(ph_t + i * 2.1 + 1) > -0.2:
                L.put(o + u, v, (236, 255, 150, 255))
                for (a_, b_) in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    L.put(o + u + a_, v + b_, (122, 176, 70, 255), over=False)
            else:
                L.put(o + u, v, (140, 190, 80, 255))
    return L


def wood_rim(img, W, H, t):
    draw_ring(img, W, H, RIM_WOOD)
    # moss on top of the rim, bark knots
    for side in range(4):
        for u in range(0, 400):
            if (u * 5 + side) % 7 in (0, 1) and (u // 7) % 2 == 0:
                ring_set(img, W, H, side, u, 2 if (u % 3) else 1, (76, 140, 62))
            if (u * 11 + side * 5) % 17 == 0:
                ring_set(img, W, H, side, u, 1, (52, 34, 30))


# ---------------------------------------------------------------- STORM (yellow + blue electricity)
Y_CORE, Y, C_BLUE, BLUE, D_BLUE = (255, 255, 214, 255), (255, 228, 78, 255), (120, 214, 255, 255), (56, 124, 238, 255), (30, 54, 150, 255)
RIM_STORM = [(16, 24, 56), (60, 84, 150), (120, 156, 220), (26, 38, 84)]


def storm_edge(t, ulen, lean=0.0, blen=10**6):
    L = Local(ulen)
    L.stem = set()
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        for k in range(2):                       # two arcs per 48 px period, studs every 24 px
            rng = random.Random(t * 97 + k * 13 + 5)
            u0, u1 = o + k * 24, o + k * 24 + 24
            v = 5
            path = []
            for u in range(u0 + 2, u1 - 1):
                target = 5
                step = rng.choice((-2, -1, -1, 0, 1, 1, 2))
                v += step + (1 if v < target - 3 else -1 if v > target + 3 else 0) * (rng.random() < 0.6)
                v = max(3, min(11, v))
                path.append((u, v))
            for (u, v) in path:                  # glow first
                for dv in (-1, 1):
                    L.put(u, v + dv, BLUE if t % 4 else C_BLUE, over=False)
            for (u, v) in path:
                L.put(u, v, Y_CORE if (u + t) % 3 else Y)
                L.put(u, v + 1, Y if (u + t) % 2 else C_BLUE)
                if (u + t) % 2 == 0:
                    L.put(u, v - 2, BLUE, over=False)
                    L.put(u, v + 3, BLUE, over=False)
            # forks reaching outward
            for _ in range(2):
                if not path:
                    break
                bu, bv = path[rng.randrange(len(path))]
                ln = rng.randint(6, 16)
                x = bu
                for j in range(1, ln):
                    x += rng.choice((-1, 0, 0, 1))
                    col = Y if j < ln * 0.4 else C_BLUE if j < ln * 0.75 else BLUE
                    L.put(x, bv + j, col)
                    if j % 2 == 0:
                        L.put(x - 1, bv + j, D_BLUE, over=False)
        # energy rail along the rim
        for u in range(P):
            L.put(o + u, 0, C_BLUE if (u + t * 6) % 12 < 4 else BLUE, over=False)
            L.put(o + u, 1, D_BLUE, over=False)
        # studs (always the same)
        for su in (o, o + 24):
            for du in (-1, 0, 1):
                for dv in (3, 4, 5, 6):
                    L.put(su + du, dv - 0, (150, 170, 210, 255) if dv == 3 else (70, 90, 140, 255) if dv < 6 else (30, 40, 80, 255))
            L.put(su, 4, Y if t % 2 == 0 else Y_CORE)
            for (a_, b_) in [(-2, 4), (2, 4), (0, 7), (0, 2)]:
                L.put(su + a_, b_, BLUE if (t + su) % 3 else C_BLUE, over=False)
        # a few loose sparks
        rng = random.Random(t * 31 + 7)
        for _ in range(3):
            L.put(o + rng.randrange(P), rng.randint(9, 20), Y if rng.random() < .6 else C_BLUE, over=False)
    return L


def storm_corner(t):
    px = {}
    cx = cy = 11
    ph_t = 2 * math.pi * t / N
    for a in range(FX + RIM):
        for b in range(FX + RIM):
            d = math.hypot(a - cx, b - cy)
            if d <= 3.3:
                px[(a, b)] = Y_CORE if d < 1.8 else Y
            elif d <= 6.2:
                px[(a, b)] = C_BLUE if d < 4.3 else BLUE if d < 5.3 else D_BLUE
    # glow ring
    for a in range(FX + RIM):
        for b in range(FX + RIM):
            d = math.hypot(a - cx, b - cy)
            if 6.2 < d <= 7.6 and (a + b + t) % 2 == 0:
                px[(a, b)] = BLUE
    rng = random.Random(t * 53 + 11)
    for i in range(6):
        ang = math.radians(20 + i * 62 + rng.randint(-14, 14))
        x, y = cx + 6 * math.cos(ang), cy + 6 * math.sin(ang)
        ln = rng.randint(8, 16)
        for j in range(ln):
            x += math.cos(ang) + rng.choice((-0.6, 0, 0.6)) * -math.sin(ang)
            y += math.sin(ang) + rng.choice((-0.6, 0, 0.6)) * math.cos(ang)
            a, b = round(x), round(y)
            if 0 <= a < FX + RIM and 0 <= b < FX + RIM:
                px[(a, b)] = Y_CORE if j < 3 else Y if j < ln * 0.5 else C_BLUE
    return px


def storm_rim(img, W, H, t):
    draw_ring(img, W, H, RIM_STORM)
    for side in range(4):
        for u in range(0, 500):
            if u % 24 in (8, 16):                # rivets
                ring_set(img, W, H, side, u, 2, (230, 214, 120))
            run = (u - t * 6) % P
            if run in (0, 1, 2):                 # running light
                ring_set(img, W, H, side, u, 1, Y_CORE[:3] if run == 1 else Y[:3])
                ring_set(img, W, H, side, u, 2, (150, 220, 255))


# ---------------------------------------------------------------- ring + compose
def draw_ring(img, W, H, cols):
    """Rim ring: layers 0..3 from the outside to the board; the board occupies [M, M+Wb) x [M, M+Hb)."""
    px = img.load()
    for k, c in enumerate(cols):
        x0, y0, x1, y1 = M - RIM + k, M - RIM + k, W - (M - RIM + k) - 1, H - (M - RIM + k) - 1
        for x in range(x0, x1 + 1):
            px[x, y0] = c + (255,); px[x, y1] = c + (255,)
        for y in range(y0, y1 + 1):
            px[x0, y] = c + (255,); px[x1, y] = c + (255,)
    for (x, y) in [(M - RIM, M - RIM), (W - M + RIM - 1, M - RIM), (M - RIM, H - M + RIM - 1), (W - M + RIM - 1, H - M + RIM - 1)]:
        px[x, y] = (0, 0, 0, 0)


def ring_set(img, W, H, side, u, k, col):
    """side 0=top 1=right 2=bottom 3=left; u along the edge, k = layer (0 outside .. 3 next to the board)."""
    px = img.load()
    kk = RIM - 1 - k if False else k
    if side == 0: x, y = M + u, M - RIM + kk
    elif side == 2: x, y = M + u, H - M + RIM - 1 - kk
    elif side == 3: x, y = M - RIM + kk, M + u
    else: x, y = W - M + RIM - 1 - kk, M + u
    if M <= (x if side in (0, 2) else y) < (W - M if side in (0, 2) else H - M) and 0 <= x < W and 0 <= y < H:
        px[x, y] = col + (255,)


def ember_corner(t):
    px = {}
    ph_t = 2 * math.pi * t / N
    fan = [(0.0, 6.5, 31.0, 0.0), (-9.0, 4.5, 19.0, 1.8), (9.0, 4.5, 21.0, 3.6), (-17.0, 3.0, 11.0, 5.0), (17.0, 3.0, 12.0, 0.9)]
    for a in range(FX + RIM):
        for b in range(FX + RIM):
            r = (a + b) / 1.4142 - 1
            lat = (a - b) / 1.4142
            best = None
            for lc, bw, R, ph in fan:
                rr = r - abs(lc) * 0.35
                h = rr / (R * (0.9 + 0.1 * math.sin(ph_t + ph)))
                if h >= 1 or rr < 0:
                    continue
                sway = 2.8 * math.sin(ph_t + ph * 1.3) * h ** 1.4
                w = bw * (1 - h) ** 0.75 + 0.5
                du = lat - lc - sway
                if abs(du) <= w:
                    d = 0.55 * h + 0.55 * abs(du) / (w + 0.01)
                    if best is None or d < best:
                        best = d
            if best is not None:
                idx = 0 if best < .16 else 1 if best < .34 else 2 if best < .55 else 3 if best < .74 else 4 if best < .92 else 5
                px[(a, b)] = FLAME[idx] + (255,)
    for i, (sa, sb) in enumerate([(6, 20), (20, 6), (12, 12)]):
        k = (2 * t + i * 5) % 16
        a, b = sa + k // 2, sb + k // 2 + (i % 2)
        if (a, b) not in px and a < FX + RIM and b < FX + RIM and k > 4:
            px[(a, b)] = (FLAME[1] if k < 10 else FLAME[3]) + (255,)
    return px


def wood_corner(t):
    px = {}
    ph_t = 2 * math.pi * t / N
    LEAF, HI, DK = (62, 150, 64, 255), (118, 200, 88, 255), (34, 98, 50, 255)
    # a fan of five leaves around a big flower
    for i, ang in enumerate([-70, -35, 0, 35, 70]):
        a0 = math.radians(45 + ang + 6 * math.sin(ph_t + i * 1.2))
        ln = 17 if i in (1, 2, 3) else 12
        for s in range(2, ln):
            h = s / ln
            wd = 3.2 * math.sin(math.pi * min(1, h * 1.15)) ** 0.8
            cx, cy = s * math.cos(a0), s * math.sin(a0)
            nx, ny = -math.sin(a0), math.cos(a0)
            for q in range(-4, 5):
                if abs(q) <= wd:
                    xx, yy = round(cx + q * nx) + 4, round(cy + q * ny) + 4
                    if xx >= 0 and yy >= 0:
                        px[(xx, yy)] = DK if q == 0 else HI if q < 0 else LEAF
    petals = (244, 130, 176, 255)
    for (a, b) in [(3, 3), (7, 3), (3, 7), (7, 7), (5, 2), (2, 5), (8, 5), (5, 8), (5, 5)]:
        px[(a, b)] = petals
    for (a, b) in [(4, 4), (5, 4), (6, 4), (4, 5), (5, 5), (6, 5), (4, 6), (5, 6), (6, 6)]:
        px[(a, b)] = (255, 226, 90, 255) if (t // 2) % 2 == 0 else (255, 190, 70, 255)
    return px


def build_frame(theme, Wb, Hb, t):
    W, H = Wb + 2 * M, Hb + 2 * M
    img = _Img(W, H)
    edge = {"flames": ember_edge, "vines": wood_edge, "storm": storm_edge}[theme]
    corner = {"flames": ember_corner, "vines": wood_corner, "storm": storm_corner}[theme]
    rim = {"flames": ember_rim, "vines": wood_rim, "storm": storm_rim}[theme]
    long_u = max(Wb, Hb) + 2 * M
    px = img.load()
    lean = -3.0 if theme == "flames" else 0.0

    def paint(L, mapper, length):
        stem = getattr(L, "stem", ())
        cm = 0 if theme == "flames" else CORN
        for (u, v), c in L.px.items():
            if (u, v) in stem:
                if u < -4 or u >= length + 4:
                    continue
            elif u < cm or u >= length - cm:
                continue
            x, y = mapper(u, v)
            if 0 <= x < W and 0 <= y < H:
                px[x, y] = c

    ew = lambda lean_, blen: edge(t, long_u, lean_, blen)
    paint(ew(0.0, Wb), lambda u, v: (M + u, M - RIM - 1 - v), Wb)            # top
    paint(ew(lean, Hb), lambda u, v: (M - RIM - 1 - v, M + u), Hb)           # left
    paint(ew(lean, Hb), lambda u, v: (W - M + RIM + v, M + u), Hb)           # right
    paint(ew(0.0, Wb), lambda u, v: (M + u, H - M + RIM + v), Wb)            # bottom
    cp = corner(t)
    for (a, b), c in cp.items():
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = (W - M + RIM + a) if sx else (M - RIM - 1 - a)
            y = (H - M + RIM + b) if sy else (M - RIM - 1 - b)
            if 0 <= x < W and 0 <= y < H:
                px[x, y] = c
    for y in range(M, H - M):                    # keep the board hole clear
        for x in range(M, W - M):
            px[x, y] = (0, 0, 0, 0)
    rim(img, W, H, t)
    return img




def build_frames(style: str, board_w: int, board_h: int) -> list[pygame.Surface]:
    """The animation frames (each (board_w + 2 MARGIN) x (board_h + 2 MARGIN), transparent hole for the board)."""
    if style not in STYLES:
        raise ValueError(f"unknown frame style {style!r}")
    return [build_frame(style, board_w, board_h, t).surf for t in range(FRAME_COUNT)]

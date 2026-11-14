"""Animated decorative frames around the board (flames / vines / storm / gears / neon / matrix), generated for any board size.

A board theme may contain `frame.json` ({"style": "flames" | "vines" | "storm" | "gears" | "neon" | "matrix", "fps": 10}); the game then draws the
animated frame around the board. The art is generated in code (no per-size image files), so it fits every board size.
Layout: a 4 px rim touches the board, 24 px of animation around it (MARGIN = 28 px on every side), 32 frames.
No two stretches of an edge look the same: every 48 px copy of the pattern is varied (lengths, phases, colours) by a
small hash of its position, and every side of the frame has its own salt.
"""
from __future__ import annotations

import math
import random

import pygame

MARGIN = 28
M = MARGIN
RIM, FX, P, N, CORN = 4, 24, 48, 32, 7
STYLES = ("flames", "vines", "storm", "gears", "neon", "matrix", "frost", "christmas", "easter")
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
def vr(*key) -> float:
    """A repeatable pseudo-random number in [0, 1) from small integers (the same everywhere, in every frame)."""
    h = 2166136261
    for k in key:
        h = ((h ^ (int(k) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
        h ^= h >> 13
    return (h % 10007) / 10007.0


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


def ember_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    ph_t = 2 * math.pi * t / N
    for u in range(L.u0, L.u0 + L.w):
        swell = 1 + 0.2 * math.sin(ph_t - 2 * math.pi * u / 97 + salt * 1.7)       # a slow surge running along the edge
        taper = max(0.0, min(1.0, (min(u, blen - 1 - u) + 1) / 20.0))
        plan = []                                                                   # per tongue, worked out once per column
        for idx, (c, bw, ln, ph) in enumerate(TONGUES):
            k = round((u - c) / P)                                                 # which copy of the pattern this tongue is in
            a, b, d_, e = vr(k, idx, salt, 1), vr(k, idx, salt, 2), vr(k, idx, salt, 3), vr(k, idx, salt, 4)
            lm = (0.72 + 0.55 * a) * (1.35 if b > 0.88 else 1.0)                   # some tongues flare up, some stay low
            ph2 = ph + 6.0 * d_
            l = ln * lm * swell * (0.88 + 0.12 * math.sin(ph_t + ph2)) * taper
            if l < 2:
                continue
            plan.append((l, bw * (0.8 + 0.5 * d_), u - (c + k * P + 3.0 * (e - 0.5)), 3.0 * math.sin(ph_t + ph2 * 1.3)))
        for v in range(FX):
            best = None
            for l, bwv, rel, swing in plan:
                h = v / l
                if h >= 1:
                    continue
                sway = swing * h ** 1.4 + lean * h ** 1.2
                du = rel - sway
                w = bwv * (1 - h) ** 0.75 + 0.5
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
    for rep in range(-1, ulen // P + 2):
        for i, (su, sv) in enumerate(sparks):
            if vr(rep, i, salt, 9) < 0.3:                                           # not every copy has every spark
                continue
            v = (sv + round(2 * FX * t / N) + int(vr(rep, i, salt, 8) * FX)) % FX
            u = su + round(1.5 * math.sin(ph_t + i * 1.3 + rep))
            if v < 6:
                continue
            col = FLAME[1] if v < 11 else FLAME[2] if v < 14 else FLAME[3]
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


def wood_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
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
            sw = math.sin(ph_t + i * 1.1 + rep * 0.9 - 2 * math.pi * (o + lu) / 97 + salt)   # a breeze that travels along the vine
            ln = 8 + ((i + rep + salt) % 3) * 2 + (2 if vr(rep, i, salt, 5) > 0.8 else 0)
            leaf(o, lu, vs + 2, ln, sw, 2)
        # long hanging tendrils with leaves along them
        for ti, (tu, tl, ph) in enumerate([(6, 22, 0.4), (19, 15, 1.3), (31, 21, 2.2), (43, 16, 3.5)]):
            tl = tl + round(5 * (vr(rep, ti, salt, 6) - 0.4))
            ph = ph + 5.0 * vr(rep, ti, salt, 7)
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
            berry = ((228, 70, 80, 255), (170, 40, 60, 255)) if vr(rep, ti, salt, 3) < 0.6 else ((150, 120, 240, 255), (96, 70, 190, 255))
            L.put(o + pu, pv + 1, berry[0])        # berry on the tip
            L.put(o + pu, pv + 2, berry[1])
        # flowers
        for fi, (fu, fv) in enumerate([(13, 11), (37, 13)]):
            if vr(rep, fi, salt, 4) < 0.2:                                          # a copy without a flower now and then
                continue
            vs = vs_at(fu)
            for v in range(vs + 2, fv):
                L.put(o + fu, v, STEM)
            pet = [(244, 130, 176, 255), (240, 240, 250, 255), (250, 196, 84, 255), (150, 170, 250, 255)][int(vr(rep, fi, salt, 2) * 4)]
            for (a_, b_) in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, 2)]:
                L.put(o + fu + a_, fv + b_, pet)
            L.put(o + fu, fv, (255, 226, 90, 255) if ((t + fu) // 4) % 2 == 0 else (255, 176, 60, 255))
        # fireflies
        for i, (fu, fv) in enumerate([(10, 17), (26, 19), (45, 14)]):
            u = fu + round(3 * math.sin(ph_t + i * 2.1 + rep * 1.7))
            v = fv + round(1.6 * math.sin(2 * ph_t + i * 1.7 + rep))
            if math.sin(ph_t + i * 2.1 + 1 + rep * 1.7) > -0.2:
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


def storm_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    L.stem = set()
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        for k in range(2):                       # two arcs per 48 px period, studs every 24 px
            rng = random.Random((t // 2) * 97 + k * 13 + rep * 7919 + salt * 104729 + 5)   # a new bolt every 2 frames, different in every copy
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
                    L.put(u, v + dv, BLUE if (t // 2) % 4 else C_BLUE, over=False)
            for (u, v) in path:
                L.put(u, v, Y_CORE if (u + t // 2) % 3 else Y)
                L.put(u, v + 1, Y if (u + t // 2) % 2 else C_BLUE)
                if (u + t // 2) % 2 == 0:
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
            L.put(o + u, 0, C_BLUE if (u + 48 * t // N) % 12 < 4 else BLUE, over=False)
            L.put(o + u, 1, D_BLUE, over=False)
        # studs (always the same)
        for su in (o, o + 24):
            for du in (-1, 0, 1):
                for dv in (3, 4, 5, 6):
                    L.put(su + du, dv - 0, (150, 170, 210, 255) if dv == 3 else (70, 90, 140, 255) if dv < 6 else (30, 40, 80, 255))
            L.put(su, 4, Y if (t // 2) % 2 == 0 else Y_CORE)
            for (a_, b_) in [(-2, 4), (2, 4), (0, 7), (0, 2)]:
                L.put(su + a_, b_, BLUE if (t // 2 + su) % 3 else C_BLUE, over=False)
        # a few loose sparks
        rng = random.Random((t // 2) * 31 + 7 + rep * 17 + salt * 5)
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
            if 6.2 < d <= 7.6 and (a + b + t // 2) % 2 == 0:
                px[(a, b)] = BLUE
    rng = random.Random((t // 2) * 53 + 11)
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
            run = (u - 48 * t // N) % P
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
        k = (32 * t // N + i * 5) % 16
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
        px[(a, b)] = (255, 226, 90, 255) if (t // 4) % 2 == 0 else (255, 190, 70, 255)
    return px


def build_frame(theme, Wb, Hb, t):
    W, H = Wb + 2 * M, Hb + 2 * M
    img = _Img(W, H)
    edge = {"flames": ember_edge, "vines": wood_edge, "storm": storm_edge, "gears": gears_edge, "neon": neon_edge, "matrix": matrix_edge, "frost": frost_edge, "christmas": xmas_edge, "easter": easter_edge}[theme]
    corner = {"flames": ember_corner, "vines": wood_corner, "storm": storm_corner, "gears": gears_corner, "neon": neon_corner, "matrix": matrix_corner, "frost": frost_corner, "christmas": xmas_corner, "easter": easter_corner}[theme]
    rim = {"flames": ember_rim, "vines": wood_rim, "storm": storm_rim, "gears": gears_rim, "neon": neon_rim, "matrix": matrix_rim, "frost": frost_rim, "christmas": xmas_rim, "easter": easter_rim}[theme]
    long_u = max(Wb, Hb) + 2 * M
    px = img.load()
    lean = -3.0 if theme == "flames" else 0.0

    def paint(L, mapper, length):
        stem = getattr(L, "stem", ())
        cm = 0 if theme in ("flames", "gears") else CORN
        for (u, v), c in L.px.items():
            if (u, v) in stem:
                if u < -4 or u >= length + 4:
                    continue
            elif u < cm or u >= length - cm:
                continue
            x, y = mapper(u, v)
            if 0 <= x < W and 0 <= y < H:
                px[x, y] = c

    ew = lambda lean_, blen, salt: edge(t, long_u, lean_, blen, salt)
    paint(ew(0.0, Wb, 0), lambda u, v: (M + u, M - RIM - 1 - v), Wb)         # top
    paint(ew(lean, Hb, 1), lambda u, v: (M - RIM - 1 - v, M + u), Hb)        # left
    paint(ew(lean, Hb, 2), lambda u, v: (W - M + RIM + v, M + u), Hb)        # right
    paint(ew(0.0, Wb, 3), lambda u, v: (M + u, H - M + RIM + v), Wb)         # bottom
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



# ---------------------------------------------------------------- GEARS (steampunk: a chain of meshing brass cogs)
BRASS = [(255, 232, 160), (232, 178, 84), (178, 118, 50), (112, 70, 32), (52, 32, 20)]
COPPER = [(255, 204, 160), (230, 136, 90), (172, 86, 50), (106, 50, 32), (50, 26, 18)]
IRON = [(226, 232, 238), (164, 174, 190), (112, 122, 140), (68, 74, 90), (32, 36, 48)]
GEAR_PALS = (BRASS, COPPER, IRON, BRASS)
TAU = 2 * math.pi


def teeth_for(rp):
    return max(6, 2 * round(math.pi * rp / 5.0))


def draw_gear(put, cx, cy, rp, teeth, rot, pal, spokes=5):
    """A pixel-art cog: pitch radius rp, `teeth` teeth, rotated by `rot` radians; put(x, y, rgb) paints one pixel."""
    ro, rb = rp + 1.1, rp - 1.0
    hub = max(1.5, rp * 0.3)
    pitch = TAU / teeth
    cells = {}
    for y in range(int(cy - ro) - 1, int(cy + ro) + 2):
        for x in range(int(cx - ro) - 1, int(cx + ro) + 2):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            if r > ro:
                continue
            ang = math.atan2(dy, dx)
            if r > rb:
                f = ((ang - rot) / pitch + 0.5) % 1.0 - 0.5
                if abs(f) > 0.40 - 0.14 * (r - rb) / (ro - rb):
                    continue
            lit = (-dx - dy) / (r * 1.4142 + 0.01)                 # light from the upper left
            if r >= rb - 1.0:
                col = pal[0] if (r > rb - 0.5 and lit > 0.35) else pal[1] if lit > -0.5 else pal[2]
            elif r <= hub:
                col = pal[0] if lit > 0.2 and r > 0.6 else pal[1] if r > 0.6 else pal[4]
            elif r < rb - 2.0 and rp >= 7:
                fs = ((ang - rot) / (TAU / spokes) + 0.5) % 1.0 - 0.5
                if abs(fs) * (TAU / spokes) * r > 1.7:
                    col = pal[4]                                    # an opening between the spokes
                else:
                    col = pal[1] if lit > 0.1 else pal[2]
            else:
                col = pal[2] if lit < 0.4 else pal[1]
            cells[(x, y)] = col
    for (x, y), col in list(cells.items()):                        # dark outline
        if any((x + a, y + b) not in cells for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            cells[(x, y)] = pal[3] if col in (pal[1], pal[2], pal[0]) else col
    for (x, y), col in cells.items():
        put(x, y, col)


def gear_chain(blen, salt):
    """[(centre, pitch radius)] of cogs that mesh in a row and fill the edge exactly from 0 to blen."""
    rng = random.Random(blen * 131 + salt * 7919 + 3)
    for _ in range(600):
        rp = rng.choice((6, 7, 8, 9, 9))
        c = rp + 0.5
        chain = [(c, float(rp))]
        for _ in range(40):
            rest = blen - (c + rp)
            last = (rest - 1.1) / 2
            if 4.5 <= last <= 9.5:
                chain.append((c + rp + last, last))
                return chain
            if rest < 12:
                break
            r2 = rng.choice((5, 6, 7, 8, 9, 9))
            c, rp = c + rp + r2, r2
            chain.append((c, rp))
    return chain


def gear_rotations(chain, t, salt, k=2):
    """Rotation (radians) of every cog of a chain at frame t; neighbours turn the opposite way and mesh exactly."""
    rots, prev = [], None
    for i, (c, rp) in enumerate(chain):
        pitch = TAU / teeth_for(rp)
        if prev is None:
            rot = vr(salt, 5) * TAU + pitch * k * t / N * (1 if salt % 2 == 0 else -1)
        else:
            pc, prp, prot = prev
            pp = TAU / teeth_for(prp)
            fx = ((0.0 - prot) / pp) % 1.0
            rot = math.pi - pitch * (0.5 - fx)
        rots.append(rot)
        prev = (c, rp, rot)
    return rots


def gears_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    chain = gear_chain(blen, salt)
    rots = gear_rotations(chain, t, salt)
    for i, ((c, rp), rot) in enumerate(zip(chain, rots)):
        pal = GEAR_PALS[int(vr(salt, i, 9) * 4)]
        draw_gear(lambda x, y, col: L.put(x, y, col + (255,)), c, 12.0, rp, teeth_for(rp), rot, pal, spokes=4 + int(vr(salt, i, 2) * 2))
        if i:                                                        # a spark where a tooth enters the gap
            pc, prp = chain[i - 1]
            pp = TAU / teeth_for(prp)
            fx = ((0.0 - rots[i - 1]) / pp) % 1.0
            if min(fx, 1 - fx) < 0.1:
                u = int(pc + prp)
                L.put(u, 12, (255, 244, 190, 255))
                L.put(u, 11, (255, 196, 90, 255), over=False)
                L.put(u, 13, (255, 196, 90, 255), over=False)
    return L


def gears_corner(t):
    px = {}
    big, small = 9.5, 4.5
    cx = cy = 13.0
    tb, ts = teeth_for(big), teeth_for(small)
    rot_b = 0.3 + TAU / tb * 2 * t / N
    th = math.pi / 4
    pb, ps = TAU / tb, TAU / ts
    fx = ((th - rot_b) / pb) % 1.0
    rot_s = th + math.pi - ps * (0.5 - fx)
    put = lambda x, y, col: px.__setitem__((x, y), col + (255,)) if 0 <= x < FX + RIM and 0 <= y < FX + RIM else None
    draw_gear(put, cx, cy, big, tb, rot_b, BRASS, spokes=6)
    d = (big + small) / math.sqrt(2)
    draw_gear(put, cx + d, cy + d, small, ts, rot_s, COPPER, spokes=3)
    return px


def gears_rim(img, W, H, t):
    draw_ring(img, W, H, [(40, 24, 16), (176, 116, 48), (236, 190, 100), (70, 42, 24)])
    for side in range(4):
        for u in range(0, 500):
            if u % 24 in (8, 9):                                       # rivets
                ring_set(img, W, H, side, u, 2, (255, 236, 170) if u % 24 == 8 else (90, 52, 28))
            run = (u - 48 * t // N) % P
            if run in (0, 1, 2):                                       # a glint running along the pipe
                ring_set(img, W, H, side, u, 1, (255, 248, 210) if run == 1 else (255, 214, 120))


# ---------------------------------------------------------------- NEON (cyberpunk: pink and cyan tubes, flicker, chase lights)
CY_CORE, CY, CY_D, CY_G = (214, 255, 255, 255), (0, 232, 255, 255), (0, 120, 160, 255), (0, 52, 84, 255)
PK_CORE, PK, PK_D, PK_G = (255, 200, 244, 255), (255, 46, 170, 255), (126, 20, 104, 255), (62, 10, 60, 255)


def neon_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        h = lambda *k: vr(rep, salt, *k)
        # 1. a straight cyan tube at the outer side, with one broken piece that flickers
        gap0 = o + int(h(1) * 30) + 4
        for u in range(o, o + P):
            broken = gap0 <= u < gap0 + 9
            if broken and h(2, t // 2) < 0.45:
                continue
            on_pulse = (u - 96 * t // N) % P < 5
            L.put(u, 21, CY_CORE if on_pulse else CY)
            L.put(u, 20, CY_D if not on_pulse else CY, over=False)
            L.put(u, 22, CY_D if not on_pulse else CY, over=False)
            if u % 3 == 0:
                L.put(u, 19, CY_G, over=False)
                L.put(u, 23, CY_G, over=False)
        # 2. a pink square wave near the rim
        shift = int(h(3) * 12)
        lo, hi = 4, 9
        prev = None
        for u in range(o, o + P):
            lvl = lo if ((u - o + shift) // 12) % 2 == 0 else hi
            if prev is not None and lvl != prev:
                for v in range(min(lo, hi), max(lo, hi) + 1):
                    hot = (v + u + t // 2) % 3 == 0
                    L.put(u, v, PK_CORE if hot else PK)
            hot = (u - 48 * t // N) % 24 < 5
            L.put(u, lvl, PK_CORE if hot else PK)
            L.put(u, lvl - 1, PK_D, over=False)
            L.put(u, lvl + 1, PK_D, over=False)
            prev = lvl
        # 3. a sign in the middle: chevrons that chase, a diamond that flickers, or rising signal bars
        kind = int(h(4) * 3)
        if kind == 0:
            step = (t // 3) % 6
            for i in range(3):
                lit = step in (i + 1, i + 2)
                bu = o + 12 + i * 8
                for j in range(5):
                    for (uu, vv) in ((bu + j, 12 + j), (bu + j, 20 - j - 1 if False else 18 - j)):
                        L.put(uu if j < 3 else bu + 4 - (j - 3), vv, CY_CORE if lit and j == 2 else CY if lit else CY_G)
        elif kind == 1:
            on = h(5, t // 3) > 0.16
            cu, cv = o + 24, 15
            for d in range(5):
                for (du, dv) in ((d, 4 - d), (-d, 4 - d), (d, d - 4), (-d, d - 4)):
                    L.put(cu + du, cv + dv, (CY if on else CY_G))
            L.put(cu, cv, PK_CORE if (t // 2) % 2 else PK)
        else:
            lit = (t // 4) % 5
            for i in range(4):
                for j in range(i + 3):
                    L.put(o + 16 + i * 4, 11 + j, PK_CORE if (i < lit and j == i + 2) else PK if i < lit else PK_G)
                    L.put(o + 17 + i * 4, 11 + j, PK if i < lit else PK_G, over=False)
    return L


def neon_corner(t):
    px = {}
    cx = cy = 4.0
    n = FX + RIM
    for a in range(n):
        for b in range(n):
            r = math.hypot(a - cx, b - cy)
            ang = math.atan2(b - cy, a - cx)
            seg = int((ang + math.pi) / TAU * 16)
            if 12.2 <= r < 13.4:                                       # cyan ring with a chasing light
                chase = (seg - t // 2) % 5
                px[(a, b)] = CY_CORE if chase == 0 else CY if chase < 3 else CY_D
            elif 18.2 <= r < 19.2:                                     # outer pink ring
                px[(a, b)] = PK_CORE if (seg + t // 3) % 6 == 0 else PK if (seg + t // 3) % 3 else PK_D
            elif 6.0 <= r < 7.0:
                px[(a, b)] = PK if (t // 4) % 2 else PK_D
    for dx in range(-1, 2):                                          # centre dot
        for dy in range(-1, 2):
            px[(4 + dx, 4 + dy)] = PK_CORE if (t // 3) % 2 else PK
    for i in range(3):                                               # a few glitch blocks
        if vr(t // 3, i, 21) > 0.55:
            gu, gv = 9 + int(vr(t // 3, i, 22) * 14), 9 + int(vr(t // 3, i, 23) * 14)
            col = CY if i % 2 else PK
            for a in range(2):
                for b in range(2):
                    px[(gu + a, gv + b)] = col
    return px


def neon_rim(img, W, H, t):
    draw_ring(img, W, H, [(10, 6, 26), (46, 20, 90), (0, 170, 220), (22, 10, 46)])
    for side in range(4):
        for u in range(0, 500):
            if u % 24 in (6, 18):
                ring_set(img, W, H, side, u, 2, (255, 60, 180))
            run = (u + 48 * t // N) % P
            if run in (0, 1, 2, 3):
                ring_set(img, W, H, side, u, 1, (214, 255, 255) if run in (1, 2) else (0, 232, 255))


# ---------------------------------------------------------------- MATRIX (falling green code streams flowing into the board)
MX = [(222, 255, 230, 255), (120, 255, 150, 255), (44, 236, 84, 255), (26, 172, 58, 255), (16, 112, 40, 255), (8, 64, 24, 255)]
_grng = random.Random(4242)
GLYPHS = []
while len(GLYPHS) < 28:                                              # 3 x 5 pseudo-katakana: bits row by row
    g = [[_grng.random() < 0.52 for _ in range(3)] for _ in range(5)]
    if 7 <= sum(map(sum, g)) <= 11 and any(r[0] for r in g) and any(r[2] for r in g) and any(g[0]) and any(g[4]):
        GLYPHS.append(g)


def matrix_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    for ci in range(-1, ulen // 4 + 2):
        ux = ci * 4
        # faint code that is always there
        for cell in range(4):
            if vr(ci, salt, cell, 99) < 0.3:
                g = GLYPHS[int(vr(ci, salt, cell, 98) * len(GLYPHS))]
                for r in range(5):
                    for c in range(3):
                        if g[r][c]:
                            L.put(ux + c, cell * 6 + r, MX[5], over=False)
        if vr(ci, salt, 1) > 0.72:
            continue
        k = 1 if vr(ci, salt, 2) < 0.55 else 2
        trail = 14 + int(vr(ci, salt, 3) * 11)
        p = (vr(ci, salt, 4) * 48 + 48 * k * t / N) % 48
        head = int(47 - p)                                           # row of the bright head; the trail is above it
        for v in range(max(0, head), min(FX, head + trail)):
            d = v - head
            cellk, row = d // 6, d % 6
            if row == 5:
                continue
            seed = (t + int(vr(ci, salt, cellk, 7) * 32)) // (3 if cellk == 0 else 12)
            g = GLYPHS[int(vr(ci, salt, cellk, seed, 8) * len(GLYPHS))]
            idx = 0 if d < 2 else 1 if d < 6 else 2 if d < trail * 0.35 else 3 if d < trail * 0.65 else 4
            for c in range(3):
                if g[row][c]:
                    L.put(ux + c, v, MX[idx])
    return L


def matrix_corner(t):
    px = {}
    n = FX + RIM
    lo, hi = 3, 23
    for a in range(lo, hi + 1):
        for b in range(lo, hi + 1):
            edge = a in (lo, hi) or b in (lo, hi)
            if edge:
                corner = a in (lo, hi) and b in (lo, hi)
                px[(a, b)] = MX[1] if corner else MX[3] if (a + b + t // 4) % 2 else MX[4]
            else:
                px[(a, b)] = (4, 16, 9, 255)
    for i in range(4):
        for j in range(3):
            ga, gb = 6 + i * 4, 6 + j * 5
            if (i, j) == (3, 2):                                     # blinking cursor
                if (t // 4) % 2 == 0:
                    for a in range(3):
                        for b in range(5):
                            px[(ga + a, gb + b)] = MX[0]
                continue
            g = GLYPHS[int(vr(t // 3, i, j, 31) * len(GLYPHS))]
            col = MX[1] if vr(t // 3, i, j, 32) > 0.8 else MX[2] if (i + j) % 2 else MX[3]
            for r in range(5):
                for c in range(3):
                    if g[r][c]:
                        px[(ga + c, gb + r)] = col
    return px


def matrix_rim(img, W, H, t):
    draw_ring(img, W, H, [(2, 10, 6), (16, 108, 42), (64, 255, 112), (6, 26, 14)])
    for side in range(4):
        for u in range(0, 500):
            if u % 6 == 3:
                ring_set(img, W, H, side, u, 2, (24, 170, 58))
            run = (u - 48 * t // N) % P
            if run in (0, 1, 2):
                ring_set(img, W, H, side, u, 1, (222, 255, 230) if run == 1 else (120, 255, 150))



# ---------------------------------------------------------------- FROST (ice crystals, snow drifts, snowflakes)
ICE = [(255, 255, 255, 255), (214, 244, 255, 255), (150, 206, 244, 255), (88, 148, 214, 255), (46, 92, 164, 255)]


def snowflake(put, cx, cy, size, glow=0):
    """An 8-armed pixel snowflake (plus and cross arms) around (cx, cy); glow brightens the tips."""
    put(cx, cy, ICE[0])
    for i in range(1, size + 1):
        c = ICE[1] if i < size else (ICE[0] if glow else ICE[2])
        for dx, dy in ((i, 0), (-i, 0), (0, i), (0, -i)):
            put(cx + dx, cy + dy, c)
        if i <= size * 2 // 3 + 1:
            for dx, dy in ((i, i), (-i, i), (i, -i), (-i, -i)):
                put(cx + dx, cy + dy, ICE[2] if i < size * 2 // 3 + 1 else (ICE[0] if glow else ICE[3]))


def frost_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    for u in range(-M, ulen):                                       # snow drift along the rim
        h = 1 + int(1.4 + 1.3 * math.sin(u * 0.35 + salt) + 1.0 * math.sin(u * 0.13) + 1.6 * vr(u // 3, salt, 1))
        for v in range(0, min(h, 5)):
            L.put(u, v, ICE[0] if v == h - 1 else ICE[1] if v == h - 2 else ICE[2])
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        for j in range(3):                                          # ice crystals growing outward
            cu = o + 6 + j * 16 + int(vr(rep, salt, j, 1) * 6)
            H = 9 + int(vr(rep, salt, j, 2) * 11)
            W = 6 + int(vr(rep, salt, j, 3) * 4)
            for v in range(2, H):
                f = v / (0.4 * H) if v < 0.4 * H else 1 - (v - 0.4 * H) / (0.6 * H)
                hw = W * 0.5 * f
                for du in range(-int(hw + 0.5), int(hw + 0.5) + 1):
                    col = ICE[0] if du == 0 else ICE[1] if du < 0 else ICE[3 if abs(du) >= hw - 0.4 else 2]
                    L.put(cu + du, v, col)
            tip = int(vr(rep, salt, j, 4) * 2)
            L.put(cu + tip, H, ICE[0])
            if H > 13:                                              # a little side crystal
                for k in range(1, 4):
                    L.put(cu - k - 1, 6 + k, ICE[1])
                    L.put(cu + k + 1, 8 + k, ICE[2])
            sv = int(((t / N) + vr(rep, salt, j, 5)) % 1.0 * H * 1.4)  # a glint runs up the crystal
            if 2 < sv < H:
                L.put(cu, sv, (255, 255, 255, 255))
                L.put(cu - 1, sv, ICE[0], over=False)
        fu, fv = o + 40, 14                                         # a snowflake that twinkles
        if vr(rep, salt, 9) > 0.15:
            on = (t // 4 + rep) % 3 != 2
            snowflake(lambda a, b, c: L.put(a, b, c), fu, fv, 3 if on else 2, glow=(t // 2) % 4 == 0)
        for q in range(5):                                          # falling snow, drifting toward the board
            phase = vr(rep, salt, q, 11)
            k = 1 + (q % 2)
            v = 23 - int(((phase + k * t / N) % 1.0) * 24)
            u = o + int(vr(rep, salt, q, 12) * P) + int(round(1.5 * math.sin(TAU * (k * t / N + phase))))
            L.put(u, v, ICE[0], over=False)
            if q % 2 == 0:
                L.put(u + 1, v, ICE[1], over=False)
    return L


def frost_corner(t):
    px = {}
    put = lambda x, y, col: px.__setitem__((x, y), col) if 0 <= x < FX + RIM and 0 <= y < FX + RIM else None
    cx = cy = 12
    # arms with branches
    put(cx, cy, ICE[0])
    for i in range(1, 11):
        tip = i == 10
        for dx, dy in ((i, 0), (0, i)):
            put(cx + dx, cy + dy, ICE[0] if (tip and (t // 2) % 4 == 0) else ICE[1])
        for dx, dy in ((i, i),):
            if i <= 7:
                put(cx + dx, cy + dy, ICE[1] if i < 7 else ICE[0])
    for br in (4, 7):                                               # branches on the straight arms
        for k in range(1, 4):
            for (x, y) in ((cx + br + k, cy + k), (cx + br + k, cy - k), (cx + k, cy + br + k), (cx - k, cy + br + k)):
                put(x, y, ICE[2])
    for a in range(-1, 2):                                          # hex core
        for b in range(-1, 2):
            put(cx + a, cy + b, ICE[0] if (a, b) == (0, 0) else ICE[1])
    for i in range(4):                                              # loose flakes
        a, b = 3 + int(vr(t // 4, i, 41) * 24), 3 + int(vr(t // 4, i, 42) * 24)
        if (a, b) not in px and vr(t // 4, i, 43) > 0.4:
            put(a, b, ICE[0])
    return px


def frost_rim(img, W, H, t):
    draw_ring(img, W, H, [(20, 40, 76), (86, 144, 206), (226, 248, 255), (40, 70, 120)])
    for side in range(4):
        for u in range(0, 500):
            if u % 12 == 5:
                ring_set(img, W, H, side, u, 2, (255, 255, 255))
            run = (u - 48 * t // N) % P
            if run in (0, 1, 2):
                ring_set(img, W, H, side, u, 1, (255, 255, 255) if run == 1 else (190, 232, 255))


# ---------------------------------------------------------------- CHRISTMAS (garland, lights, baubles, gifts)
XG = [(20, 84, 42, 255), (38, 134, 62, 255), (84, 184, 92, 255), (150, 224, 130, 255)]
XC = [(222, 44, 56, 255), (255, 214, 70, 255), (60, 190, 96, 255), (70, 150, 255, 255)]           # light colours
XC_DIM = [(96, 22, 30, 255), (110, 92, 30, 255), (28, 84, 44, 255), (30, 66, 110, 255)]
GIFTS = [((214, 44, 52), (255, 236, 150)), ((44, 112, 216), (255, 255, 255)), ((244, 198, 62), (214, 44, 52)), ((58, 168, 92), (255, 236, 150)), ((150, 70, 200), (255, 236, 150))]


def _dark(c, k=0.6):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k), 255)


def xmas_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    path = lambda x: 20 - round(6 * math.sin(math.pi * (x % P) / P))
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        h = lambda *k: vr(rep, salt, *k)
        for x in range(P):                                          # the garland
            pv = path(x)
            for dv in range(-2, 3):
                idx = 3 if (x + dv * 2 + int(h(x, 1) * 3)) % 7 == 0 else 2 if dv > 0 else 1 if abs(dv) < 2 else 0
                if abs(dv) == 2 and h(x, dv + 5) < 0.45:
                    continue
                L.put(o + x, pv + dv, XG[idx])
        for i, bx in enumerate((6, 18, 30, 42)):                    # bulbs
            pv = path(bx)
            ci = (i + rep * 2 + int(h(20) * 4)) % 4
            lit = (t // 3 + i + rep) % 4 != 0
            L.put(o + bx, pv - 3, (60, 60, 60, 255))
            for dv in (-4, -5):
                for du in (0, 1):
                    L.put(o + bx + du, pv + dv, XC[ci] if lit else XC_DIM[ci])
            if lit:
                L.put(o + bx - 1, pv - 4, _dark(XC[ci][:3], 0.5), over=False)
                L.put(o + bx + 2, pv - 4, _dark(XC[ci][:3], 0.5), over=False)
                L.put(o + bx, pv - 4, (255, 255, 235, 255))
        bc = XC[int(h(21) * 3) * 1 % 4] if h(22) > 0.5 else (240, 196, 70, 255)   # a bauble that swings
        sway = round(1.2 * math.sin(TAU * t / N + h(23) * 6))
        for v in range(12, path(24) - 2):
            L.put(o + 24 + sway // 2, v, (214, 200, 150, 255))
        cu, cv = o + 24 + sway, 9
        for a in range(-3, 4):
            for b in range(-3, 4):
                d = math.hypot(a, b)
                if d <= 3.2:
                    col = bc if d > 1.0 or True else bc
                    if a + b < -2:
                        col = (255, 255, 255, 255) if a + b < -3 else tuple(min(255, c + 70) for c in bc[:3]) + (255,)
                    elif a + b > 2:
                        col = _dark(bc[:3], 0.62)
                    L.put(cu + a, cv + b, col)
        L.put(cu, cv + 4, (240, 196, 70, 255)) if False else None
        for gi, (gu, size) in enumerate(((8, 8), (34, 6))):         # gifts on the rim
            body, ribbon = GIFTS[int(h(30 + gi) * len(GIFTS))]
            gh = size - 1
            for a in range(size):
                for b in range(gh):
                    col = body + (255,)
                    if a == size // 2 or b == gh // 2:
                        col = ribbon + (255,)
                    elif a == 0 or b == 0 and False:
                        col = _dark(body, 0.7)
                    elif a == size - 1:
                        col = _dark(body, 0.72)
                    L.put(o + gu + a, b, col)
            bu = o + gu + size // 2                                 # bow
            for (da, db) in ((-2, gh), (-1, gh + 1), (2, gh), (1, gh + 1), (0, gh)):
                L.put(bu + da, db, ribbon + (255,))
        for q in range(4):                                          # snow
            phase = h(40 + q)
            v = 23 - int(((phase + t / N) % 1.0) * 24)
            L.put(o + int(h(50 + q) * P), v, (250, 252, 255, 255), over=False)
    return L


def xmas_corner(t):
    px = {}
    ph = TAU * t / N
    LEAF, HI, DK = (34, 130, 58, 255), (92, 196, 100, 255), (18, 76, 40, 255)
    for i, ang in enumerate([-70, -35, 0, 35, 70]):
        a0 = math.radians(45 + ang + 5 * math.sin(ph + i * 1.2))
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
    red, red_d = (230, 40, 54, 255), (160, 20, 40, 255)
    for (a, b) in [(3, 3), (7, 3), (3, 7), (7, 7), (5, 2), (2, 5), (8, 5), (5, 8), (5, 5), (4, 3), (6, 3), (3, 4), (3, 6), (7, 4), (7, 6), (4, 7), (6, 7)]:
        px[(a, b)] = red if (a + b) % 3 else red_d
    for (a, b) in [(4, 4), (5, 4), (6, 4), (4, 5), (5, 5), (6, 5), (4, 6), (5, 6), (6, 6)]:
        px[(a, b)] = (255, 226, 90, 255) if (t // 3 + a + b) % 4 else (255, 255, 220, 255)
    for (a, b) in [(14, 18), (18, 14), (16, 16)]:                   # holly berries
        for da, db in ((0, 0), (1, 0), (0, 1), (1, 1)):
            px[(a + da, b + db)] = red if da + db < 2 else red_d
        px[(a, b)] = (255, 170, 170, 255)
    return px


def xmas_rim(img, W, H, t):
    draw_ring(img, W, H, [(44, 10, 16), (172, 30, 44), (246, 206, 90), (70, 16, 24)])
    for side in range(4):
        for u in range(0, 500):
            if u % 6 == 3:
                ci = (u // 6 + t // 3) % 4
                ring_set(img, W, H, side, u, 2, XC[ci][:3])


# ---------------------------------------------------------------- EASTER (eggs, flowers, butterflies, a bunny)
EGG_PAIRS = [((255, 168, 200), (255, 236, 150)), ((156, 208, 255), (255, 255, 255)), ((190, 158, 240), (255, 200, 230)), ((156, 236, 178), (255, 240, 156)), ((255, 200, 130), (255, 150, 170))]
GRASS = [(60, 132, 60, 255), (96, 176, 84, 255), (150, 220, 116, 255)]


def _egg(L, cu, cv, pair, pattern, shift=0):
    a, b = pair
    for dv in range(-5, 6):
        w = 3.6 * math.sqrt(max(0.0, 1 - (dv / 5.2) ** 2)) * (0.82 + 0.18 * (dv + 5) / 10)
        for du in range(-4, 5):
            if abs(du) > w:
                continue
            col = a
            if pattern == 0:
                col = b if dv % 4 in (0, 1) and abs(dv) < 4 else a
            elif pattern == 1:
                col = b if (du + dv * 2) % 4 in (0, 1) and abs(dv) < 4 else a
            else:
                col = b if (du + 4) % 3 == 0 and (dv + 5) % 3 == 0 else a
            if abs(du) > w - 0.9 and du > 0:
                col = tuple(int(c * 0.82) for c in col)
            if du == -1 and dv == 2:
                col = (255, 255, 255)
            L.put(cu + du + shift, cv + dv, col + (255,))


def _bunny(L, x0, t, salt):
    W_, SH = (252, 248, 242, 255), (214, 206, 218, 255)
    for du in range(-5, 5):
        for dv in range(-3, 4):
            if (du / 4.6) ** 2 + (dv / 3.6) ** 2 <= 1:
                L.put(x0 + du, 4 + dv, SH if dv < -1 or du > 2 else W_)
    for du in range(-3, 4):
        for dv in range(-3, 4):
            if du * du + dv * dv <= 7.5:
                L.put(x0 + 4 + du, 9 + dv, W_ if dv > -2 else SH)
    twitch = (t // 3) % 10 == 0
    for k, ex in enumerate((x0 + 3, x0 + 6)):
        for v in range(12, 19):
            lean = 1 if (twitch and k == 1 and v > 15) else 0
            L.put(ex + lean, v, W_)
            L.put(ex + lean + 1, v, SH)
            if 13 <= v <= 17:
                L.put(ex + lean, v, (255, 190, 206, 255))
    L.put(x0 + 6, 10, (40, 28, 40, 255) if (t // 2) % 16 != 0 else SH)
    L.put(x0 + 8, 9, (255, 150, 170, 255))
    for (a, b) in ((-6, 4), (-6, 5), (-7, 4)):
        L.put(x0 + a, b, (255, 255, 255, 255))


def easter_edge(t, ulen, lean=0.0, blen=10**6, salt=0):
    L = Local(ulen)
    for u in range(-M, ulen):                                       # grass
        h = 1 + int(3 * vr(u // 2, salt, 1))
        for v in range(h):
            L.put(u, v, GRASS[0] if v == 0 else GRASS[1] if v < h - 1 else GRASS[2])
    for rep in range(-1, ulen // P + 2):
        o = rep * P
        h = lambda *k: vr(rep, salt, *k)
        bunny = h(7) < 0.34
        for i, ex in enumerate((7, 36)):
            pair = EGG_PAIRS[int(h(10 + i) * len(EGG_PAIRS))]
            rock = (t // 8 + i + rep) % 4 == 0
            shift = (0, 1, 0, -1)[(t // 2) % 4] if rock else 0
            _egg(L, o + ex, 8, pair, int(h(12 + i) * 3), shift)
        if bunny:
            _bunny(L, o + 21, t, salt)
        else:                                                       # a tulip that sways
            tu = o + 21
            sway = round(math.sin(TAU * t / N + h(15) * 6))
            for v in range(2, 13):
                L.put(tu + (sway if v > 8 else 0), v, GRASS[1])
            L.put(tu - 1, 5, GRASS[2]); L.put(tu - 2, 6, GRASS[2])
            col = [(244, 80, 110), (255, 170, 60), (190, 120, 240)][int(h(16) * 3)]
            for (da, db) in ((-2, 14), (-2, 15), (-1, 13), (-1, 14), (0, 13), (0, 14), (0, 15), (1, 13), (1, 14), (2, 14), (2, 15), (-1, 15), (1, 15)):
                L.put(tu + sway + da, db + 0, col + (255,) if da != 0 or db != 13 else tuple(min(255, c + 60) for c in col) + (255,))
        du = o + 46                                                 # a daisy that turns plus <-> cross
        for v in range(2, 11):
            L.put(du, v, GRASS[1])
        L.put(du + 1, 5, GRASS[2])
        petals = ((1, 0), (-1, 0), (0, 1), (0, -1)) if (t // 6) % 2 == 0 else ((1, 1), (-1, 1), (1, -1), (-1, -1))
        for (a, b) in petals:
            L.put(du + a * 2, 12 + b * 2, (255, 255, 255, 255))
            L.put(du + a, 12 + b, (255, 255, 255, 255))
        L.put(du, 12, (255, 214, 60, 255))
        for j, col in enumerate(((255, 214, 80, 255), (255, 150, 200, 255))):    # butterflies crossing slowly
            bx = o + int(j * 24 + 48 * t / N)
            by = 17 + round(2 * math.sin(TAU * (3 * t / N + j * 0.5)))
            flap = (t // 2) % 2
            for (a, b) in ((0, 0), (0, 1), (0, -1)):
                L.put(bx + a, by + b, (60, 40, 60, 255))
            wings = ((-2, 1), (-1, 1), (2, 1), (1, 1), (-2, 2), (2, 2)) if flap else ((-1, 0), (1, 0), (-2, 0), (2, 0))
            for (a, b) in wings:
                L.put(bx + a, by + b, col)
    return L


def easter_corner(t):
    px = {}
    put = lambda x, y, col: px.__setitem__((x, y), col) if 0 <= x < FX + RIM and 0 <= y < FX + RIM else None
    tilt = round(1.4 * math.sin(TAU * t / N))
    L = Local(60)
    L.px = {}
    _egg(L, 12 + tilt, 12, EGG_PAIRS[0], 0)
    for (u, v), c in L.px.items():                                  # an egg twice the size
        for a in range(2):
            for b in range(2):
                put(u * 2 - 8 + a, v * 2 - 8 + b, c)
    for k in range(1, 8):                                           # leaves
        put(20 + k, 4 + k // 2, GRASS[1]); put(4 + k // 2, 20 + k, GRASS[1])
    dx, dy = 22, 22
    petals = ((1, 0), (-1, 0), (0, 1), (0, -1)) if (t // 6) % 2 == 0 else ((1, 1), (-1, 1), (1, -1), (-1, -1))
    for (a, b) in petals:
        for k in (1, 2, 3):
            put(dx + a * k, dy + b * k, (255, 255, 255, 255))
    put(dx, dy, (255, 214, 60, 255))
    return px


def easter_rim(img, W, H, t):
    draw_ring(img, W, H, [(46, 96, 52), (120, 200, 110), (196, 238, 166), (70, 130, 70)])
    pastel = [(255, 168, 200), (255, 236, 150), (190, 158, 240), (156, 208, 255)]
    for side in range(4):
        for u in range(0, 500):
            if u % 8 == 4:
                ring_set(img, W, H, side, u, 2, pastel[(u // 8) % 4])
            run = (u - 48 * t // N) % P
            if run in (0, 1, 2):
                ring_set(img, W, H, side, u, 1, (255, 255, 235) if run == 1 else (255, 244, 170))

"""Reading and writing .aseprite files (per the official specification: github.com/aseprite/aseprite/docs/ase-file-specs.md).

Supported: (normal) layers, frames with durations, cels (RAW/zlib/linked), tags, slices (including 9-patch),
palette, sRGB profile. Writing is RGBA only (32 bpp). Reading also supports Indexed (8) and Grayscale (16) -> RGBA.

Aseprite itself is not needed: this is only the format. (The files we write were verified by reading them back with this
same reader and comparing with PNGs; they were not opened in Aseprite itself.)
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MAGIC_FILE = 0xA5E0
MAGIC_FRAME = 0xF1FA

CHUNK_OLD_PALETTE_4 = 0x0004
CHUNK_OLD_PALETTE_11 = 0x0011
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_COLOR_PROFILE = 0x2007
CHUNK_TAGS = 0x2018
CHUNK_PALETTE = 0x2019
CHUNK_USER_DATA = 0x2020
CHUNK_SLICE = 0x2022


@dataclass
class Layer:
    name: str
    visible: bool = True
    editable: bool = True
    kind: int = 0                 # 0 obican, 1 grupa, 2 tilemap
    child_level: int = 0
    opacity: int = 255
    blend: int = 0


@dataclass
class Cel:
    x: int
    y: int
    width: int
    height: int
    rgba: bytes                   # width*height*4, red po red
    opacity: int = 255


@dataclass
class Tag:
    name: str
    start: int
    end: int
    direction: int = 0            # 0 napred, 1 nazad, 2 ping-pong


@dataclass
class SliceKey:
    frame: int
    x: int
    y: int
    width: int
    height: int
    center: tuple[int, int, int, int] | None = None     # (x, y, w, h) relative to the slice


@dataclass
class Slice:
    name: str
    keys: list[SliceKey]

    @property
    def is_nine_patch(self) -> bool:
        return any(k.center is not None for k in self.keys)


@dataclass
class Sprite:
    width: int
    height: int
    layers: list[Layer] = field(default_factory=list)
    durations: list[int] = field(default_factory=list)            # po frejmu, ms
    cels: dict[tuple[int, int], Cel] = field(default_factory=dict)   # (frame, layer) -> Cel
    tags: list[Tag] = field(default_factory=list)
    slices: list[Slice] = field(default_factory=list)
    palette: list[tuple[int, int, int, int]] = field(default_factory=list)
    depth: int = 32

    @property
    def frame_count(self) -> int:
        return len(self.durations)

    # ---- spajanje slojeva u jednu sliku ----------------------------------------------
    def flatten(self, frame: int = 0) -> bytes:
        """RGBA (width*height*4) - normal alpha blending of the layers."""
        out = bytearray(self.width * self.height * 4)
        for li, layer in enumerate(self.layers):
            if not layer.visible or layer.kind != 0:
                continue
            cel = self.cels.get((frame, li))
            if cel is None:
                continue
            lop = layer.opacity / 255 * cel.opacity / 255
            for cy in range(cel.height):
                y = cel.y + cy
                if not 0 <= y < self.height:
                    continue
                for cx in range(cel.width):
                    x = cel.x + cx
                    if not 0 <= x < self.width:
                        continue
                    i = (cy * cel.width + cx) * 4
                    r, g, b, a = cel.rgba[i:i + 4]
                    a = a * lop / 255
                    if a <= 0:
                        continue
                    o = (y * self.width + x) * 4
                    da = out[o + 3] / 255
                    na = a + da * (1 - a)
                    for c, v in enumerate((r, g, b)):
                        out[o + c] = round((v * a + out[o + c] * da * (1 - a)) / na)
                    out[o + 3] = round(na * 255)
        return bytes(out)


# =========================================================================================
# CITANJE
# =========================================================================================
class _Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def u8(self) -> int:
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def i16(self) -> int:
        v = struct.unpack_from("<h", self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def raw(self, n: int) -> bytes:
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def string(self) -> str:
        return self.raw(self.u16()).decode("utf-8")

    def skip(self, n: int) -> None:
        self.p += n


def _to_rgba(pixels: bytes, depth: int, palette: list[tuple[int, int, int, int]]) -> bytes:
    if depth == 32:
        return pixels
    out = bytearray()
    if depth == 16:                      # sivo + alfa
        for i in range(0, len(pixels), 2):
            v, a = pixels[i], pixels[i + 1]
            out += bytes((v, v, v, a))
    else:                                # indeksirano
        for idx in pixels:
            out += bytes(palette[idx]) if idx < len(palette) else b"\0\0\0\0"
    return bytes(out)


def read_aseprite(path: str | Path) -> Sprite:
    data = Path(path).read_bytes()
    r = _Reader(data)
    r.u32()                                           # file size
    if r.u16() != MAGIC_FILE:
        raise ValueError("nije .aseprite fajl")
    frames, width, height, depth = r.u16(), r.u16(), r.u16(), r.u16()
    r.u32()                                           # flags
    r.u16()                                           # speed
    r.skip(8)
    transparent_index = r.u8()
    r.skip(3)
    r.u16()                                           # number of colours
    r.skip(2 + 4 + 4 + 84 - 4 - 4 + 4 + 4)            # pixel w/h, grid x/y/w/h, rezervisano (do 128 bajtova)
    r.p = 128

    sprite = Sprite(width, height, depth=depth)
    for fi in range(frames):
        start = r.p
        frame_bytes = r.u32()
        if r.u16() != MAGIC_FRAME:
            raise ValueError(f"los frejm {fi}")
        old_count = r.u16()
        duration = r.u16()
        r.skip(2)
        new_count = r.u32()
        count = new_count if new_count else old_count
        sprite.durations.append(duration)
        for _ in range(count):
            cstart = r.p
            csize = r.u32()
            ctype = r.u16()
            if ctype == CHUNK_LAYER:
                flags, kind, child = r.u16(), r.u16(), r.u16()
                r.skip(4)
                blend = r.u16()
                opacity = r.u8()
                r.skip(3)
                name = r.string()
                sprite.layers.append(Layer(name, bool(flags & 1), bool(flags & 2), kind, child, opacity, blend))
            elif ctype == CHUNK_CEL:
                layer, x, y, opacity, ctype2 = r.u16(), r.i16(), r.i16(), r.u8(), r.u16()
                r.i16()
                r.skip(5)
                if ctype2 in (0, 2):
                    w, h = r.u16(), r.u16()
                    body = r.raw(cstart + csize - r.p)
                    pixels = zlib.decompress(body) if ctype2 == 2 else body
                    sprite.cels[(fi, layer)] = Cel(x, y, w, h, _to_rgba(pixels, depth, sprite.palette), opacity)
                elif ctype2 == 1:                      # povezana celija
                    src = r.u16()
                    linked = sprite.cels.get((src, layer))
                    if linked:
                        sprite.cels[(fi, layer)] = Cel(x, y, linked.width, linked.height, linked.rgba, opacity)
            elif ctype == CHUNK_TAGS:
                n = r.u16()
                r.skip(8)
                for _t in range(n):
                    a, b, direction = r.u16(), r.u16(), r.u8()
                    r.u16()
                    r.skip(6 + 3 + 1)
                    sprite.tags.append(Tag(r.string(), a, b, direction))
            elif ctype == CHUNK_SLICE:
                n, flags = r.u32(), r.u32()
                r.u32()
                name = r.string()
                keys = []
                for _k in range(n):
                    frame, x, y, w, h = r.u32(), r.i32(), r.i32(), r.u32(), r.u32()
                    center = None
                    if flags & 1:
                        center = (r.i32(), r.i32(), r.u32(), r.u32())
                    if flags & 2:
                        r.skip(8)
                    keys.append(SliceKey(frame, x, y, w, h, center))
                sprite.slices.append(Slice(name, keys))
            elif ctype == CHUNK_PALETTE:
                size, first, last = r.u32(), r.u32(), r.u32()
                r.skip(8)
                if len(sprite.palette) < size:
                    sprite.palette += [(0, 0, 0, 255)] * (size - len(sprite.palette))
                for i in range(first, last + 1):
                    flags = r.u16()
                    rr, gg, bb, aa = r.u8(), r.u8(), r.u8(), r.u8()
                    if flags & 1:
                        r.string()
                    sprite.palette[i] = (rr, gg, bb, aa)
            elif ctype == CHUNK_OLD_PALETTE_4 and not sprite.palette:
                packets = r.u16()
                idx = 0
                for _p in range(packets):
                    idx += r.u8()
                    n = r.u8() or 256
                    for _c in range(n):
                        rr, gg, bb = r.u8(), r.u8(), r.u8()
                        while len(sprite.palette) <= idx:
                            sprite.palette.append((0, 0, 0, 255))
                        sprite.palette[idx] = (rr, gg, bb, 255)
                        idx += 1
            r.p = cstart + csize                       # skip everything we did not read
        r.p = start + frame_bytes
    if depth == 8 and sprite.palette and 0 <= transparent_index < len(sprite.palette):
        pass                                           # transparency for indexed: alpha comes from the cel (0 = empty)
    return sprite


# =========================================================================================
# PISANJE
# =========================================================================================
def _string(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def _chunk(ctype: int, body: bytes) -> bytes:
    return struct.pack("<IH", len(body) + 6, ctype) + body


def write_aseprite(path: str | Path, sprite: Sprite) -> None:
    """Pise RGBA .aseprite. Sloj i = sprite.layers[i]; celije u sprite.cels[(frame, sloj)]."""
    chunks_first = []
    chunks_first.append(_chunk(CHUNK_COLOR_PROFILE, struct.pack("<HHI", 1, 0, 0) + b"\0" * 8))   # sRGB
    palette = sprite.palette or [(0, 0, 0, 0)]
    pal = struct.pack("<III", len(palette), 0, len(palette) - 1) + b"\0" * 8
    for rr, gg, bb, aa in palette:
        pal += struct.pack("<HBBBB", 0, rr, gg, bb, aa)
    chunks_first.append(_chunk(CHUNK_PALETTE, pal))
    for layer in sprite.layers:
        flags = (1 if layer.visible else 0) | (2 if layer.editable else 0)
        body = struct.pack("<HHHHHHB", flags, layer.kind, layer.child_level, 0, 0, layer.blend, layer.opacity)
        body += b"\0\0\0" + _string(layer.name)
        chunks_first.append(_chunk(CHUNK_LAYER, body))

    def cel_chunk(fi: int) -> list[bytes]:
        out = []
        for li in range(len(sprite.layers)):
            cel = sprite.cels.get((fi, li))
            if cel is None:
                continue
            body = struct.pack("<HhhBHh", li, cel.x, cel.y, cel.opacity, 2, 0) + b"\0" * 5
            body += struct.pack("<HH", cel.width, cel.height) + zlib.compress(cel.rgba, 9)
            out.append(_chunk(CHUNK_CEL, body))
        return out

    tail = []
    if sprite.tags:
        body = struct.pack("<H", len(sprite.tags)) + b"\0" * 8
        for t in sprite.tags:
            body += struct.pack("<HHBH", t.start, t.end, t.direction, 0) + b"\0" * 6 + b"\0\0\0\0" + _string(t.name)
        tail.append(_chunk(CHUNK_TAGS, body))
    for s in sprite.slices:
        flags = 1 if s.is_nine_patch else 0
        body = struct.pack("<III", len(s.keys), flags, 0) + _string(s.name)
        for k in s.keys:
            body += struct.pack("<IiiII", k.frame, k.x, k.y, k.width, k.height)
            if flags & 1:
                cx, cy, cw, ch = k.center or (0, 0, k.width, k.height)
                body += struct.pack("<iiII", cx, cy, cw, ch)
        tail.append(_chunk(CHUNK_SLICE, body))

    frames_data = []
    for fi in range(sprite.frame_count):
        chunks = (chunks_first + cel_chunk(fi) + tail) if fi == 0 else cel_chunk(fi)
        payload = b"".join(chunks)
        head = struct.pack("<IHHHBBI", len(payload) + 16, MAGIC_FRAME, min(len(chunks), 0xFFFF),
                           sprite.durations[fi], 0, 0, len(chunks))
        frames_data.append(head + payload)

    body = b"".join(frames_data)
    header = struct.pack("<IHHHHHIHII", len(body) + 128, MAGIC_FILE, sprite.frame_count, sprite.width,
                         sprite.height, 32, 1, sprite.durations[0] if sprite.durations else 100, 0, 0)
    header += struct.pack("<B3sH", 0, b"\0\0\0", len(palette) if len(palette) < 256 else 0)
    header += struct.pack("<BBhhHH", 1, 1, 0, 0, 16, 16)
    header = header.ljust(128, b"\0")
    Path(path).write_bytes(header + body)


# ---- helper functions for building sprites from pygame surfaces -------------------------------
def surface_to_rgba(surface) -> bytes:
    import pygame
    return pygame.image.tobytes(surface, "RGBA")


def palette_from_surfaces(surfaces, limit: int = 256) -> list[tuple[int, int, int, int]]:
    seen: dict[tuple[int, int, int, int], None] = {}
    for s in surfaces:
        data = surface_to_rgba(s)
        for i in range(0, len(data), 4):
            px = tuple(data[i:i + 4])
            if px[3] and px not in seen:
                seen[px] = None
    return [(0, 0, 0, 0)] + [c for c in seen][:limit - 1]

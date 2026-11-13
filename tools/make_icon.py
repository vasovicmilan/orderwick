"""The game icon. You draw ONLY 32x32 (assets/icon/icon_32.png) and this tool makes everything else:

    python tools/make_icon.py              # creates a placeholder icon from the assets if icon_32.png does not exist
    python tools/make_icon.py --force      # creates the placeholder icon again (overwrites icon_32.png)

Output (assets/icon/): icon_16..icon_1024.png (integer scaling, no blurring), icon.ico (Windows: 16,32,48,64,128,256),
icon.icns (macOS: 16..1024). If a hand-drawn icon_16.png exists it is used for 16 px (and 48 px = x3).
Aseprite source: assets/aseprite/icon.aseprite (32x32). After drawing, export the PNG as assets/icon/icon_32.png.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pygame

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon"
SPRITES = ROOT / "assets" / "sprites"
WOOD, DARK, MID, PLANK, TAN, CREAM = (90, 78, 68), (66, 57, 52), (121, 103, 85), (136, 115, 90), (199, 176, 139), (250, 214, 184)


def placeholder() -> pygame.Surface:
    """32x32: a wooden tile with two cards (a stand-in until you draw your own)."""
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    # dark outline with rounded corners, wooden board, dashed edge like on the game board
    pygame.draw.rect(s, DARK, (0, 0, 32, 32), border_radius=5)
    pygame.draw.rect(s, WOOD, (1, 1, 30, 30), border_radius=4)
    pygame.draw.rect(s, PLANK, (3, 3, 26, 26), border_radius=2)
    for i in range(4, 28, 2):
        s.set_at((i, 4), TAN)
        s.set_at((i + 1, 27), MID)
    back, front = (pygame.image.load(str(SPRITES / f"{n}.png")).convert_alpha() for n in ("green_apple", "blue_cherry"))
    for img, (x, y) in ((back, (4, 5)), (front, (12, 11))):
        pygame.draw.rect(s, DARK, (x - 1, y - 1, 18, 18))
        s.blit(img, (x, y))
    return s


def scaled(master: pygame.Surface, size: int, small: pygame.Surface | None) -> pygame.Surface:
    """Integer scaling (nearest). 16 px: the hand-drawn icon_16 if present, otherwise downscaled; 48 = 16 x3 if icon_16 exists."""
    if size == 16:
        return small if small is not None else pygame.transform.scale(master, (16, 16))
    if size == 48 and small is not None:
        return pygame.transform.scale(small, (48, 48))
    return pygame.transform.scale(master, (size, size))


def png_bytes(surface: pygame.Surface) -> bytes:
    import io
    from PIL import Image
    img = Image.frombytes("RGBA", surface.get_size(), pygame.image.tobytes(surface, "RGBA"))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def write_ico(path: Path, images: dict[int, bytes]) -> None:
    sizes = sorted(images)
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for size in sizes:
        data = images[size]
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.write_bytes(head + entries + blobs)


def write_icns(path: Path, images: dict[int, bytes]) -> None:
    types = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07", 256: b"ic08", 512: b"ic09", 1024: b"ic10"}
    body = b"".join(types[s] + struct.pack(">I", 8 + len(images[s])) + images[s] for s in sorted(types) if s in images)
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def main() -> None:
    pygame.display.init()                 # not pygame.init(): tools never need the sound system (it can hang on some Linux audio setups)
    pygame.font.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    master_path = OUT / "icon_32.png"
    if "--force" in sys.argv or not master_path.exists():
        pygame.image.save(placeholder(), str(master_path))
        print("napravljena zamenska ikona", master_path)
    master = pygame.image.load(str(master_path)).convert_alpha()
    if master.get_size() != (32, 32):
        raise SystemExit(f"icon_32.png mora biti 32x32 (ima {master.get_size()})")
    small_path = OUT / "icon_16.png"
    small = pygame.image.load(str(small_path)).convert_alpha() if small_path.exists() else None
    if small is not None and small.get_size() != (16, 16):
        raise SystemExit("icon_16.png mora biti 16x16")
    images = {}
    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        img = scaled(master, size, small)
        pygame.image.save(img, str(OUT / f"icon_{size}.png"))
        images[size] = png_bytes(img)
    write_ico(OUT / "icon.ico", {s: images[s] for s in (16, 32, 48, 64, 128, 256)})
    write_icns(OUT / "icon.icns", images)
    # Aseprite source (only if it does not exist yet, so your work is not overwritten)
    ase = ROOT / "assets" / "aseprite" / "icon.aseprite"
    if not ase.exists():
        from aseprite_io import Cel, Layer, Sprite, palette_from_surfaces, surface_to_rgba, write_aseprite
        sp = Sprite(32, 32, layers=[Layer("Icon")], palette=palette_from_surfaces([master]))
        sp.durations.append(100)
        sp.cels[(0, 0)] = Cel(0, 0, 32, 32, surface_to_rgba(master))
        write_aseprite(ase, sp)
    print("ikone:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()

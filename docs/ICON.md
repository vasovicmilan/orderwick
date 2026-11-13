# The game icon

**Draw 32×32 px** (one file, `assets/aseprite/icon.aseprite`, transparent background). The tool makes every other size:
1. Draw in Aseprite and export the PNG as `assets/icon/icon_32.png`.
2. (Optional) hand-draw `icon_16.png` at 16×16 – 16 px is the title-bar/taskbar size and looks better when drawn on purpose.
3. `python tools/make_icon.py` → `icon_16/32/48/64/128/256/512/1024.png`, `icon.ico` (Windows) and `icon.icns` (macOS).
Scaling is by integers (nearest), so it stays sharp: 32 → 64 (×2) → 128 (×4) → 256 (×8) → 512 (×16) → 1024 (×32).

| Where | Sizes |
|---|---|
| Game window (pygame) | 32×32 (`icon_32.png`) |
| Windows .ico | 16, 32, 48, 64, 128, 256 |
| macOS .icns | 16 … 1024 |
| Linux | PNG 32/64/128/256 |
| itch.io page | cover image 630×500 (recommended), plus screenshots |

Tips: a readable silhouette at 16 px (thick outline, 2–3 colours), the board palette (WOOD/DARK/CREAM/GOLD), no tiny text.
The current icon is a placeholder (a wooden tile with a green apple and a blue cherry) made from your sprites.
`python tools/make_icon.py --force` rebuilds the placeholder (delete `assets/aseprite/icon.aseprite` first to rewrite it too).

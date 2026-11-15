# Board themes and card styles

Two kinds of unlockable looks. You choose them in **Settings → Board / Cards** (locked ones show a lock and the reason).

| Look | What changes | Shipped | Unlocked by |
|---|---|---|---|
| **Board theme** | the board **and** the HUD, dialogs, menus, buttons, panels, icons and text colours | `emerald` (your emerald board) | every trophy (`"all_trophies"`) |
| **Card style** | the card backgrounds (all 38 cards + `question_mark` + `exclamation_mark`) | `gold` (your gold cards) | trophy `score_100k` ("Hundred Thousand") |

Both are registered in `config.py` (`BOARD_THEMES`, `CARD_STYLES`); an entry is `(id, display name, unlock rule)`, the first entry is the default.
Unlock rule: `None` (always), `"all_trophies"`, or any trophy id from `docs/PROGRESSION.md`. When a look unlocks a toast appears once
("NEW BOARD!" / "NEW CARDS!"); it is not selected automatically.

## From your Aseprite files to the game: `tools/import_aseprite.py`
    python tools/import_aseprite.py path/to/folder_with_the_aseprite_files
It understands the old file names (`bannana`, `eqlamtion`, ...) and the in-game names (`docs/ASSET_NAMES.md`).

**Cards** – 16×16, two frames: **frame 0 = classic card, frame 1 = gold card**, bottom layer = background, top layer = fruit.
Writes `assets/sprites/<name>.png` (classic), `assets/card_styles/gold/<name>.png` (gold), the source renamed to
`assets/aseprite/cards/<name>.aseprite`, and loose copies in `export/classic/`, `export/gold/` and `export/transparent/` (fruit only).

**Board** – `board.aseprite` (193×217): layer 1 of a frame is the board, the other layers are mock-ups. Frame 0 = wood (the default,
checked against `assets/board/board.png`), frame 3 = emerald (`--board-frame wood:0 --board-frame emerald:3`).
The emerald board goes to `assets/themes/emerald/board/board.png` and `tools/make_theme.py` then builds everything else for it.

## How the HUD / dialogs / icons get the board's palette: `tools/make_theme.py`
    python tools/make_theme.py emerald --board export/board/board_emerald.png      # first time
    python tools/make_theme.py emerald                                            # after editing palette.json
1. It compares the new board pixel by pixel with the default board: the colour found where the default board has WOOD, DARK, MID,
   PLANK, PLANK_L, TAN or CREAM is the new colour of that **role**.
2. Roles the board does not contain (button highlight, hover/disabled body, icon colours, text colours) are derived from those.
   On a theme with light buttons (like emerald) button labels are dark with a light shadow; the rest of the text is pale.
3. The result is `assets/themes/<id>/palette.json` (edit any role by hand, then re-run) and the generated `hud/panel.png`, `inset.png`,
   `button.png` (4 states), `divider.png`, `icons.png`, `icons_audio.png` – made by the same generators as the default look
   (`tools/make_hud_assets.py`), so every piece is built from the same few colours. `--rederive` reads the palette from the board again.

Anything you draw by hand later simply replaces the generated PNG (keep the sizes below). Every file in a theme is optional – a missing one
falls back to the default look.

| File in `assets/themes/<id>/` | Size | Notes |
|---|---|---|
| `board/board.png` | 193 × 217 | same layout as the default board |
| `hud/panel.png` | 16×16 | 9-slice, 6 px edge; pixel (1,1) is also the frame colour of the menu card strip |
| `hud/inset.png` | 12×12 | 9-slice, 4 px edge |
| `hud/button.png` | 48×12 | 4 states of 12×12 (normal, hover, pressed, disabled), 9-slice 4 px |
| `hud/divider.png` | 4×2 | tile |
| `hud/icons.png`, `hud/icons_audio.png` | 96×12, 72×12 | HUD icons and menu/sound icons |
| `palette.json` | – | colour roles (see above); text colours are read from it |

## Card styles
`assets/card_styles/<id>/<colour>_<type>.png` (16×16, names in `docs/ASSET_NAMES.md`) plus `question_mark.png` and `exclamation_mark.png`.
A missing file falls back to the classic card.

## Adding a new look
1. Draw it (Aseprite) and put it in the folder above, or extend your `.aseprite` files with more frames/boards and use the importer.
2. Add the entry to `config.BOARD_THEMES` / `CARD_STYLES`. 3. Run the tests (`Looks` checks that every registered look has its files and
that boards assemble in every theme).

## Animated frame around the board (`frame.json`)

A board theme can have an animated frame. Put `frame.json` next to `palette.json`:

```json
{ "style": "flames", "fps": 10 }
```

Styles: `flames` (Ember), `vines` (Wildwood), `storm` (electric yellow and blue), `gears` (Clockwork: meshing brass cogs), `neon` (Neon District: flickering pink and cyan tubes) `matrix` (Mainframe: falling green code), `frost` (ice crystals and snow), `christmas` (garland, lights, baubles, gifts) and `easter` (eggs, flowers, butterflies, a bunny). The frame is generated in code
(`orderwick/view/frame_fx.py`) for every board size, 28 px wide on every side, 32 frames (every 48 px stretch of an edge is varied, so nothing repeats visibly; fps 8–12 looks calm). A theme without `frame.json`
A theme with a frame also brings its board lanes to life, automatically and with the same style: the decoration painted into the lanes (cracks, moss, rungs) is found in `board.png` and re-coloured over a 5 second loop (a surge of heat, a breeze, a flash), plus a few extra pixels (rising embers, spores, one bolt of lightning, small turning cogs, a neon scan line and glitch, falling code heads). It is drawn under the cards (`orderwick/view/lane_fx.py`); no extra files are needed.
(or with an unknown style) has no frame. Themes that come from the server get `frame.json` through the same content
sync as `board.png` and the HUD files. When a frame is active only 8 of its 28 px are reserved when the board is fitted
into the window, so it does not shrink the board; on a tight window the outer edge of the frame is clipped.

## Card backgrounds and card sets

`tools/import_aseprite.py` reads the card sources (16x16, 9 frames: classic, gold, ember, frost, wildwood, neon, clockwork, matrix, storm; bottom layer = background, top layer = picture) and writes
`assets/cards_fg/<card>.png` (the picture alone), `assets/card_styles/<style>/background.png` and the `?`/`!` of every style. A card is drawn as background + picture
(`engine/assets.py`), so a new card set from the server (`card_sets/<code>/<card>.png` + `families.json`, see `core/cardsets.py`) works with every background.

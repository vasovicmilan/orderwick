# Orderwick

A 2D pixel-art card-sorting puzzle in Python + pygame-ce. Sort the cards so every column holds a single type.
Cards come in families (fruit is the first one) that grow over time; new families and expansions are planned.

Author: Milan Vasovic · vasovicmilanbiz@gmail.com

## Run

    pip install -r requirements.txt     # pygame-ce, Python 3.10+
    python main.py                      # python main.py --no-audio = without sound

**Developer mode** (local testing only): `python main.py --dev` unlocks every card, trophy, board theme and card style so you can check the
looks without playing. It saves into a separate `dev` folder (your real progress is never touched), puts `[DEV]` in the window title,
and is always disabled in packaged builds.

Tests: `python -m unittest discover -s tests -v`  ·  Random-input stress test: `python tools/monkey_test.py`.
Errors are written to `crash.log` in the data folder (next to `progress.json`, `settings.json`, `leaderboard.json`).

## The game

- **Campaign** – 15 levels from easy to hard (width 5 → 10, then fewer free slots, then taller columns; the finale
  is 10 × 13 with one free slot). You pick the starting level.
- **Hard mode** – goes straight to the finale (level 15), then keeps generating finale boards.
- **Custom game** – choose width, free slots and height (not ranked).
- **Leaderboard** – local top 10 for the campaign and for hard mode.
- **Daily challenges** – one daily board (same for everyone, solvable once a day) and three tasks a day (easy, medium, hard) drawn from a catalogue of 200+; the same set for the whole
  day, a new one at local midnight. They count while you play Campaign or Hard mode (not Custom). Streaks and totals feed 10 trophies.
  Details: `docs/DAILY.md`.
- **Trophies** – 50 achievements and a **card collection**: only the first card of every family is unlocked at the start;
  the others are earned by revealing cards and solving boards (thresholds in `config.UNLOCK_THRESHOLDS`).
- **Settings** – music and effects on/off + volume, board theme, card style. **About** – the game, the author, links.
- **Unlockable looks** – the *Emerald* board theme (restyles the board, HUD, dialogs, menus, icons and text colours) for completing every
  trophy, and the *Gold* card style for reaching 100,000 points in one run.

Rules: the top card (and the run of equal cards under it) moves onto an empty column or onto a column whose top card is the
same type; free slots (top right) hold one card each; one column is always empty. A clean column may move to an empty
column (refusing that move would reveal hidden cards). Extras: time and moves are measured, only **one undo** is allowed
(U), and **rescue** (X) adds a free slot but drops one level (after you solve the board you return to the previous level).

Keys: `1-9,0` columns · `a s d f…` free slots · arrows + Enter · `U` undo · `X` rescue · `R` new board (-50, press twice) ·
`Esc`/`P` pause · `Q` end the run (with confirmation) · `F11` full screen. Everything also works with the mouse.

## Documentation

`docs/PROGRESSION.md` (collection, trophies, sound) · `docs/UI_SIZES.md` (sizes) · `docs/ICON.md` (icon) ·
`docs/DAILY.md` (daily challenges) · `docs/BUILD.md` (executables for Windows/Linux/macOS) · `docs/LICENSING.md` (licences, protection) ·
`docs/ITCH_CHECKLIST.md` · `docs/ASSET_NAMES.md` (card file names) · `docs/THEMES.md` (unlockable board themes and card styles).

Tools: `tools/import_aseprite.py` (your .aseprite files → game PNGs), `tools/make_theme.py` (HUD/dialogs/icons in a board's palette),
`tools/make_audio.py`, `tools/make_icon.py`, `tools/make_hud_assets.py`, `tools/make_audio_icons.py`, `tools/export_aseprite.py`,
`tools/monkey_test.py`.

## Structure

    main.py                    entry point (--selftest, --no-audio, --dev)
    assets/sprites/*.png       16x16 cards named <colour>_<type> (38 types) + question_mark.png + exclamation_mark.png
    assets/board/board.png     board template, 10 lanes x 12 rows (193 x 217 px)
    assets/hud/*.png           HUD in the same style: panel, inset, button (4 states), icons, audio icons, divider
    assets/fonts/              Public Pixel (titles) + Pixel Operator 8 (long texts), both CC0
    assets/audio/              generated sound effects (wav) and music (ogg)
    assets/icon/, aseprite/    game icon (all sizes) and .aseprite sources
    orderwick/
      config.py                constants (colours, sizes, card families, unlock thresholds, keys)
      game.py                  OrderwickGame(App): leaderboard, progress, settings, toasts, audio
      core/                    LOGIC, no pygame (testable on its own)
        models.py board.py     Card, Loc, LevelSpec; Board: move rules, win, undo snapshots
        generator.py           builds boards BACKWARDS from the solved state (rotations in thin layers), then breaks
                               regularities with swaps that PathSolver verifies, so every board is provably solvable
        pathsolver.py          solver with the exact game rules (proof of solvability, rescue check)
        levels.py scoring.py   LevelCatalog + Modes (Campaign/Hard/Custom); score = level + move bonus + time bonus
        collection.py          card unlocking;  achievements.py: trophies;  palette.py: picks the types for a board
        session.py             GameSession / Round: moves, time, 1 undo, rescue, score, events
      engine/                  small engine that knows nothing about this game
        app.py scene.py        main loop, scene stack;  native_scene.py: integer-scaled pixel-art scenes
        ui.py nine_slice.py    widgets, 9-slice;  pixel_font.py: unsmoothed integer-scaled font
        audio.py logs.py       sound (effects + music playlist), crash log;  tasks.py events.py: threads, EventBus
      view/                    board_skin.py, board_view.py, hud_view.py, wood_kit.py (UI kit), toasts.py
      scenes/                  menu, level select, custom, game, pause, confirm, name entry, leaderboard, help,
                               trophies, settings, about
      data/                    JSON storage: leaderboard, progress (collection + trophies), settings

### The board from an asset

`board.png` is the template for the biggest board (10 lanes × 12 rows): 3 px outer frame, a row of free slots (16 px),
a 3 px gap, then 16 × 192 px lanes separated by 3 px gaps. Smaller boards are assembled from the same asset: a narrower
board takes the first n lanes, a shorter one shortens the lane (the top and bottom 4 rows stay, the middle gradient is
squeezed while the dashed edge is preserved). A 10 × 12 board is pixel-for-pixel identical to the asset. Cards and board
are drawn at the original resolution and the **whole** picture is scaled by one integer.

Slots in the top row that are not free show `exclamation_mark.png` (locked, on the left); free slots are on the right.
When a rescue adds a free slot, one "!" disappears. If you redraw `board.png`, keep 193 × 217 (frame 3, gap 3, slot and lane
16 px wide, lane 192 px tall); the first/last 4 lane rows are a "cap" that does not stretch.

### Fonts and HUD

- **Fonts:** *Public Pixel* (GGBotNet, CC0) is drawn for capitals, so titles, buttons and numbers are UPPERCASE
  (`UPPERCASE_UI`); *Pixel Operator 8* (Jayvee Enaguas, CC0) has readable lowercase and is used for long texts.
  Fonts are never smoothed: they render at 8 px and are scaled by an integer, like everything else.
- **HUD** is drawn at the original resolution (128 asset pixels wide) and scaled by **the same integer as the board and cards**.
  It adapts to the available height (full / mid / tight layouts). Panel and fields are 9-slice, the button has 4 states.
  All HUD assets use the colours of `board.png`.
- To use your own drawings replace the files in `assets/hud/` (same sizes: `panel` 16×16, `inset` 12×12, `button` 4 × 12×12,
  `icons` 12×12 each in `ICON_ORDER`, `icons_audio` in `AUDIO_ICON_ORDER`). The tests compare the PNGs with the generator
  scripts, so if you draw them by hand, delete `test_hud_assets_match_the_generator_script` /
  `test_audio_icons_match_generator` or update the scripts.

## Extending

- **New card:** add `colour_type.png` (16×16) to `assets/sprites/` and list it in a family in `CARD_FAMILIES` (`config.py`).
  A family = cards that look alike (same shape, different colour); a board uses at most one card per family.
- **New mode:** subclass `Mode` in `core/levels.py`. **Levels:** `_build_catalog()` in `core/levels.py`.
- **Achievements:** `app.events` emits `round_started`, `move`, `undo`, `rescue`, `restart`, `round_won`, `run_finished`,
  `card_unlocked`, `achievement_unlocked`, `chain`; a store integration would hook a handler here.

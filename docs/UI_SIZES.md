# UI sizes (native pixels)

Everything is drawn at native resolution (1 px = 1 px of the art, cards are 16x16) and the whole screen is then
scaled by ONE integer (nearest neighbour). Scale = min(window_w // 320, window_h // 200) for menus;
the game screen picks its own integer scale so the board + HUD fit. Menu layouts are built to fit a
**320x200** native area at minimum (e.g. 1180x780 window -> x3 -> 393x260 native).
For a Photoshop/Aseprite artboard use **480x270** (16:9, scales x2 / x3 / x4 exactly); layouts only get more margin.

## Assets (what you draw)
| Asset | Size | Notes |
|---|---|---|
| panel | 16x16 | 9-slice, edge 6, centre 4x4 tiles |
| inset | 12x12 | 9-slice, edge 4 |
| button | 12x12 x 4 frames | normal, hover, pressed, disabled; 9-slice edge 4 (sheet 48x12) |
| icons | 12x12 x 8 | undo, rescue, restart, pause, moves, time, score, lock (sheet 96x12) |
| divider | 4x2 | |
| card sprites | 16x16 | |
| board | 193x217 | 10 columns x 12 rows (3 px frame, 3 px gaps; width = 19n+3, height = 16k+25) |
| font | 8 px grid | Public Pixel; 8 px text and 16 px (x2) titles |
| arrows (code) | 4x7 | drawn from a pixel pattern, no asset |

## Game screen
| Element | Size |
|---|---|
| HUD panel | 128 wide x board height; margin 8 |
| HUD buttons | 112x16, gap 3 |
| HUD stats box (moves/time/score) | 112x(3*12+8) = 112x44, row 12 |
| Win window | 168 wide, buttons 152x16 |
| Board (10x13) | 193x217 + HUD 128 = 321x217 |

## Other screens (native px)
| Screen | Element | Size |
|---|---|---|
| Menu | panel | 200x190 |
| | buttons | 128x16, gap 2 |
| | fruit strip | 9 cards: 174x22 |
| Level select | full panel | window - 12 (margin 6) |
| | tile | 52x(30..46) (42 at 320x200), gap 4, 5 per row |
| Custom | rows / buttons | 240x16, gap 3 |
| | info inset | 240x37 |
| Leaderboard | tab buttons | 84x16 |
| | table inset | panel - 16 wide; row 9..11 px |
| | columns | rank 2, name 12, score 6, level 3, time 5, moves 5 characters (8 px each) |
| Help | text inset | panel - 16; pages are packed automatically |
| Pause | panel | 184x130, buttons 112x16 |
| Confirm | panel | 280x110, buttons 128x16 |
| Name entry | panel | 260x108, input 124x18 |

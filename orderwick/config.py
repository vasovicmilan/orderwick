"""Game constants in one place."""
import os
import sys
from pathlib import Path

APP_NAME = "Orderwick"      # game name (window + menu title)
ORG_NAME = "orderwick"      # folder name for save data
APP_ID = "com.orderwick.game"   # macOS bundle id; change to a reverse-domain you own before publishing
AUTHOR_EMAIL = "vasovicmilanbiz@gmail.com"

# Online features (opt-in; see docs/ONLINE.md). Leave empty until the server has an address: the game then stays 100% offline
# and the Online screen says so. Set it here for a release build, or with the environment variable ORDERWICK_SERVER.
# Until there is a domain: running from source talks to the local server (npm start in orderwick-server). Packaged builds stay offline.
# ORDERWICK_SERVER=""  turns it off when running from source; ORDERWICK_SERVER=https://... points elsewhere.
LOCAL_SERVER = "http://127.0.0.1:3101"
PUBLIC_SERVER = "https://orderwick.com"          # packaged builds talk to the real server; running from source uses the local one
SERVER_URL = os.environ.get("ORDERWICK_SERVER", PUBLIC_SERVER if getattr(sys, "frozen", False) else LOCAL_SERVER)
ONLINE_CONSENT_VERSION = 2       # raise it when what is sent changes: everybody is asked again

# Developer mode (local testing only): everything unlocked, saves go to a separate "dev" folder, window title says DEV.
# Enable with:  python main.py --dev   (or ORDERWICK_DEV=1). It is always OFF in packaged (frozen) builds.
DEV = os.environ.get("ORDERWICK_DEV") == "1" and not getattr(sys, "frozen", False)

# in a PyInstaller build (frozen) resources sit next to the executable / in _MEIPASS
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ASSETS_DIR = ROOT_DIR / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"
UPPERCASE_UI = True   # the font is drawn for capital letters; lowercase is hard to read at 8 px
BODY_FONT_PATH = ASSETS_DIR / "fonts" / "PixelOperator8.ttf"   # CC0, upper + lower case, for longer texts
FONT_PATH = ASSETS_DIR / "fonts" / "PublicPixel.ttf"   # CC0, vidi assets/fonts/README.txt

# --- window ---------------------------------------------------------------
WINDOW_SIZE = (1180, 780)
MIN_WINDOW_SIZE = (900, 620)
FPS = 60

# --- pixel art ------------------------------------------------------------
CELL = 16          # size of one card in pixels (before scaling)
MAX_SCALE = 6
BOARD_IMAGE = "board/board.png"     # board template: 10 lanes x 12 rows (193 x 217)

# --- HUD (native resolution; scaled by the same factor as the board) -----------
HUD_WIDTH = 128                    # HUD width in asset pixels
HUD_PANEL = "hud/panel.png"        # 9-slice, rub 6 px
HUD_INSET = "hud/inset.png"        # 9-slice, rub 4 px
HUD_BUTTON = "hud/button.png"      # 4 stanja po 12x12, 9-slice, rub 4 px
HUD_ICONS = "hud/icons.png"        # 12x12 icons, same order as ICON_ORDER
ICON_CELL = 12
ICON_ORDER = ["undo", "rescue", "restart", "pause", "moves", "time", "score", "lock"]
BUTTON_STATES = ["normal", "hover", "pressed", "disabled"]

# --- colours (UI panel; the board and cards come from assets) ---------------------------
COLOR_BORDER = (88, 141, 190)
COLOR_BG = (18, 17, 28)
COLOR_PANEL = (28, 27, 42)
COLOR_TEXT = (235, 235, 245)
COLOR_DIM = (140, 140, 165)
COLOR_ACCENT = (255, 205, 80)
COLOR_GOOD = (90, 220, 130)
COLOR_BAD = (240, 90, 90)
COLOR_SELECT = (255, 205, 80)
COLOR_CURSOR = (90, 200, 255)
COLOR_WOOD = (90, 78, 68)           # colour of the wooden frame (from the board asset)
COLOR_CREAM = (250, 214, 184)
COLOR_TAN = (199, 176, 139)
COLOR_DARK_WOOD = (66, 57, 52)

# --- cards (file names in assets/sprites, without .png) ---------------------------
HIDDEN_SPRITE = "question_mark"      # hidden card
BLOCKED_SPRITE = "exclamation_mark"  # locked free slot

# Card types grouped into "families" of look-alikes (same shape, different colour).
# A board uses at most one type from each family, so cards stay easy to tell apart.
# Card file names are <colour>_<type>.png in assets/sprites; the FIRST card of a family is unlocked from the start.
LEGACY_FAMILY_KEYS = {"lump": "berry", "brownround": "round"}      # old saves (progress.json) are migrated
CARD_FAMILIES: dict[str, list[str]] = {
    "grape": ["purple_grape", "blue_grape", "green_grape", "orange_grape", "red_grape", "yellow_grape"],
    "apple": ["red_apple", "green_apple", "blue_apple", "yellow_apple", "orange_pumpkin"],
    "pear": ["red_pear", "green_pear", "blue_pear", "yellow_pear"],
    "cherry": ["red_cherry", "blue_cherry", "purple_cherry", "yellow_cherry"],
    "berry": ["red_berry", "green_berry", "blue_berry", "yellow_berry"],
    "curved": ["yellow_banana", "purple_eggplant", "yellow_eggplant", "green_eggplant"],
    "carrot": ["orange_carrot", "purple_carrot", "white_carrot"],
    "beet": ["purple_beet", "white_radish"],
    "round": ["brown_coconut", "brown_kiwi"],
    "dotted": ["tan_cookie", "orange_mango"],
    "sunflower": ["yellow_sunflower"],
    "watermelon": ["red_watermelon"],
}
MAX_TYPES = 9      # most types on one board (10 columns - 1 empty)

# --- tasteri ----------------------------------------------------------------
COL_KEYS = "1234567890"
FREE_KEYS = "asdfghjkl"

# --- game ---------------------------------------------------------------------
RESTART_PENALTY = 50
LEADERBOARD_SIZE = 10
NAME_MAX_LEN = 12

# --- card collection (unlocking) ----------------------------------------------------
# The first card of every family is unlocked from the start. The others unlock at thresholds of that family's "points".
# Points: +POINTS_PER_REVEAL for every revealed (turned over) card of the family, +POINTS_PER_SET for every type
# of that family that is sorted (column completed) when a board is solved.
POINTS_PER_REVEAL = 1
POINTS_PER_SET = 2
# threshold by number of locked cards in a family (locked = cards - 1)
UNLOCK_THRESHOLDS: dict[int, list[int]] = {
    1: [100],
    2: [50, 100],
    3: [25, 50, 100],
    4: [10, 25, 50, 100],
    5: [10, 25, 50, 100, 200],
}

# --- premium cards (rewards) -------------------------------------------------------------
# sprite name (assets/sprites/<name>.png) -> id of the achievement that unlocks it; e.g. {"gold_grape": "score_100k"}
# After unlocking, a premium card joins boards as a type of its own (like a new "family").
PREMIUM_CARDS: dict[str, str] = {}

# --- sound -------------------------------------------------------------------------------------
ICON_PATH = ASSETS_DIR / "icon" / "icon_32.png"      # window icon (see tools/make_icon.py)
AUDIO_DIR = ASSETS_DIR / "audio"
AUDIO_ICONS = "hud/icons_audio.png"
AUDIO_ICON_ORDER = ["music", "sound", "mute", "gear", "trophy", "cards"]
# Loudness per effect (multiplied by the global effects volume): "place" (moving a card) is the reference (0.8),
# pairing is much quieter, a completed column is the loudest (1.0).
SFX_GAIN = {"pick": 1.0, "place": 0.9, "pair": 0.42, "reveal": 0.8, "invalid": 1.0, "undo": 1.0, "rescue": 1.0,
            "win": 1.0, "column_done": 1.0, "unlock": 1.0, "achievement": 1.0, "ui_move": 0.8, "ui_click": 0.9,
            "ui_back": 0.95, "restart": 0.95}
DEFAULT_SETTINGS = {"music_on": True, "music_vol": 50, "sfx_on": True, "sfx_vol": 90,
                    "board_theme": "wood", "card_style": "classic"}

# --- looks (unlockable cosmetics) ----------------------------------------------------------------
# A BOARD THEME restyles the board AND the HUD, dialogs and menus: assets/themes/<id>/ may contain board/board.png and
# hud/{panel,inset,button,divider,icons,icons_audio}.png; any file that is missing falls back to the default theme.
# A CARD STYLE is a full set of card sprites with another background: assets/card_styles/<id>/<card>.png; missing files fall
# back to the classic card.   Entry = (id, display name, unlock rule); the first entry of each list is the default.
# Unlock rule: None = always, "all_trophies" = every achievement, or an achievement id (see core/achievements.py).
THEMES_DIR = ASSETS_DIR / "themes"
CARD_STYLES_DIR = ASSETS_DIR / "card_styles"
BOARD_THEMES = [("wood", "Wood", None), ("emerald", "Emerald", "all_trophies")]
CARD_STYLES = [("classic", "Classic", None), ("gold", "Gold", "score_100k")]

# --- about / author (About screen) -----------------------------------------------------------
VERSION = "0.2.0"
AUTHOR_NAME = "Milan Vasovic"
# (button label, URL). Buttons with example.com are hidden until you enter real addresses.
LINKS: list[tuple[str, str]] = [
    ("Contact", "mailto:vasovicmilanbiz@gmail.com"),
    ("Website", "https://example.com"),
    ("itch.io page", "https://example.com/itch"),
]
CREDITS = [
    "Fonts: Public Pixel (GGBotNet) and Pixel Operator 8 (Jayvee Enaguas), both CC0.",
    "Music and sound effects are generated in code for this game.",
    "Made with Python and pygame-ce.",
]

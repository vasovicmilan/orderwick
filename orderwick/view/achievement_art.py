"""Achievement art: assets/achievements/<id>.png (16x16 by convention). If missing, a placeholder icon is drawn."""
from __future__ import annotations

import pygame

from .. import config
from ..core.achievements import BY_ID

SIZE = 16
PLACEHOLDER_CARDS = ["purple_grape", "red_apple", "red_pear", "red_cherry", "red_berry", "yellow_banana", "orange_carrot",
                     "purple_beet", "brown_coconut", "orange_mango", "yellow_sunflower", "red_watermelon"]


def _placeholder(assets, ach_id: str) -> pygame.Surface:
    """Placeholder icon: a gold tile with a card from the game (stable per id)."""
    surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    surf.fill(config.COLOR_DARK_WOOD)
    pygame.draw.rect(surf, config.COLOR_ACCENT, surf.get_rect(), 1)
    names = list(BY_ID)
    # achievements added later on the server have no local entry: pick a stable card from the id itself
    index = names.index(ach_id) if ach_id in BY_ID else sum(ord(ch) for ch in ach_id)
    card = PLACEHOLDER_CARDS[index % len(PLACEHOLDER_CARDS)]
    small = assets.sprite(card)
    surf.blit(small, ((SIZE - small.get_width()) // 2, (SIZE - small.get_height()) // 2))
    return surf


def achievement_icon(assets, ach_id: str, locked: bool = False) -> pygame.Surface:
    if locked:
        return assets.sprite(config.HIDDEN_SPRITE)
    key = f"ach:{ach_id}"
    surf = assets._sprites.get(key)
    if surf is None:
        path = config.ASSETS_DIR / "achievements" / f"{ach_id}.png"
        if path.exists():
            surf = pygame.image.load(str(path)).convert_alpha()
            if surf.get_size() != (SIZE, SIZE):                 # different size: scale to 16x16 (nearest)
                surf = pygame.transform.scale(surf, (SIZE, SIZE))
        else:
            surf = _placeholder(assets, ach_id)
        assets._sprites[key] = surf
    return surf

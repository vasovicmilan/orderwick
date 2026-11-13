# Card file names

Format: **`<colour>_<type>.png`** in `assets/sprites/` (lowercase, one underscore, 16×16). The first card of every family is unlocked
from the start. Special sprites: `question_mark.png` (hidden card), `exclamation_mark.png` (locked free slot).

| Family | Cards (first = unlocked at the start) |
|---|---|
| grape | purple_grape, blue_grape, green_grape, orange_grape, red_grape, yellow_grape |
| apple | red_apple, green_apple, blue_apple, yellow_apple, orange_pumpkin |
| pear | red_pear, green_pear, blue_pear, yellow_pear |
| cherry | red_cherry, blue_cherry, purple_cherry, yellow_cherry |
| berry | red_berry, green_berry, blue_berry, yellow_berry |
| curved | yellow_banana, purple_eggplant, yellow_eggplant, green_eggplant |
| carrot | orange_carrot, purple_carrot, white_carrot |
| beet | purple_beet, white_radish |
| round | brown_coconut, brown_kiwi |
| dotted | tan_cookie, orange_mango |
| sunflower | yellow_sunflower |
| watermelon | red_watermelon |

## Old name → new name (for your own source files)
| Old | New | Old | New |
|---|---|---|---|
| grape | purple_grape | pumkin | orange_pumpkin |
| grapeblue | blue_grape | peerred | red_pear |
| grapegreen | green_grape | peergreen | green_pear |
| grapeorange | orange_grape | peerblue | blue_pear |
| grapered | red_grape | peeryellow | yellow_pear |
| grapeyellow | yellow_grape | chary | red_cherry |
| redapple | red_apple | charyblue | blue_cherry |
| greenapple | green_apple | charypurple | purple_cherry |
| blueapple | blue_apple | charyyellow | yellow_cherry |
| yelllowapple | yellow_apple | redberry | red_berry |
| greenbery | green_berry | buleberry | blue_berry |
| yellowbery | yellow_berry | bannana | yellow_banana |
| eggplant | purple_eggplant | eggplanteyellow | yellow_eggplant |
| eggplantgreen | green_eggplant | carrot | orange_carrot |
| carrotpurple | purple_carrot | carrotwhite | white_carrot |
| beets | purple_beet | raddishwhite | white_radish |
| coconout | brown_coconut | kiwi | brown_kiwi |
| coockie | tan_cookie | mango | orange_mango |
| sunflower | yellow_sunflower | wattermallon | red_watermelon |
| questionmark | question_mark | exclamationmark | exclamation_mark |

Saved data note: the families `lump` and `brownround` were renamed to `berry` and `round`; old `progress.json` files are migrated automatically.

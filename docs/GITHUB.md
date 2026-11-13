# GitHub repository

**Name:** `orderwick`
**Visibility:** private (the game is proprietary, see `LICENSE.txt`)

**Short description (the "About" box, max 350 characters):**
> Orderwick – a cozy pixel-art card-sorting puzzle for Windows, Linux and macOS. Python + pygame-ce. Campaign, hard mode, trophies, unlockable card collection, board themes and card styles; built to grow with new card families and expansions.

**Topics:** `game` `puzzle-game` `card-game` `sorting` `pixel-art` `pygame` `pygame-ce` `python` `indie-game` `pyinstaller` `itch-io`

**Website:** leave empty until the store page exists.

## First push
    cd orderwick
    git init -b main
    git add .
    git commit -m "Initial commit"
    git remote add origin git@github.com:<your-user>/orderwick.git
    git push -u origin main

Before the first commit check `git status`: there must be no `dist/`, `build/`, `__pycache__/`, `*.raw` or `crash.log`
(`.gitignore` covers them). The `export/` and `assets/aseprite/` folders are sources and belong in the repository.

## Suggested files on GitHub
`README.md` (already there), `LICENSE.txt` (proprietary), `.github/workflows/build.yml` (builds Windows, Linux and both macOS versions when you push a tag `v*`, and publishes a Release).

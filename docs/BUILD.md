# Building Orderwick locally (Windows / Linux / macOS)

PyInstaller (`onedir`) makes a folder with the game, Python and all libraries inside. It cannot cross-compile: build on the
operating system you want to ship for (or let GitHub Actions do all three, see the end).

## 0. Requirements
* **Python 3.12 or 3.13** (3.10+ works) from python.org (Windows/macOS) or your package manager (Linux).
* **Git** (only to clone the repository).
* Linux only: `sudo apt install python3-venv python3-dev libsdl2-2.0-0` (SDL itself comes bundled with pygame-ce, the
  system packages are only a safety net).

## 1. Get the source and make a clean environment
    git clone https://github.com/<your-user>/orderwick.git
    cd orderwick
    python3 -m venv .venv

Activate it:
* Linux / macOS: `source .venv/bin/activate`
* Windows (PowerShell): `.venv\Scripts\Activate.ps1`  (if scripts are blocked: `Set-ExecutionPolicy -Scope Process Bypass`)
* Windows (cmd): `.venv\Scripts\activate.bat`

Install what is needed (the game needs only pygame-ce; the rest is for building):

    pip install -r requirements.txt
    pip install pyinstaller pillow

## 2. Check that it runs
    python3 main.py                   # play
    python3 main.py --dev             # developer mode: everything unlocked, separate save folder, [DEV] in the title
    python3 main.py --no-audio        # without sound
    python3 main.py --selftest        # headless check: loads every asset, draws every screen
    python3 -m unittest discover -s tests -q

## 3. Build
    python packaging/build.py

What it does: makes the icons, runs PyInstaller with `packaging/Orderwick.spec`, starts the finished build with `--selftest`,
copies EULA / LICENSE / THIRD_PARTY_NOTICES / licenses next to the game and packs the result:

| System  | Result |
|---------|--------|
| Windows | `dist/Orderwick-0.2.0-windows.zip` (folder `Orderwick/` with `Orderwick.exe`) |
| Linux   | `dist/Orderwick-0.2.0-linux.tar.gz` (folder `Orderwick/` with the `Orderwick` binary) |
| macOS   | `dist/Orderwick-0.2.0-macos-arm64.zip` or `...-macos-x64.zip` (`Orderwick.app`) |

Run it from the unpacked folder, not from inside the archive. The version comes from `VERSION` in `orderwick/config.py`.

## 4. Release checklist
1. Raise `VERSION` in `orderwick/config.py`.
2. Replace the placeholder links in `LINKS` (`example.com` entries are hidden until you enter real addresses) and, if you
   plan to publish on macOS, `APP_ID` (reverse-domain you own, also used by `Orderwick.spec`).
3. `python -m unittest discover -s tests -q` must pass, `python packaging/build.py` must end with `selftest OK`.
4. Start the built game once by hand: window, icon, sound, F11, closing with X. A developer-mode switch (`--dev`) does not exist in packaged builds.
5. Tag and push (`git tag v0.1.0 && git push --tags`): GitHub Actions builds all three systems.

## Per-system notes
* **Windows:** an unsigned .exe triggers SmartScreen and sometimes an antivirus false alarm (that is why `onedir`, not `onefile`).
  Signing needs a code-signing certificate; on itch.io, players install through the itch app or a plain zip. Optional: an Inno Setup installer.
* **Linux:** a build made on ubuntu-22.04 runs on newer distributions too; it runs on most current distributions.
* **macOS:** an `.app` without Apple signing and notarization is blocked by Gatekeeper (right-click > Open). For a real
  release you need an Apple Developer account + `codesign` + `notarytool`. The `macos-latest` runner builds arm64;
  Intel/universal needs another runner.
* Player data (progress, settings, scores, `crash.log`) lives in the user's folder, not in the game folder:
  Windows `%APPDATA%\orderwick\Orderwick`, Linux `~/.local/share/orderwick/Orderwick`, macOS `~/Library/Application Support/orderwick/Orderwick`.
  Override with `ORDERWICK_HOME=/some/folder`. To get a *clean instance* (as a new player) delete that folder or point `ORDERWICK_HOME` to an empty one.

## What was verified
* **Linux:** build, `--selftest` and starting the frozen game with its sound process were run.
* **Windows and macOS:** the spec/script are prepared but were never run here. Check the first build by hand.

## Sound runs in its own process
All audio (mixer, music, effects) lives in a separate process (`orderwick/audio_worker.py`). A crash or hang inside the native
audio libraries cannot take the game down: the game notices the worker is gone, logs it to `crash.log` and continues silently.
On exit the game ends the worker (politely, then by force). Switches: `ORDERWICK_AUDIO=off`, `ORDERWICK_AUDIO=inproc`
(debugging only), `--no-audio`. Frozen builds need `multiprocessing.freeze_support()` (already in `main.py`) and the hidden
import in `packaging/Orderwick.spec`.

## Alternatives
Nuitka (faster start, harder to decompile, slower to build), briefcase, cx_Freeze.


## 5. GitHub Actions (all systems, no local build)
`.github/workflows/build.yml` runs the unit tests, then builds **Windows, Linux, macOS Apple silicon and macOS Intel**.
The Linux build is also started in a virtual screen and plays one board with `--agent`, so a broken package is caught.

* **Release:** `git tag v0.2.0 && git push origin v0.2.0` -> a GitHub Release with the four files appears (Releases page).
* **Test run without a release:** Actions -> build -> Run workflow; download the files from the run page (kept 30 days).
* **itch.io, by hand:** download the files from the Release and upload them on the itch.io page, one per platform.
* **itch.io, automatic (optional):** repository Settings -> Secrets and variables -> Actions: secret `BUTLER_API_KEY`
  (itch.io -> Settings -> API keys) and variable `ITCH_TARGET` = `yourname/orderwick`. Channels: windows, linux, mac-arm64, mac-x64.
* Optional server upload: secrets `ORDERWICK_URL` and `ORDERWICK_ADMIN_TOKEN`.

The builds are unsigned. Windows SmartScreen: "More info" -> "Run anyway". macOS: after unzipping run
`xattr -dr com.apple.quarantine Orderwick.app` once (or right-click -> Open). Linux: `chmod +x Orderwick/Orderwick` if needed.

## 6. Claude's player (`--agent`)
The game contains a player that presses the real keys like a human (visible cards only, undo, rescue, loop protection):

    Orderwick --agent --mode hard --boards 3 --server https://orderwick.com --key OW-XXXX-XXXX-XXXX --nick Claude_AI

It needs a Linux machine with a screen (or `xvfb-run`). To let Claude play and record: send Claude the Linux build
(`Orderwick-<version>-linux.tar.gz`) and an activation key from your own account page on the website. Options: `--help`.

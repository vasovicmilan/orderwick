# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: `pyinstaller packaging/Orderwick.spec --noconfirm` (from the project root)
# Produces the folder dist/Orderwick/ (Windows/Linux) or dist/Orderwick.app (macOS). onedir is better than onefile:
# it starts faster, triggers fewer antivirus false alarms, and the LGPL libraries (SDL/pygame-ce) stay separate files.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))
from orderwick import config   # noqa: E402  (APP_ID = macOS bundle id)
APP = "Orderwick"
SKIP_DIRS = {"aseprite", "_reference"}                 # source files for drawing, the game does not need them
SKIP_FILES = {"icon_16.png", "icon_48.png", "icon_64.png", "icon_128.png", "icon_256.png", "icon_512.png",
              "icon_1024.png", "icon.ico", "icon.icns"}  # only icon_32.png (the window icon) stays

datas = []
for path in (ROOT / "assets").rglob("*"):
    if path.is_dir() or SKIP_DIRS & set(path.relative_to(ROOT / "assets").parts) or path.name in SKIP_FILES:
        continue
    datas.append((str(path), str(path.parent.relative_to(ROOT))))
for doc in ("LICENSE.txt", "EULA.txt", "THIRD_PARTY_NOTICES.txt"):
    if (ROOT / doc).exists():
        datas.append((str(ROOT / doc), "."))
for path in (ROOT / "licenses").rglob("*"):                     # license texts ship with every build
    if path.is_file():
        datas.append((str(path), str(path.parent.relative_to(ROOT))))

icon = None
if sys.platform == "win32":
    icon = str(ROOT / "assets" / "icon" / "icon.ico")
elif sys.platform == "darwin":
    icon = str(ROOT / "assets" / "icon" / "icon.icns")

a = Analysis([str(ROOT / "main.py")], pathex=[str(ROOT)], datas=datas, hiddenimports=["orderwick.audio_worker", "orderwick.agent_player", "orderwick.agent_run"],
             excludes=["numpy", "scipy", "PIL", "tkinter", "unittest", "pydoc", "test"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP, console=False, icon=icon, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
if sys.platform == "darwin":
    app = BUNDLE(coll, name=f"{APP}.app", icon=icon, bundle_identifier=config.APP_ID,
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": config.VERSION})

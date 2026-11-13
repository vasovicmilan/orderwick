"""Build for the CURRENT operating system (PyInstaller cannot build for another OS):

    pip install -r requirements.txt pyinstaller
    python packaging/build.py

Result: dist/Orderwick-<version>-<os>.zip (.tar.gz on Linux). To build all three systems at once use
.github/workflows/build.yml (GitHub Actions runs the build on Windows, Linux and macOS machines).
"""
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from orderwick import config  # noqa: E402


def main() -> None:
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], check=True, cwd=ROOT, env=env)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "packaging/Orderwick.spec", "--noconfirm"], check=True, cwd=ROOT, env=env)
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64", "AMD64": "x64"}.get(platform.machine(), platform.machine())
    # macOS exists for two processors (Apple silicon and Intel), so its file name says which one
    name = f"Orderwick-{config.VERSION}-{system}" + (f"-{arch}" if system == "macos" else "")
    dist = ROOT / "dist"
    target = dist / ("Orderwick.app" if system == "macos" else "Orderwick")
    if system != "macos":                                  # legal documents next to the game (not only inside _internal)
        for doc in ("LICENSE.txt", "EULA.txt", "THIRD_PARTY_NOTICES.txt"):
            shutil.copy(ROOT / doc, target / doc)
        shutil.copytree(ROOT / "licenses", target / "licenses", dirs_exist_ok=True)
    # check that the build works before packaging it
    exe = (target / "Contents" / "MacOS" / "Orderwick") if system == "macos" else target / ("Orderwick.exe" if system == "windows" else "Orderwick")
    # Output is captured: a windowed Windows exe has no console of its own, and a hang must end with a message, not run for hours.
    try:
        res = subprocess.run([str(exe), "--selftest"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=150)
    except subprocess.TimeoutExpired as exc:
        print("SELFTEST TIMEOUT\n", exc.stdout or "", exc.stderr or "")
        raise SystemExit(1)
    print(res.stdout, res.stderr)
    if res.returncode != 0:
        raise SystemExit(f"selftest failed with code {res.returncode}")
    if system == "linux":
        with tarfile.open(dist / f"{name}.tar.gz", "w:gz") as tar:
            tar.add(target, arcname="Orderwick")
    else:
        shutil.make_archive(str(dist / name), "zip", dist, target.name)
    print("done:", dist / name)


if __name__ == "__main__":
    main()

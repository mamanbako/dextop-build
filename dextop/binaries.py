"""Téléchargement et gestion des binaires scrcpy/ADB."""
from __future__ import annotations

import os
import platform
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SCRCPY_VERSION = "3.1"
BIN_DIR = Path(__file__).parent.parent / "bin"

SCRCPY_URLS = {
    "windows": f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-win64-v{SCRCPY_VERSION}.zip",
    "linux": f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-linux-x86_64-v{SCRCPY_VERSION}.tar.gz",
    "darwin": f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-macos-aarch64-v{SCRCPY_VERSION}.tar.gz",
}
ADB_URLS = {
    "windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
    "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
}


def _platform_key() -> str:
    key = platform.system().lower()
    return "darwin" if key == "darwin" else ("windows" if key == "windows" else "linux")


def _download_and_extract(url: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / Path(url).name
    urllib.request.urlretrieve(url, archive)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(dest)
    archive.unlink()


def _flatten(root: Path) -> None:
    for pattern in ("scrcpy*", "adb*"):
        for p in root.rglob(pattern):
            if p.is_file() and p.parent != root:
                target = root / p.name
                if not target.exists():
                    p.rename(target)
                if os.name != "nt":
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)


def ensure_binaries(progress_cb=None) -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    plat = _platform_key()
    scrcpy_bin = BIN_DIR / ("scrcpy.exe" if plat == "windows" else "scrcpy")
    adb_bin = BIN_DIR / ("adb.exe" if plat == "windows" else "adb")
    if scrcpy_bin.exists() and adb_bin.exists():
        return
    if progress_cb:
        progress_cb("Téléchargement de scrcpy…")
    _download_and_extract(SCRCPY_URLS[plat], BIN_DIR)
    if progress_cb:
        progress_cb("Téléchargement d'ADB…")
    _download_and_extract(ADB_URLS[plat], BIN_DIR)
    _flatten(BIN_DIR)
    if progress_cb:
        progress_cb("Binaires prêts.")

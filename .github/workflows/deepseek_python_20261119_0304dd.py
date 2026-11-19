# dextop/binaries.py (version améliorée)
import os
import platform
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

BIN_DIR = Path(__file__).parent.parent / "bin"
SCRCPY_VERSION = "5.0.1"  # Dernière version stable (Oct 2026)[reference:9]

# URLs officielles
SCRCPY_URLS = {
    "windows": f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-win64-v{SCRCPY_VERSION}.zip",
    "linux":   f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-linux-x86_64-v{SCRCPY_VERSION}.tar.gz",
    "darwin":  f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-macos-v{SCRCPY_VERSION}.tar.gz",
}

ADB_URLS = {
    "windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "linux":   "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
    "darwin":  "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
}

def _platform_key() -> str:
    key = platform.system().lower()
    if key == "darwin":
        return "darwin"
    if key == "windows":
        return "windows"
    return "linux"

def _download_and_extract(url: str, dest: Path) -> None:
    """Télécharge une archive et l'extrait dans dest/."""
    archive = dest / Path(url).name
    urllib.request.urlretrieve(url, archive)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:  # tar.gz
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(dest)
    archive.unlink()

def _move_binaries_to_root(root: Path) -> None:
    """Aplatit l'arborescence : déplace les exécutables à la racine de bin/."""
    for pattern in ("scrcpy*", "adb*", "scrcpy-server*"):
        for p in root.rglob(pattern):
            if p.is_file() and p.parent != root:
                target = root / p.name
                if not target.exists():
                    p.rename(target)
                # Rend exécutable sous Unix
                if os.name != "nt":
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)

def ensure_binaries() -> None:
    """Télécharge scrcpy et adb si absents de ./bin/."""
    BIN_DIR.mkdir(exist_ok=True)
    plat = _platform_key()

    scrcpy_bin = BIN_DIR / ("scrcpy.exe" if plat == "windows" else "scrcpy")
    adb_bin = BIN_DIR / ("adb.exe" if plat == "windows" else "adb")
    server_jar = BIN_DIR / "scrcpy-server"

    if scrcpy_bin.exists() and adb_bin.exists() and server_jar.exists():
        return  # Déjà prêts

    print(f"[dextop] Téléchargement des binaires pour {plat}…")
    _download_and_extract(SCRCPY_URLS[plat], BIN_DIR)
    _download_and_extract(ADB_URLS[plat], BIN_DIR)
    _move_binaries_to_root(BIN_DIR)
    print("[dextop] Binaires prêts.")
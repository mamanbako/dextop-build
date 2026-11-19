# dextop/binaries.py
import os
import platform
import stat
import urllib.request
import zipfile
from pathlib import Path

BIN_DIR = Path(__file__).parent.parent / "bin"
SCRCPY_VERSION = "3.1"  # Adapte à la dernière version stable

def get_platform_info():
    system = platform.system().lower()
    if system == "windows":
        return "windows", "zip", f"scrcpy-win64-v{SCRCPY_VERSION}.zip"
    elif system == "linux":
        return "linux", "tar.gz", f"scrcpy-linux-x86_64-v{SCRCPY_VERSION}.tar.gz"
    elif system == "darwin":
        return "macos", "tar.gz", f"scrcpy-macos-v{SCRCPY_VERSION}.tar.gz"
    raise OSError(f"Plateforme non supportée: {system}")

def ensure_binaries():
    """Télécharge scrcpy et adb si absents de ./bin/."""
    BIN_DIR.mkdir(exist_ok=True)
    scrcpy_bin = BIN_DIR / ("scrcpy.exe" if os.name == "nt" else "scrcpy")
    adb_bin = BIN_DIR / ("adb.exe" if os.name == "nt" else "adb")
    server_jar = BIN_DIR / "scrcpy-server"

    if scrcpy_bin.exists() and adb_bin.exists() and server_jar.exists():
        return  # Déjà prêts

    print("[dextop] Téléchargement des binaires…")
    # 1. Télécharger scrcpy (inclut scrcpy-server)
    os_name, archive_type, filename = get_platform_info()
    url = f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/{filename}"
    archive_path = BIN_DIR / filename
    urllib.request.urlretrieve(url, archive_path)

    # 2. Extraire
    if archive_type == "zip":
        with zipfile.ZipFile(archive_path, 'r') as z:
            z.extractall(BIN_DIR)
    else:
        import tarfile
        with tarfile.open(archive_path, 'r:gz') as t:
            t.extractall(BIN_DIR)

    # 3. Aplatir l'arborescence et rendre exécutable
    for p in BIN_DIR.rglob("scrcpy*"):
        if p.is_file():
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
    # ... (logique pour déplacer les fichiers à la racine de BIN_DIR)

    # 4. Télécharger adb (Android Platform Tools)
    # ... (similaire, depuis dl.google.com)

    print("[dextop] Binaires prêts.")
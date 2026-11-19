#!/usr/bin/env bash
set -e
ROOT="dextop-repo"
rm -rf "$ROOT" && mkdir -p "$ROOT"/{dextop,resources} "$ROOT"/.github/workflows
cd "$ROOT"

# ─── .github/workflows/build-release.yml ──────────────────────────
cat > .github/workflows/build-release.yml <<'YML'
name: Build & Release DeXtop

on:
  push:
    tags: ["v*.*.*"]
  workflow_dispatch:
    inputs:
      version:
        description: "Version à publier (ex: v0.1.0)"
        required: true
        default: "v0.0.0"

permissions:
  contents: write

jobs:
  prepare:
    name: Préparer la version
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.version }}
      is_prerelease: ${{ steps.version.outputs.is_prerelease }}
    steps:
      - name: Déterminer la version
        id: version
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            VERSION="${{ github.event.inputs.version }}"
          else
            VERSION="${GITHUB_REF#refs/tags/}"
          fi
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          if [[ "$VERSION" == *"-alpha"* || "$VERSION" == *"-beta"* || "$VERSION" == *"-rc"* ]]; then
            echo "is_prerelease=true" >> "$GITHUB_OUTPUT"
          else
            echo "is_prerelease=false" >> "$GITHUB_OUTPUT"
          fi

  build-windows:
    name: Build Windows
    needs: prepare
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Installer les dépendances
        run: |
          python -m pip install --upgrade pip
          pip install customtkinter pyinstaller
      - name: Télécharger scrcpy + adb
        shell: pwsh
        run: python -c "from dextop.binaries import ensure_binaries; ensure_binaries()"
      - name: PyInstaller
        run: pyinstaller dextop.spec --clean --noconfirm
      - name: Inno Setup
        run: choco install innosetup --yes --no-progress
      - name: Compiler l'installateur
        shell: pwsh
        run: |
          $v = "${{ needs.prepare.outputs.version }}" -replace '^v',''
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DMyAppVersion=$v" dextop.iss
      - uses: actions/upload-artifact@v4
        with:
          name: windows-${{ needs.prepare.outputs.version }}
          path: |
            dist/DeXtop.exe
            installer/output/DeXtop-Setup-*.exe
          if-no-files-found: error

  build-linux:
    name: Build Linux
    needs: prepare
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Dépendances
        run: |
          sudo apt-get update
          sudo apt-get install -y libfuse2 file wget
          pip install customtkinter pyinstaller
      - name: Télécharger scrcpy + adb
        run: python -c "from dextop.binaries import ensure_binaries; ensure_binaries()"
      - name: PyInstaller
        run: pyinstaller dextop.spec --clean --noconfirm
      - name: Rendre exécutable
        run: chmod +x dist/DeXtop
      - name: AppImage
        env:
          VERSION: ${{ needs.prepare.outputs.version }}
        run: |
          chmod +x build_appimage.sh
          ./build_appimage.sh
      - uses: actions/upload-artifact@v4
        with:
          name: linux-${{ needs.prepare.outputs.version }}
          path: |
            dist/DeXtop
            dist/DeXtop-*.AppImage
          if-no-files-found: error

  build-macos:
    name: Build macOS
    needs: prepare
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Dépendances
        run: pip install customtkinter pyinstaller
      - name: Télécharger scrcpy + adb
        run: python -c "from dextop.binaries import ensure_binaries; ensure_binaries()"
      - name: PyInstaller
        run: pyinstaller dextop.spec --clean --noconfirm
      - name: Rendre exécutable
        run: chmod +x dist/DeXtop
      - name: Zipper
        run: cd dist && zip -r "DeXtop-macos-${{ needs.prepare.outputs.version }}.zip" DeXtop
      - uses: actions/upload-artifact@v4
        with:
          name: macos-${{ needs.prepare.outputs.version }}
          path: dist/DeXtop-macos-*.zip
          if-no-files-found: error

  release:
    name: Créer la Release GitHub
    needs: [prepare, build-windows, build-linux, build-macos]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/') || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
          pattern: "*-${{ needs.prepare.outputs.version }}"
      - run: find artifacts -type f -exec ls -lh {} \;
      - uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ needs.prepare.outputs.version }}
          name: "DeXtop ${{ needs.prepare.outputs.version }}"
          draft: false
          prerelease: ${{ needs.prepare.outputs.is_prerelease == 'true' }}
          generate_release_notes: true
          files: |
            artifacts/**/DeXtop.exe
            artifacts/**/DeXtop-Setup-*.exe
            artifacts/**/DeXtop
            artifacts/**/DeXtop-*.AppImage
            artifacts/**/DeXtop-macos-*.zip
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
YML

# ─── dextop/__init__.py ───────────────────────────────────────────
cat > dextop/__init__.py <<'PY'
"""DeXtop — Desktop mode for Android via scrcpy."""
__version__ = "0.1.0"
PY

# ─── main.py (entry point) ────────────────────────────────────────
cat > main.py <<'PY'
from dextop.gui import run

if __name__ == "__main__":
    run()
PY

# ─── dextop/gui.py ────────────────────────────────────────────────
cat > dextop/gui.py <<'PY'
# dextop/gui.py
import threading
import customtkinter as ctk
from tkinter import messagebox

from dextop.orchestrator import (
    ScrcpyOrchestrator, DisplayConfig, ConnectionConfig, SessionState,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DeXtopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DeXtop — Desktop mode via scrcpy")
        self.geometry("720x560")
        self.orch = ScrcpyOrchestrator(
            on_state_change=self._on_state,
            on_log=self._on_log,
        )
        self._build_ui()
        self._refresh_devices()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(top, text="Appareil :").pack(side="left", padx=(8, 4))
        self.device_var = ctk.StringVar(value="")
        self.device_menu = ctk.CTkOptionMenu(top, variable=self.device_var, values=["—"])
        self.device_menu.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(top, text="↻", width=36, command=self._refresh_devices).pack(side="left")

        params = ctk.CTkFrame(self)
        params.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(params, text="Résolution :").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.width_entry = ctk.CTkEntry(params, width=80)
        self.width_entry.insert(0, "1920")
        self.width_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(params, text="×").grid(row=0, column=2)
        self.height_entry = ctk.CTkEntry(params, width=80)
        self.height_entry.insert(0, "1080")
        self.height_entry.grid(row=0, column=3, padx=4)
        ctk.CTkLabel(params, text="DPI :").grid(row=0, column=4, padx=8)
        self.dpi_entry = ctk.CTkEntry(params, width=80)
        self.dpi_entry.insert(0, "240")
        self.dpi_entry.grid(row=0, column=5, padx=4)
        ctk.CTkLabel(params, text="App (optionnel) :").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.app_entry = ctk.CTkEntry(params, placeholder_text="com.android.settings")
        self.app_entry.grid(row=1, column=1, columnspan=5, sticky="ew", padx=4)

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=12, pady=8)
        self.start_btn = ctk.CTkButton(actions, text="▶ Démarrer", command=self._start)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ctk.CTkButton(actions, text="■ Arrêter", command=self._stop,
                                     state="disabled", fg_color="#8b1e1e")
        self.stop_btn.pack(side="left", padx=4)

        self.log_box = ctk.CTkTextbox(self, height=240)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _refresh_devices(self):
        try:
            devices = self.orch.list_devices()
        except Exception as e:
            devices = [f"erreur: {e}"]
        values = devices or ["—"]
        self.device_menu.configure(values=values)
        self.device_var.set(values[0])

    def _start(self):
        try:
            display = DisplayConfig(
                width=int(self.width_entry.get()),
                height=int(self.height_entry.get()),
                dpi=int(self.dpi_entry.get()),
                start_app=self.app_entry.get().strip() or None,
            )
            serial = self.device_var.get()
            connection = ConnectionConfig(serial=serial if serial != "—" else None)
            self.orch.start(display, connection)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _stop(self):
        threading.Thread(target=self.orch.stop, daemon=True).start()

    def _on_state(self, state: SessionState):
        def update():
            running = state in (SessionState.RUNNING, SessionState.STARTING)
            self.start_btn.configure(state="disabled" if running else "normal")
            self.stop_btn.configure(state="normal" if running else "disabled")
            self.title(f"DeXtop — {state.value}")
        self.after(0, update)

    def _on_log(self, line: str):
        def update():
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
        self.after(0, update)


def run():
    app = DeXtopApp()
    app.mainloop()


if __name__ == "__main__":
    run()
PY

# ─── dextop/orchestrator.py ───────────────────────────────────────
cat > dextop/orchestrator.py <<'PY'
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class SessionState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"


@dataclass
class DisplayConfig:
    width: int = 1920
    height: int = 1080
    dpi: int = 240
    flex_display: bool = True
    hide_system_decorations: bool = True
    start_app: Optional[str] = None
    extra_args: list[str] = field(default_factory=list)

    def to_scrcpy_args(self) -> list[str]:
        args = ["--new-display", f"{self.width}x{self.height}/{self.dpi}"]
        if self.flex_display:
            args.append("--flex-display")
        if self.hide_system_decorations:
            args.append("--no-vd-system-decorations")
        if self.start_app:
            args.extend(["--start-app", self.start_app])
        args.extend(self.extra_args)
        return args


@dataclass
class ConnectionConfig:
    serial: Optional[str] = None
    bitrate: str = "8M"
    max_fps: int = 60
    audio: bool = True
    audio_codec: str = "opus"
    stay_awake: bool = True
    turn_screen_off: bool = True

    def to_scrcpy_args(self) -> list[str]:
        args: list[str] = []
        if self.serial:
            args.extend(["--serial", self.serial])
        args.extend(["--video-bit-rate", self.bitrate])
        args.extend(["--max-fps", str(self.max_fps)])
        args.extend(["--audio-codec", self.audio_codec] if self.audio else ["--no-audio"])
        if self.stay_awake:
            args.append("--stay-awake")
        if self.turn_screen_off:
            args.append("--turn-screen-off")
        return args


def _bin_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "bin"
    return Path(__file__).parent.parent / "bin"


class ScrcpyOrchestrator:
    def __init__(
        self,
        scrcpy_path: Optional[str] = None,
        adb_path: Optional[str] = None,
        on_state_change: Optional[Callable[[SessionState], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self.scrcpy_path = scrcpy_path or self._find_binary("scrcpy")
        self.adb_path = adb_path or self._find_binary("adb")
        self._on_state = on_state_change or (lambda s: None)
        self._on_log = on_log or (lambda line: None)
        self._process: Optional[subprocess.Popen] = None
        self._state = SessionState.IDLE
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None

    @staticmethod
    def _find_binary(name: str) -> str:
        exe = name + (".exe" if os.name == "nt" else "")
        local = _bin_dir() / exe
        if local.exists():
            return str(local)
        found = shutil.which(name)
        if not found:
            raise FileNotFoundError(
                f"Binaire '{name}' introuvable. Place-le dans ./bin/ ou ajoute-le au PATH."
            )
        return found

    @property
    def state(self) -> SessionState:
        return self._state

    def _set_state(self, new_state: SessionState) -> None:
        with self._lock:
            self._state = new_state
        self._on_state(new_state)

    def list_devices(self) -> list[str]:
        result = subprocess.run(
            [self.adb_path, "devices"],
            capture_output=True, text=True, timeout=10
        )
        devices = []
        for line in result.stdout.splitlines()[1:]:
            if "\tdevice" in line:
                devices.append(line.split("\t")[0])
        return devices

    def build_command(self, display: DisplayConfig, connection: ConnectionConfig) -> list[str]:
        cmd = [self.scrcpy_path]
        cmd += connection.to_scrcpy_args()
        cmd += display.to_scrcpy_args()
        return cmd

    def start(self, display: DisplayConfig, connection: ConnectionConfig) -> None:
        if self.state == SessionState.RUNNING:
            raise RuntimeError("Une session est déjà en cours.")
        devices = self.list_devices()
        if not devices:
            raise RuntimeError("Aucun appareil détecté. Vérifie le débogage USB / la connexion.")
        if connection.serial and connection.serial not in devices:
            raise RuntimeError(f"Appareil '{connection.serial}' non trouvé parmi {devices}.")
        cmd = self.build_command(display, connection)
        self._on_log(f"[dextop] Lancement : {' '.join(cmd)}")
        self._set_state(SessionState.STARTING)
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        self._set_state(SessionState.RUNNING)
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def _read_output(self) -> None:
        assert self._process and self._process.stdout
        for line in self._process.stdout:
            self._on_log(line.rstrip())
        rc = self._process.wait()
        if rc == 0:
            self._set_state(SessionState.IDLE)
        else:
            self._on_log(f"[dextop] scrcpy s'est arrêté avec le code {rc}")
            self._set_state(SessionState.CRASHED)

    def stop(self, timeout: float = 5.0) -> None:
        if not self._process or self._process.poll() is not None:
            self._set_state(SessionState.IDLE)
            return
        self._set_state(SessionState.STOPPING)
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
        self._set_state(SessionState.IDLE)
PY

# ─── dextop/binaries.py (improved) ────────────────────────────────
cat > dextop/binaries.py <<'PY'
import os
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SCRCPY_VERSION = os.environ.get("SCRCPY_VERSION", "3.1")

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


def _bin_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "bin"
    return Path(__file__).parent.parent / "bin"


def _platform_key() -> str:
    key = platform.system().lower()
    if key == "darwin":
        return "darwin"
    if key == "windows":
        return "windows"
    return "linux"


def _download_and_extract(url: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / Path(url).name
    print(f"[dextop] Téléchargement {url}")
    urllib.request.urlretrieve(url, archive)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(dest)
    archive.unlink()


def _move_binaries_to_root(root: Path) -> None:
    for pattern in ("scrcpy*", "adb*", "scrcpy-server*"):
        for p in root.rglob(pattern):
            if p.is_file() and p.parent != root:
                target = root / p.name
                if not target.exists():
                    p.rename(target)
                if os.name != "nt":
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)


def ensure_binaries() -> Path:
    """Télécharge scrcpy + adb si absents. Retourne le chemin vers bin/."""
    dest = _bin_dir()
    dest.mkdir(parents=True, exist_ok=True)
    plat = _platform_key()

    scrcpy_bin = dest / ("scrcpy.exe" if plat == "windows" else "scrcpy")
    adb_bin = dest / ("adb.exe" if plat == "windows" else "adb")
    server_jar = dest / "scrcpy-server"

    if scrcpy_bin.exists() and adb_bin.exists() and server_jar.exists():
        return dest

    print(f"[dextop] Téléchargement des binaires pour {plat}…")
    _download_and_extract(SCRCPY_URLS[plat], dest)
    _download_and_extract(ADB_URLS[plat], dest)
    _move_binaries_to_root(dest)
    print("[dextop] Binaires prêts.")
    return dest


if __name__ == "__main__":
    ensure_binaries()
PY

# ─── dextop/multi_session.py (imports fixed) ──────────────────────
cat > dextop/multi_session.py <<'PY'
import subprocess
import threading
import uuid
from dataclasses import dataclass
from typing import Dict

from dextop.orchestrator import DisplayConfig, ConnectionConfig


@dataclass
class AppSession:
    id: str
    app_package: str
    display_config: DisplayConfig
    process: subprocess.Popen
    window_title: str


class MultiSessionOrchestrator:
    def __init__(self, adb_path: str, scrcpy_path: str):
        self.sessions: Dict[str, AppSession] = {}
        self.adb = adb_path
        self.scrcpy = scrcpy_path

    def launch_app_window(self, app_package: str, display: DisplayConfig, connection: ConnectionConfig) -> str:
        session_id = str(uuid.uuid4())[:8]
        cmd = [
            self.scrcpy,
            *connection.to_scrcpy_args(),
            "--new-display", f"{display.width}x{display.height}/{display.dpi}",
            "--start-app", app_package,
            "--display-ime-policy=local",
            "--window-title", f"{app_package} — DeXtop",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        session = AppSession(
            id=session_id, app_package=app_package, display_config=display,
            process=proc, window_title=f"{app_package} — DeXtop",
        )
        self.sessions[session_id] = session
        threading.Thread(target=self._watch_session, args=(session_id,), daemon=True).start()
        return session_id

    def _watch_session(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        assert session.process.stdout
        for line in session.process.stdout:
            print(f"[{session.app_package}] {line.strip()}")
        session.process.wait()
        self.sessions.pop(session_id, None)

    def close_session(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session:
            session.process.terminate()
            try:
                session.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                session.process.kill()
PY

# ─── dextop/cli.py ────────────────────────────────────────────────
cat > dextop/cli.py <<'PY'
import argparse
import sys
import time

from dextop.orchestrator import (
    ScrcpyOrchestrator, DisplayConfig, ConnectionConfig, SessionState,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeXtop — prototype CLI")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--app", help="Package à lancer")
    parser.add_argument("--serial", help="Serial ADB")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    orch = ScrcpyOrchestrator(
        on_state_change=lambda s: print(f"[état] {s.value}"),
        on_log=lambda l: print(l),
    )
    if args.list:
        for dev in orch.list_devices():
            print(dev)
        return 0

    display = DisplayConfig(width=args.width, height=args.height, dpi=args.dpi, start_app=args.app)
    connection = ConnectionConfig(serial=args.serial, audio=not args.no_audio)
    try:
        orch.start(display, connection)
    except Exception as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 1
    try:
        while orch.state in (SessionState.STARTING, SessionState.RUNNING):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dextop] Arrêt demandé…")
        orch.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY

# ─── dextop.spec ──────────────────────────────────────────────────
cat > dextop.spec <<'PY'
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("customtkinter")

# Bundle the ./bin directory (scrcpy + adb) so the app is self-contained
binaries = []
if os.path.isdir("bin"):
    for f in os.listdir("bin"):
        p = os.path.join("bin", f)
        if os.path.isfile(p):
            binaries.append((p, "bin"))

icon_path = "resources/icon.ico"
if not os.path.exists(icon_path):
    icon_path = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="DeXtop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
PY

# ─── dextop.iss ───────────────────────────────────────────────────
cat > dextop.iss <<'ISS'
; dextop.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "DeXtop"
#define MyAppPublisher "DeXtop"
#define MyAppExeName "DeXtop.exe"

[Setup]
AppId={{8F3A5B2C-9E1D-4F7A-B6C4-DEXT0P000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer\output
OutputBaseFilename=DeXtop-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
ISS

# ─── build_appimage.sh ────────────────────────────────────────────
cat > build_appimage.sh <<'SH'
#!/bin/bash
set -e
APP_NAME="DeXtop"
DIST_DIR="dist"
APPDIR="AppDir"
APPIMAGETOOL="${DIST_DIR}/appimagetool"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

mkdir -p "$DIST_DIR"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "[AppImage] Downloading appimagetool..."
    wget -q "$APPIMAGETOOL_URL" -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "${DIST_DIR}/DeXtop" "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/DeXtop" "$@"
EOF
chmod +x "$APPDIR/AppRun"

VERSION="${VERSION:-0.0.0}"
"$APPIMAGETOOL" "$APPDIR" "${DIST_DIR}/DeXtop-${VERSION}-x86_64.AppImage"
echo "[AppImage] Build complete."
SH
chmod +x build_appimage.sh

# ─── requirements.txt ─────────────────────────────────────────────
cat > requirements.txt <<'TXT'
customtkinter>=5.2.0
TXT

# ─── .gitignore ───────────────────────────────────────────────────
cat > .gitignore <<'GI'
__pycache__/
*.pyc
bin/
build/
dist/
AppDir/
installer/
*.egg-info/
.venv/
GI

# ─── README.md ────────────────────────────────────────────────────
cat > README.md <<'MD'
# DeXtop

Desktop mode for Android via scrcpy.

## Utilisation locale
```bash
pip install -r requirements.txt
python -m dextop.binaries   # télécharge scrcpy + adb dans ./bin
python main.py
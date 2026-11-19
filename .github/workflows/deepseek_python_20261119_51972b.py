# dextop/orchestrator.py
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
    """Configuration d'un écran virtuel DeXtop."""
    width: int = 1920
    height: int = 1080
    dpi: int = 240
    flex_display: bool = True           # --flex-display
    hide_system_decorations: bool = True  # --no-vd-system-decorations
    start_app: Optional[str] = None     # --start-app=nom.paquet
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
    """Paramètres de connexion à l'appareil."""
    serial: Optional[str] = None        # ex: "192.168.1.42:5555" ou None pour USB
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


class ScrcpyOrchestrator:
    """
    Gère le lancement et le suivi de scrcpy en mode 'écran virtuel DeX'.
    Thread-safe, avec callbacks pour notifier l'UI.
    """

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

    # ---------- Helpers ----------

    @staticmethod
    def _find_binary(name: str) -> str:
        """Cherche le binaire dans ./bin puis dans le PATH."""
        local = Path(__file__).parent.parent / "bin" / (name + (".exe" if os.name == "nt" else ""))
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

    # ---------- Vérification appareil ----------

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

    # ---------- Cycle de vie ----------

    def build_command(self, display: DisplayConfig, connection: ConnectionConfig) -> list[str]:
        cmd = [self.scrcpy_path]
        cmd += connection.to_scrcpy_args()
        cmd += display.to_scrcpy_args()
        return cmd

    def start(self, display: DisplayConfig, connection: ConnectionConfig) -> None:
        if self.state == SessionState.RUNNING:
            raise RuntimeError("Une session est déjà en cours.")

        # Vérifie qu'un appareil est bien connecté
        devices = self.list_devices()
        if not devices:
            raise RuntimeError("Aucun appareil détecté. Vérifie le débogage USB / la connexion.")
        if connection.serial and connection.serial not in devices:
            raise RuntimeError(f"Appareil '{connection.serial}' non trouvé parmi {devices}.")

        cmd = self.build_command(display, connection)
        self._on_log(f"[dextop] Lancement : {' '.join(cmd)}")
        self._set_state(SessionState.STARTING)

        # Fusionne stderr dans stdout pour capter tous les logs
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
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
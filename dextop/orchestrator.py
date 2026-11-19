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
        args.extend(["--video-bit-rate", self.bitrate, "--max-fps", str(self.max_fps)])
        args.extend(["--audio-codec", self.audio_codec] if self.audio else ["--no-audio"])
        if self.stay_awake:
            args.append("--stay-awake")
        if self.turn_screen_off:
            args.append("--turn-screen-off")
        return args


def _find_binary(name: str) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    binary_name = name + suffix
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.extend([Path(sys.executable).parent / "bin" / binary_name])
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "bin" / binary_name)
    candidates.append(Path(__file__).parent.parent / "bin" / binary_name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if not found:
        return name
    return found


class ScrcpyOrchestrator:
    def __init__(self, scrcpy_path: Optional[str] = None, adb_path: Optional[str] = None,
                 on_state_change: Optional[Callable[[SessionState], None]] = None,
                 on_log: Optional[Callable[[str], None]] = None):
        self.scrcpy_path = scrcpy_path or _find_binary("scrcpy")
        self.adb_path = adb_path or _find_binary("adb")
        self._on_state = on_state_change or (lambda state: None)
        self._on_log = on_log or (lambda line: None)
        self._process: Optional[subprocess.Popen] = None
        self._state = SessionState.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> SessionState:
        return self._state

    def _set_state(self, state: SessionState) -> None:
        with self._lock:
            self._state = state
        self._on_state(state)

    def list_devices(self) -> list[str]:
        try:
            result = subprocess.run([self.adb_path, "devices"], capture_output=True,
                                    text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            return []
        return [line.split("\t", 1)[0] for line in result.stdout.splitlines()[1:] if "\tdevice" in line]

    def list_packages(self, serial: Optional[str] = None, third_party_only: bool = True) -> list[str]:
        command = [self.adb_path]
        if serial:
            command.extend(["-s", serial])
        command.extend(["shell", "pm", "list", "packages"])
        if third_party_only:
            command.append("-3")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"Impossible d'interroger le device : {exc}") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or f"ADB a terminé avec le code {result.returncode}"
            raise RuntimeError(message)

        return sorted({
            line.removeprefix("package:").strip()
            for line in result.stdout.splitlines()
            if line.strip().startswith("package:")
        })

    def build_command(self, display: DisplayConfig, connection: ConnectionConfig) -> list[str]:
        return [self.scrcpy_path, *connection.to_scrcpy_args(), *display.to_scrcpy_args()]

    def start(self, display: DisplayConfig, connection: ConnectionConfig) -> None:
        if self.state in (SessionState.RUNNING, SessionState.STARTING):
            raise RuntimeError("Une session est déjà en cours.")
        devices = self.list_devices()
        if not devices:
            raise RuntimeError("Aucun appareil détecté. Vérifie le débogage USB ou la connexion Wi-Fi.")
        if connection.serial and connection.serial not in devices:
            raise RuntimeError(f"Appareil '{connection.serial}' introuvable parmi {devices}.")
        cmd = self.build_command(display, connection)
        self._on_log(f"[dextop] Lancement : {' '.join(cmd)}")
        self._set_state(SessionState.STARTING)
        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1)
        self._set_state(SessionState.RUNNING)
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        assert self._process and self._process.stdout
        for line in self._process.stdout:
            self._on_log(line.rstrip())
        rc = self._process.wait()
        self._set_state(SessionState.IDLE if rc == 0 else SessionState.CRASHED)

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

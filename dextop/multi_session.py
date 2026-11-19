from __future__ import annotations

import subprocess
import threading
import uuid
from dataclasses import dataclass

from dextop.orchestrator import _find_binary


@dataclass
class AppSession:
    id: str
    app_package: str
    process: subprocess.Popen
    window_title: str


class MultiSessionOrchestrator:
    def __init__(self, on_session_started=None, on_session_ended=None, on_log=None):
        self.scrcpy_path = _find_binary("scrcpy")
        self.adb_path = _find_binary("adb")
        self.sessions: dict[str, AppSession] = {}
        self._on_started = on_session_started or (lambda session: None)
        self._on_ended = on_session_ended or (lambda session_id: None)
        self._on_log = on_log or (lambda session_id, line: None)

    def launch_app(self, app_package: str, display, connection) -> str:
        session_id = str(uuid.uuid4())[:8]
        title = f"{app_package} — DeXtop"
        cmd = [self.scrcpy_path, *connection.to_scrcpy_args(),
               "--new-display", f"{display.width}x{display.height}/{display.dpi}",
               "--flex-display", "--no-vd-system-decorations",
               "--start-app", app_package, "--display-ime-policy=local",
               "--window-title", title]
        self._on_log(session_id, f"[dextop] {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        session = AppSession(session_id, app_package, process, title)
        self.sessions[session_id] = session
        self._on_started(session)
        threading.Thread(target=self._watch, args=(session_id,), daemon=True).start()
        return session_id

    def _watch(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session or not session.process.stdout:
            return
        for line in session.process.stdout:
            self._on_log(session_id, line.rstrip())
        session.process.wait()
        self.sessions.pop(session_id, None)
        self._on_ended(session_id)

    def close(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if not session:
            return
        if session.process.poll() is None:
            session.process.terminate()
            try:
                session.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                session.process.kill()
        self._on_ended(session_id)

    def close_all(self) -> None:
        for session_id in list(self.sessions):
            self.close(session_id)

    def list_packages(self, serial: str | None = None, third_party_only: bool = True) -> list[str]:
        command = [self.adb_path] + (["-s", serial] if serial else [])
        command += ["shell", "pm", "list", "packages"]
        if third_party_only:
            command.append("-3")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        except (subprocess.TimeoutExpired, OSError):
            return []
        return [line.replace("package:", "").strip() for line in result.stdout.splitlines() if line.strip()]

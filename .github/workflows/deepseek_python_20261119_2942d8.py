# dextop/multi_session.py
import uuid
from dataclasses import dataclass
from typing import Dict

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

    def launch_app_window(self, app_package: str, display: DisplayConfig, connection: ConnectionConfig):
        """Lance une nouvelle fenêtre indépendante pour une application."""
        session_id = str(uuid.uuid4())[:8]

        # 1. Créer un nouvel écran virtuel dédié à cette app
        #    On peut utiliser --new-display avec un ID de display spécifique
        #    ou laisser scrcpy en créer un nouveau à chaque fois.
        #    L'approche de LinkAndroid est d'utiliser --new-display + --start-app.
        cmd = [
            self.scrcpy,
            *connection.to_scrcpy_args(),
            "--new-display", f"{display.width}x{display.height}/{display.dpi}",
            "--start-app", app_package,
            "--display-ime-policy=local",  # Garde le clavier dans la fenêtre
        ]

        # 2. Ajouter un titre de fenêtre pour identifier l'app
        cmd.extend(["--window-title", f"{app_package} — DeXtop"])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        session = AppSession(
            id=session_id,
            app_package=app_package,
            display_config=display,
            process=proc,
            window_title=f"{app_package} — DeXtop"
        )
        self.sessions[session_id] = session

        # 3. Lancer un thread pour surveiller ce processus
        threading.Thread(target=self._watch_session, args=(session_id,), daemon=True).start()
        return session_id

    def _watch_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session: return
        # Lire les logs et attendre la fin
        for line in session.process.stdout:
            print(f"[{session.app_package}] {line.strip()}")
        session.process.wait()
        # Nettoyer la session quand scrcpy se termine
        self.sessions.pop(session_id, None)

    def close_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session:
            session.process.terminate()
            try:
                session.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                session.process.kill()
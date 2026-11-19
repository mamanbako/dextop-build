"""Persistance de la configuration utilisateur."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "DeXtop"


class Config:
    DEFAULTS: dict[str, Any] = {
        "width": 1920,
        "height": 1080,
        "dpi": 240,
        "max_fps": 60,
        "audio": True,
        "stay_awake": True,
        "turn_screen_off": True,
        "last_serial": None,
        "favorite_apps": [],
    }

    def __init__(self, path: Path | None = None):
        self.path = path or config_dir() / "config.json"
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

import json
import threading
from pathlib import Path


class UserProfile:
    def __init__(self, profile_path: str = None):
        self._path = Path(profile_path or (Path.home() / ".jarvis" / "profile.json"))
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    def _load(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        try:
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError:
            pass

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value
            self._save()

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._data)

    def update(self, data: dict):
        with self._lock:
            self._data.update(data)
            self._save()

    def delete(self, key: str):
        with self._lock:
            self._data.pop(key, None)
            self._save()

    def clear(self):
        with self._lock:
            self._data.clear()
            self._save()

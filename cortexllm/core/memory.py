"""Core memory persistence"""
import json
from pathlib import Path
from typing import Any, Optional, Dict

HOT_LIMIT = 200
WARM_LIMIT = 500

class Memory:
    """Atomic file persistence with enforced hot/warm caps"""

    def __init__(self, path=None):
        self.root = path or Path.home() / ".config" / "cortexllm"
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache = {}

    def _file(self, name):
        return self.root / f"{name}.json"

    def write(self, key, data):
        """Write data atomically. Enforces message cap for hot/warm keys."""
        if key in ("hot", "session") and isinstance(data, list) and len(data) > HOT_LIMIT:
            data = data[-HOT_LIMIT:]
        elif key == "warm" and isinstance(data, list) and len(data) > WARM_LIMIT:
            data = data[-WARM_LIMIT:]
        self._cache[key] = data
        tmp = self._file(f"{key}.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._file(key))

    def read(self, key):
        if key in self._cache:
            return self._cache[key]
        try:
            return json.loads(self._file(key).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def session(self, data=None):
        if data:
            self.write("session", data)
            return data
        return self.read("session")

    def tasks(self):
        return self.read("tasks") or {}

    def save_task(self, tid, data):
        t = self.tasks()
        t[tid] = data
        self.write("tasks", t)

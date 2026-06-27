"""Configuration with Brave + searxng defaults"""
import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "brain": {
        "heartbeat_interval": 30,
        "task_timeout": 300,
        "max_retries": 2
    },
    "workers": {
        "heartbeat_interval": 10,
        "max_concurrent": 10
    },
    "memory": {
        "path": "~/.config/cortexllm",
        "write_interval": 5
    },
    "browser": {
        "enabled": True,
        "cdp_url": "http://127.0.0.1:9222"
    },
    "search": {
        "enabled": True,
        "provider": "searxng",
        "base_url": "http://127.0.0.1:8888"
    },
    "model": {
        "reasoning_model": "gpt-oss:20b-cloud",
        "reasoning_host": "cloud",
        "worker_model": "deepseek-flash",
        "worker_host": "cloud",
        "context_tokens": 262144,
        "reasoning_token_cap": 32768,
        "worker_token_cap": 16384
    },
    "gateway": {
        "port": 18789,
        "bind": "lan"
    }
}

class Config:
    """Configuration handler"""

    def __init__(self, path=None):
        self.path = path or Path.home() / ".config" / "cortexllm" / "config.json"
        self._data = {}
        self.load()

    def load(self):
        try:
            self._data = json.loads(self.path.read_text())
        except FileNotFoundError:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)

    def get(self, *path, default=None):
        d = self._data
        for k in path:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d

    def set(self, *path, value=None):
        d = self._data
        for k in path[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[path[-1]] = value
        self.save()

    @property
    def cdp_url(self):
        return self.get("browser", "cdp_url", default="http://127.0.0.1:9222")

    @property
    def searxng_url(self):
        return self.get("search", "base_url", default="http://127.0.0.1:8888")

    @property
    def gateway_port(self):
        return self.get("gateway", "port", default=18789)

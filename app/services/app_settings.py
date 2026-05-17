"""Persistent user-facing settings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PLUS_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PLUS_ROOT / "config" / "app_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "credential_valid_days": 14,
    "network": {
        "request_interval_ms": 500,
        "max_retries": 3,
        "task_timeout_seconds": 30,
    },
    "notifications": {
        "enable_sound": True,
        "enable_desktop": True,
        "log_auto_scroll": True,
        "max_log_items": 500,
    },
}


class AppSettings:
    def get(self) -> dict[str, Any]:
        if not SETTINGS_PATH.exists():
            return DEFAULT_SETTINGS.copy()
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return _merge(DEFAULT_SETTINGS, loaded)
        except Exception:
            return DEFAULT_SETTINGS.copy()

    def save(self, values: dict[str, Any]) -> dict[str, Any]:
        current = self.get()
        merged = _merge(current, values)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=4), encoding="utf-8")
        return merged


def _merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


app_settings = AppSettings()

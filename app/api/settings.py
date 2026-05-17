"""Settings and real runtime resource state."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.auth import _credential_meta, _current_user
from app.core.config import settings
from app.services.app_settings import PLUS_ROOT, app_settings
from app.services.config_loader import CONFIG_DIR, config_manager

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    credential_valid_days: int | None = None
    network: dict | None = None
    notifications: dict | None = None


def _file_info(path: Path) -> dict:
    stat = path.stat()
    return {"name": path.name, "path": str(path), "size": stat.st_size, "updated_at": stat.st_mtime}


def _dir_info(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False, "files": 0, "size": 0}
    files = [item for item in path.rglob("*") if item.is_file()]
    return {"path": str(path), "exists": True, "files": len(files), "size": sum(item.stat().st_size for item in files)}


@router.get("")
async def get_settings():
    execute_dir = PLUS_ROOT / "execute"
    cookies_dir = PLUS_ROOT / "cookies"
    config_files = sorted((_file_info(path) for path in CONFIG_DIR.glob("*.json")), key=lambda item: item["name"]) if CONFIG_DIR.exists() else []
    cookie_files = sorted((_file_info(path) for path in cookies_dir.rglob("*") if path.is_file()), key=lambda item: item["path"]) if cookies_dir.exists() else []
    executables = sorted((_file_info(path) for path in execute_dir.iterdir() if path.is_file()), key=lambda item: item["name"]) if execute_dir.exists() else []
    extra_dirs = {name: _dir_info(PLUS_ROOT / name) for name in ["captcha_images", "javascript", "model", "others", "videos"]}
    return {
        "settings": app_settings.get(),
        "credential": _credential_meta(),
        "user": _current_user if _current_user.get("is_login") else None,
        "games": config_manager.get_all_games(),
        "resources": {
            "paths": {"config": str(CONFIG_DIR), "cookies": str(cookies_dir), "execute": str(execute_dir)},
            "config_files": config_files,
            "cookie_files": cookie_files,
            "executables": executables,
            "extra_dirs": extra_dirs,
        },
        "backend": {
            "host": settings.host,
            "port": settings.port,
            "database_url": settings.database_url,
            "bili_request_interval": settings.bili_request_interval,
            "bili_max_retries": settings.bili_max_retries,
        },
    }


@router.post("")
async def save_settings(req: SettingsUpdate):
    values = req.model_dump(exclude_none=True)
    saved = app_settings.save(values)
    cred_path = PLUS_ROOT / "cookies" / "bili_cookies.json"
    if req.credential_valid_days and cred_path.exists():
        import json
        from datetime import datetime, timedelta

        data = json.loads(cred_path.read_text(encoding="utf-8"))
        now = datetime.now()
        data["saved_at"] = data.get("saved_at") or now.isoformat(timespec="seconds")
        data["expires_at"] = (now + timedelta(days=max(req.credential_valid_days, 1))).isoformat(timespec="seconds")
        cred_path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    return {"success": True, "settings": saved}

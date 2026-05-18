"""应用核心配置"""
from __future__ import annotations
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(os.environ.get("BILITOOLS_PLUS_ROOT", Path(__file__).resolve().parents[2])) / "config" / "secrets.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bili_sign_salt: str = ""
    bili_coupon_salt: str = ""
    jwt_secret: str = os.environ.get("BILITOOLS_JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    database_url: str = os.environ.get("BILITOOLS_DATABASE_URL", "sqlite+aiosqlite:///./data/bili_tools.db")
    host: str = os.environ.get("BILITOOLS_HOST", "0.0.0.0")
    port: int = int(os.environ.get("BILITOOLS_PORT", os.environ.get("PORT", "8001")))
    cors_origins: list[str] = ["http://localhost:1420", "http://127.0.0.1:1420"]
    ws_heartbeat_interval: int = 25
    bili_request_interval: float = 0.5
    bili_max_retries: int = 3


settings = Settings()

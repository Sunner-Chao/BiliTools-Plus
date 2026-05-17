"""账号模型"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    cookies: Mapped[str] = mapped_column(Text, nullable=False, default="")
    game: Mapped[str] = mapped_column(String(32), nullable=False, default="原神")
    room_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_login: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now(timezone.utc).isoformat())

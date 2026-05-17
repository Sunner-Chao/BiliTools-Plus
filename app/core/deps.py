"""FastAPI 依赖注入 — 认证 & B站 Cookie 校验"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.response import ErrorCode, fail_response, token_expired_response, auth_required_response

logger = logging.getLogger(__name__)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """从 Authorization: Bearer <token> 解析当前用户

    Returns:
        {"sub": username, "uid": uid}  或抛出 401
    """
    if not authorization:
        return auth_required_response()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return auth_required_response()

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        logger.warning(f"[Auth] JWT decode failed: {e}")
        return token_expired_response()

    exp = payload.get("exp")
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        return token_expired_response()

    return {"sub": payload.get("sub", ""), "uid": payload.get("uid", "")}


async def require_bili_cookies(user: dict = Depends(get_current_user)) -> str:
    """依赖 get_current_user, 然后从 DB 中加载该用户的 B站 Cookie 字符串

    Returns:
        cookie string 或抛出错误
    """
    from app.models import Account, async_session

    if isinstance(user, dict) and user.get("sub"):
        username = user["sub"]
    else:
        return fail_response(ErrorCode.AUTH_REQUIRED, status_code=401)

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Account).where(
                    (Account.username == username) | (Account.uid == user.get("uid", ""))
                )
            )
            acc = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"[Auth] DB lookup failed: {e}")
        return fail_response(ErrorCode.DATABASE_ERROR, status_code=500)

    if not acc or not acc.cookies:
        return fail_response(ErrorCode.BILI_COOKIE_INVALID, msg="请先扫码登录获取B站Cookie", status_code=401)

    return acc.cookies

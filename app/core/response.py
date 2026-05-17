"""统一 API 响应模型 & 错误码枚举

所有接口统一返回格式:
  { "code": int, "msg": str, "data": any }

code == 0 表示成功, 非 0 表示各类错误 (见 ErrorCode)
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any, Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ── 错误码枚举 ────────────────────────────────────────────────
class ErrorCode(IntEnum):
    """统一错误码 — 1000 段供后端各模块使用"""

    # 通用
    SUCCESS = 0
    UNKNOWN = 1000
    PARAM_INVALID = 1001
    NOT_FOUND = 1002
    FORBIDDEN = 1003

    # 认证 2000 段
    AUTH_REQUIRED = 2000
    AUTH_TOKEN_EXPIRED = 2001
    AUTH_TOKEN_INVALID = 2002
    AUTH_LOGIN_FAILED = 2003
    AUTH_QR_EXPIRED = 2004
    AUTH_QR_NOT_CONFIRMED = 2005

    # B站 API 3000 段
    BILI_API_ERROR = 3000
    BILI_RATE_LIMIT = 3001
    BILI_COOKIE_INVALID = 3002
    BILI_REQUEST_FAILED = 3003

    # 任务 4000 段
    TASK_NOT_FOUND = 4000
    TASK_ALREADY_RUNNING = 4001
    TASK_CANCELLED = 4002
    TASK_EXEC_FAILED = 4003

    # 服务器 5000 段
    SERVER_ERROR = 5000
    DATABASE_ERROR = 5001
    NETWORK_ERROR = 5002


# 错误码 → 默认消息映射 (给前端做 reference)
ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.UNKNOWN: "未知错误",
    ErrorCode.PARAM_INVALID: "参数无效",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.FORBIDDEN: "无权限访问",

    ErrorCode.AUTH_REQUIRED: "请先登录",
    ErrorCode.AUTH_TOKEN_EXPIRED: "登录已过期，请重新登录",
    ErrorCode.AUTH_TOKEN_INVALID: "无效的访问令牌",
    ErrorCode.AUTH_LOGIN_FAILED: "登录失败",
    ErrorCode.AUTH_QR_EXPIRED: "二维码已过期，请重新生成",
    ErrorCode.AUTH_QR_NOT_CONFIRMED: "扫码未确认，请在手机端确认",

    ErrorCode.BILI_API_ERROR: "B站 API 返回错误",
    ErrorCode.BILI_RATE_LIMIT: "请求过于频繁，请稍后重试",
    ErrorCode.BILI_COOKIE_INVALID: "B站 Cookie 已失效，请重新登录",
    ErrorCode.BILI_REQUEST_FAILED: "B站请求失败，请检查网络",

    ErrorCode.TASK_NOT_FOUND: "任务不存在",
    ErrorCode.TASK_ALREADY_RUNNING: "任务已在运行中",
    ErrorCode.TASK_CANCELLED: "任务已取消",
    ErrorCode.TASK_EXEC_FAILED: "任务执行失败",

    ErrorCode.SERVER_ERROR: "服务器内部错误",
    ErrorCode.DATABASE_ERROR: "数据库操作失败",
    ErrorCode.NETWORK_ERROR: "网络连接失败",
}


# ── 响应模型 ──────────────────────────────────────────────────
class ApiResponse(BaseModel):
    """标准 API 响应体"""
    code: int = ErrorCode.SUCCESS
    msg: str = "成功"
    data: Optional[Any] = None


def ok(data: Any = None, msg: str = "成功") -> dict:
    """成功响应"""
    return {"code": ErrorCode.SUCCESS, "msg": msg, "data": data}


def fail(code: ErrorCode, msg: str | None = None, data: Any = None) -> dict:
    """失败响应 — msg 缺省时自动查表"""
    return {
        "code": code,
        "msg": msg or ERROR_MESSAGES.get(code, "未知错误"),
        "data": data,
    }


def fail_response(code: ErrorCode, msg: str | None = None, status_code: int = 400) -> JSONResponse:
    """返回 JSONResponse 形式的错误 (适用于需要自定义 HTTP 状态码的场景)"""
    return JSONResponse(
        status_code=status_code,
        content=fail(code, msg),
    )


# ── 令牌相关辅助 ──────────────────────────────────────────────
def token_expired_response() -> JSONResponse:
    """令牌过期的标准响应 (HTTP 401)"""
    return fail_response(ErrorCode.AUTH_TOKEN_EXPIRED, status_code=401)


def auth_required_response() -> JSONResponse:
    """未登录的标准响应 (HTTP 401)"""
    return fail_response(ErrorCode.AUTH_REQUIRED, status_code=401)


def bili_cookie_invalid_response() -> JSONResponse:
    """B站 Cookie 失效的标准响应 (HTTP 401)"""
    return fail_response(ErrorCode.BILI_COOKIE_INVALID, status_code=401)

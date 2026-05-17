"""B站扫码登录 API — 完整复刻 src 源码登录流程 + 自动获取用户信息"""
from __future__ import annotations
import asyncio, base64, io, json, logging, os, time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx, qrcode
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.response import (
    ErrorCode, ok, fail, fail_response,
    token_expired_response, auth_required_response,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

BILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}
logger = logging.getLogger(__name__)

# ── cookies 持久化路径（复刻 src 目录结构）──────────────────
COOKIES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cookies")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
os.makedirs(COOKIES_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)


class QRSession:
    def __init__(self, qrcode_key: str, image_base64: str):
        self.qrcode_key = qrcode_key
        self.image_base64 = image_base64
        self.created_at = time.time()
        self.status = "pending"
        self.cookies: Optional[str] = None
        self.username: Optional[str] = None
        self.uid: Optional[str] = None

    def is_expired(self) -> bool:
        return time.time() - self.created_at > 180


_qr_sessions: dict[str, QRSession] = {}
_qr_lock = asyncio.Lock()

# ── 当前登录用户信息缓存 ──────────────────────────────────
_current_user: dict = {}


async def _fetch(url: str, params: dict, cookies_str: str = None) -> dict:
    headers = BILI_HEADERS.copy()
    if cookies_str:
        headers["Cookie"] = cookies_str
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=headers)
        return resp.json()


async def _fetch_user_info(cookies_str: str) -> dict:
    """登录成功后自动获取用户完整信息 — 复刻 src 的 get_user_info 逻辑"""
    user_info = {}
    try:
        # 1. 获取 nav 信息（uid, username, avatar, vip 等）
        nav_data = await _fetch(
            "https://api.bilibili.com/x/web-interface/nav",
            {}, cookies_str
        )
        if nav_data.get("code") == 0:
            data = nav_data.get("data", {})
            user_info["uid"] = str(data.get("mid", ""))
            user_info["username"] = data.get("uname", "")
            user_info["avatar"] = data.get("face", "")
            user_info["vip_status"] = data.get("vipStatus", 0)
            user_info["vip_type"] = data.get("vipType", 0)
            user_info["level"] = data.get("level_info", {}).get("current_level", 0)

        # 2. 获取直播间信息（room_id 等）
        uid = user_info.get("uid", "")
        if uid:
            live_data = await _fetch(
                "https://api.live.bilibili.com/xlive/web-ucenter/user/get_user_info",
                {}, cookies_str
            )
            if live_data.get("code") == 0:
                live_info = live_data.get("data", {})
                user_info["room_id"] = str(live_info.get("room_id", ""))
                user_info["live_room_url"] = live_info.get("live_room_url", "")

        # 3. 解析 cookies 中的关键字段
        cookies_dict = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies_dict[k.strip()] = v.strip()
        user_info["bili_jct"] = cookies_dict.get("bili_jct", "")
        user_info["buvid3"] = cookies_dict.get("buvid3", "")
        user_info["dede_user_id"] = cookies_dict.get("DedeUserID", cookies_dict.get("dedeuserid", ""))

    except Exception as e:
        logger.warning(f"[Auth] 获取用户信息失败: {e}")
    return user_info


def _save_cookies_to_file(cookies_str: str, uid: str = ""):
    """保存 cookies 到文件 — 复刻 src 的 cookies 目录结构"""
    try:
        now = datetime.now()
        valid_days = 14
        settings_path = os.path.join(CONFIG_DIR, "app_settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as sf:
                    valid_days = max(int(json.load(sf).get("credential_valid_days", 14)), 1)
            except Exception:
                valid_days = 14
        # bili_cookies.json（主格式，复刻 src）
        cookies_json_path = os.path.join(COOKIES_DIR, "bili_cookies.json")
        with open(cookies_json_path, "w", encoding="utf-8") as f:
            json.dump({
                "COOKIES": cookies_str,
                "uid": uid,
                "saved_at": now.isoformat(timespec="seconds"),
                "expires_at": (now + timedelta(days=valid_days)).isoformat(timespec="seconds"),
            }, f, ensure_ascii=False, indent=4)
        logger.info(f"[Auth] cookies 已保存到 {cookies_json_path}")
    except Exception as e:
        logger.warning(f"[Auth] cookies 保存失败: {e}")


def _credential_meta() -> dict:
    path = os.path.join(COOKIES_DIR, "bili_cookies.json")
    if not os.path.exists(path):
        return {"exists": False, "valid": False}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        expires_at = data.get("expires_at")
        valid = bool(data.get("COOKIES")) and (not expires_at or datetime.fromisoformat(expires_at) > datetime.now())
        return {
            "exists": True,
            "valid": valid,
            "uid": data.get("uid", ""),
            "saved_at": data.get("saved_at", ""),
            "expires_at": expires_at or "",
            "path": path,
        }
    except Exception as exc:
        return {"exists": True, "valid": False, "error": str(exc), "path": path}


def _save_user_info_to_file(user_info: dict):
    """保存用户信息到 config 目录"""
    try:
        user_info_path = os.path.join(CONFIG_DIR, "bili_user_info.json")
        with open(user_info_path, "w", encoding="utf-8") as f:
            json.dump(user_info, f, ensure_ascii=False, indent=4)
        logger.info(f"[Auth] 用户信息已保存到 {user_info_path}")
    except Exception as e:
        logger.warning(f"[Auth] 用户信息保存失败: {e}")


async def _generate_qrcode() -> QRSession:
    url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    params = {"source": "main-fe-header", "_": str(int(time.time() * 1000))}
    data = await _fetch(url, params)
    if data.get("code") != 0:
        raise HTTPException(status_code=502, detail=f"B站API错误: {data}")

    qrcode_key = data["data"]["qrcode_key"]
    url_str = data["data"]["url"]
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=2)
    qr.add_data(url_str); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    session = QRSession(qrcode_key=qrcode_key, image_base64=img_base64)
    async with _qr_lock:
        for k in list(_qr_sessions.keys()):
            if _qr_sessions[k].is_expired():
                del _qr_sessions[k]
        _qr_sessions[qrcode_key] = session
    return session


async def _poll_qrcode(qrcode_key: str) -> dict:
    async with _qr_lock:
        if qrcode_key not in _qr_sessions:
            return {"code": 404, "status": "expired", "message": "二维码已过期"}
        session = _qr_sessions[qrcode_key]
    if session.status == "confirmed":
        return {"code": 0, "status": "confirmed", "username": session.username, "uid": session.uid, "cookies": session.cookies}
    if session.is_expired():
        session.status = "expired"; return {"code": 408, "status": "expired", "message": "二维码已过期"}
    poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    params = {"qrcode_key": qrcode_key, "source": "main-fe-header", "_": str(int(time.time() * 1000))}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            poll_data = (await client.get(poll_url, params=params, headers=BILI_HEADERS)).json()
    except Exception as e:
        logger.error(f"[QR] poll failed: {e}")
        return {"code": 503, "status": "failed", "message": "网络请求失败"}
    bili_code = poll_data.get("data", {}).get("code", -1)
    if bili_code == 0:
        session.status = "confirmed"
        cookies_list = poll_data.get("data", {}).get("cookie_info", {}).get("cookies", [])
        session.cookies = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
        session.username = poll_data.get("data", {}).get("uname", "")
        session.uid = str(poll_data.get("data", {}).get("uid", ""))
        return {"code": 0, "status": "confirmed", "username": session.username, "uid": session.uid, "cookies": session.cookies}
    elif bili_code == 86101: session.status = "pending"; return {"code": 86101, "status": "pending", "message": "等待扫码"}
    elif bili_code in (86090, 86091): session.status = "scanned"; return {"code": bili_code, "status": "scanned", "message": "扫码成功，请在手机端确认"}
    else: session.status = "failed"; return {"code": bili_code, "status": "failed", "message": "扫码失败"}


# ── Routes ──────────────────────────────────────────────────

@router.post("/qrcode/generate")
async def generate_qrcode():
    session = await _generate_qrcode()
    # 返回 code:0（ok）+ data 结构，前端 LoginView 检查 data.code === 0
    return {"code": 0, "msg": "成功", "data": {
        "qrcode_key": session.qrcode_key,
        "image": f"data:image/png;base64,{session.image_base64}",
        "expires_in": 180,
    }}


@router.get("/qrcode/poll")
async def poll_qrcode(qrcode_key: str = Query(...)):
    result = await _poll_qrcode(qrcode_key)
    code = result.get("code", -1)
    # 所有状态（含 pending/scanned）都返回 code:0，data.status 区分状态
    return {"code": 0, "msg": result.get("message", "轮询成功"), "data": result}


@router.post("/qrcode/confirm")
async def confirm_qrcode(qrcode_key: str = Query(...)):
    """扫码确认 — 自动获取用户完整信息 + 保存 cookies 到文件 + DB 持久化"""
    from app.core.config import settings
    global _current_user

    async with _qr_lock:
        session = _qr_sessions.get(qrcode_key)
    if not session or session.status != "confirmed":
        raise HTTPException(status_code=400, detail="扫码未确认或已过期")

    # ── 1. 自动获取用户完整信息（复刻 src 的 try_entry_login 后半段）──
    user_info = {}
    if session.cookies:
        user_info = await _fetch_user_info(session.cookies)
        # 用获取到的 uid/username 覆盖 session 中可能为空的值
        session.uid = user_info.get("uid") or session.uid
        session.username = user_info.get("username") or session.username

    # ── 2. 保存 cookies 到文件（复刻 src 的 cookies 目录）──
    _save_cookies_to_file(session.cookies or "", session.uid or "")
    _save_user_info_to_file(user_info)

    # ── 3. 生成 JWT token ──
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    token = jwt.encode(
        {"sub": session.username or "bili_user", "uid": session.uid or "", "exp": expire, "iat": datetime.now(timezone.utc)},
        settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    # ── 4. 更新全局登录状态 ──
    _current_user = {
        "is_login": True,
        "username": session.username,
        "uid": session.uid,
        "cookies": session.cookies,
        "room_id": user_info.get("room_id", ""),
        "avatar": user_info.get("avatar", ""),
        "level": user_info.get("level", 0),
        "bili_jct": user_info.get("bili_jct", ""),
        "buvid3": user_info.get("buvid3", ""),
    }

    # ── 5. DB 持久化 ──
    try:
        from app.models import Account, async_session
        from sqlalchemy import select
        async with async_session() as db:
            result = await db.execute(select(Account).where(Account.uid == session.uid))
            acc = result.scalar_one_or_none()
            if acc:
                acc.cookies = session.cookies or ""
                acc.is_login = True
                acc.room_id = user_info.get("room_id", "")
            else:
                acc = Account(
                    username=session.username or session.uid or "unknown",
                    uid=session.uid or "",
                    cookies=session.cookies or "",
                    room_id=user_info.get("room_id", ""),
                    game="原神",
                    is_login=True,
                )
                db.add(acc)
            await db.commit()
    except Exception as e:
        logger.warning(f"[QR] auto-save failed: {e}")

    logger.info(f"[Auth] 登录成功: {session.username} (uid={session.uid}, room_id={user_info.get('room_id', '')})")

    return ok(data={
        "is_login": True,
        "username": session.username,
        "uid": session.uid,
        "cookies": session.cookies,
        "room_id": user_info.get("room_id", ""),
        "avatar": user_info.get("avatar", ""),
        "level": user_info.get("level", 0),
        "bili_jct": user_info.get("bili_jct", ""),
        "access_token": token,
        "expires_in": settings.access_token_expire_minutes * 60,
    }, msg="登录成功")


@router.get("/user/info")
async def get_current_user_info():
    """获取当前登录用户信息 — 登录后自动填充"""
    global _current_user
    if not _current_user.get("is_login"):
        # 尝试从文件加载
        try:
            user_info_path = os.path.join(CONFIG_DIR, "bili_user_info.json")
            if os.path.exists(user_info_path):
                with open(user_info_path, "r", encoding="utf-8") as f:
                    _current_user = json.load(f)
                    _current_user["is_login"] = True
        except Exception:
            pass
    if not _current_user.get("is_login"):
        return fail(ErrorCode.AUTH_REQUIRED, msg="请先登录")
    return ok(data=_current_user)


@router.post("/login")
async def login(username: str, password: str = ""):
    from app.core.config import settings
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    token = jwt.encode({"sub": username, "exp": expire, "iat": datetime.now(timezone.utc)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"is_login": True, "username": username, "access_token": token, "expires_in": settings.access_token_expire_minutes * 60}


@router.get("/status")
async def auth_status():
    return {"is_login": False, "message": "请先登录"}

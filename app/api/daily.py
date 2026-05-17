"""Daily live-room helper tasks migrated from the original day-task panel."""
from __future__ import annotations

import base64
import io
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import qrcode
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.activity_info import csrf_from_cookie, uid_from_cookie
from app.services.http_client import create_client
from app.services.snipe_engine import load_cookie_from_file

router = APIRouter(prefix="/api/daily", tags=["Daily"])
PLUS_ROOT = Path(os.environ.get("BILITOOLS_PLUS_ROOT", Path(__file__).resolve().parents[2])).resolve()
SLOT_COUNT = 4
DANMAKUS = ["打卡", "路过支持一下", "(⌒▽⌒).", "（￣▽￣）.", "(=・ω・=).", "(｀・ω・´).", "(･∀･).", "(°∀°)ﾉ."]
_logs: list[dict] = []
_entries: dict[int, dict] = {}
_qr_sessions: dict[str, dict] = {}


class LiveDailyRequest(BaseModel):
    room_id: str
    cookies: str = ""
    msg: str = ""


class AudienceCookieRequest(BaseModel):
    slot: int
    cookies: str


class AudienceActionRequest(BaseModel):
    slot: int
    room_id: str
    msg: str = ""
    duration_minutes: int = 16


def _log(level: str, msg: str) -> None:
    _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "level": level, "msg": msg})
    del _logs[:-400]


def _slot_path(slot: int) -> Path:
    if slot < 0 or slot >= SLOT_COUNT:
        raise HTTPException(status_code=400, detail="观众槽位无效")
    return PLUS_ROOT / "cookies" / f"bili_cookies_sub{slot}" / f"bili_cookies_audience{slot}.txt"


def _read_slot_cookie(slot: int) -> str:
    path = _slot_path(slot)
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _write_slot_cookie(slot: int, cookies: str) -> None:
    path = _slot_path(slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cookies.strip(), encoding="utf-8")


async def _fetch_user(cookies: str) -> dict | None:
    if not cookies:
        return None
    try:
        async with create_client(timeout=10.0, verify=False) as client:
            payload = (await client.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
            )).json()
        if payload.get("code") == 0 and payload.get("data", {}).get("isLogin"):
            data = payload["data"]
            return {"mid": data.get("mid"), "name": data.get("uname"), "avatar": data.get("face", "")}
    except Exception:
        return None
    return None


async def _require_slot(slot: int) -> tuple[str, str, dict]:
    cookies = _read_slot_cookie(slot)
    csrf = csrf_from_cookie(cookies)
    if not cookies or not csrf:
        raise HTTPException(status_code=400, detail=f"观众 {slot} 尚未保存 Cookie")
    user = await _fetch_user(cookies)
    if not user:
        raise HTTPException(status_code=400, detail=f"观众 {slot} 身份已过期")
    return cookies, csrf, user


def _require_cookies(cookies: str) -> tuple[str, str, str]:
    cookies = cookies or load_cookie_from_file()
    csrf = csrf_from_cookie(cookies)
    uid = uid_from_cookie(cookies)
    if not cookies or not csrf:
        raise HTTPException(status_code=400, detail="缺少登录 Cookie 或 bili_jct")
    return cookies, csrf, uid


@router.get("/status")
async def daily_status():
    slots = []
    for slot in range(SLOT_COUNT):
        cookies = _read_slot_cookie(slot)
        user = await _fetch_user(cookies) if cookies else None
        slots.append({
            "slot": slot,
            "has_cookie": bool(cookies),
            "is_valid": bool(user),
            "name": user.get("name") if user else "",
            "mid": user.get("mid") if user else None,
            "avatar": user.get("avatar") if user else "",
            "live_entry": _entries.get(slot),
        })
    return {"slots": slots, "logs": _logs}


@router.post("/audience/qrcode")
async def audience_qrcode(slot: int):
    _slot_path(slot)
    async with create_client(timeout=20.0, verify=False) as client:
        payload = (await client.get(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
            params={"source": "main-fe-header", "_": str(int(time.time() * 1000))},
            headers={"User-Agent": "Mozilla/5.0"},
        )).json()
    if payload.get("code") != 0:
        return {"success": False, "error": payload.get("message") or "二维码生成失败", "payload": payload}
    data = payload.get("data", {})
    qr_key = data.get("qrcode_key", "")
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(data.get("url", ""))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    _qr_sessions[qr_key] = {"slot": slot, "created_at": time.time()}
    _log("info", f"观众 {slot + 1} 扫码登录二维码已生成")
    return {"success": True, "qr_key": qr_key, "qr_url": f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}", "expires_in": 180}


@router.get("/audience/qrcode/status")
async def audience_qrcode_status(qr_key: str):
    session = _qr_sessions.get(qr_key)
    if not session:
        return {"status": "expired", "message": "二维码会话不存在或已过期"}
    if time.time() - float(session["created_at"]) > 180:
        return {"status": "expired", "message": "二维码已过期"}
    async with create_client(timeout=20.0, verify=False) as client:
        resp = await client.get(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
            params={"qrcode_key": qr_key, "source": "main-fe-header", "_": str(int(time.time() * 1000))},
            headers={"User-Agent": "Mozilla/5.0"},
        )
    payload = resp.json()
    code = payload.get("data", {}).get("code", -1)
    if code == 0:
        cookies = _cookies_from_response(resp, payload)
        if not cookies:
            return {"status": "error", "message": "登录成功但未获得 Cookie", "payload": payload}
        slot = int(session["slot"])
        _write_slot_cookie(slot, cookies)
        user = await _fetch_user(cookies)
        if not user:
            return {"status": "error", "message": "Cookie 保存后验证失败", "payload": payload}
        _log("success", f"观众 {slot + 1} {user['name']} 扫码身份已保存")
        return {"status": "success", "success": True, "slot": slot, "user": user, "payload": payload}
    if code == 86101:
        return {"status": "pending", "message": "请使用哔哩哔哩 APP 扫码"}
    if code in (86090, 86091):
        return {"status": "scanned", "message": "已扫码，请在手机端确认"}
    if code == 86038:
        return {"status": "expired", "message": "二维码已过期"}
    return {"status": "failed", "message": payload.get("message") or payload.get("data", {}).get("message") or "扫码失败", "payload": payload}


@router.post("/audience/cookie")
async def save_audience_cookie(req: AudienceCookieRequest):
    _write_slot_cookie(req.slot, req.cookies)
    user = await _fetch_user(req.cookies)
    if not user:
        _log("error", f"观众 {req.slot + 1} 身份验证失败")
        raise HTTPException(status_code=400, detail="Cookie 无效")
    _log("success", f"观众 {req.slot + 1} {user['name']} 身份已保存")
    return {"success": True, "user": user}


@router.post("/audience/validate")
async def validate_audience(req: AudienceActionRequest):
    _, _, user = await _require_slot(req.slot)
    _log("success", f"观众 {req.slot + 1} {user['name']} 已就位")
    return {"success": True, "user": user}


@router.post("/audience/enter")
async def enter_live_room(req: AudienceActionRequest):
    cookies, _, user = await _require_slot(req.slot)
    async with create_client(timeout=10.0, verify=False) as client:
        payload = (await client.get(
            "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom",
            params={"room_id": req.room_id},
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0", "Referer": f"https://live.bilibili.com/{req.room_id}"},
        )).json()
    if payload.get("code") != 0:
        _log("error", f"观众 {req.slot + 1} 进入直播间失败: code={payload.get('code')} message={payload.get('message') or payload.get('msg')}")
        return {"success": False, "payload": payload}
    expires = datetime.now() + timedelta(minutes=max(req.duration_minutes, 1))
    _entries[req.slot] = {"room_id": req.room_id, "name": user["name"], "expires_at": expires.isoformat(timespec="seconds")}
    _log("success", f"观众 {req.slot + 1} {user['name']} 进入直播间 {req.room_id}")
    return {"success": True, "payload": payload, "entry": _entries[req.slot]}


@router.post("/audience/danmaku")
async def audience_danmaku(req: AudienceActionRequest):
    cookies, csrf, user = await _require_slot(req.slot)
    payload = await _send_danmaku_payload(req.room_id, cookies, csrf, req.msg)
    ok = payload.get("code") == 0
    _log("success" if ok else "error", f"观众 {req.slot + 1} {user['name']} 发送弹幕: code={payload.get('code')} message={payload.get('message') or payload.get('msg') or req.msg or '随机弹幕'}")
    return {"success": ok, "payload": payload}


@router.post("/audience/gift")
async def audience_gift(req: AudienceActionRequest):
    cookies, csrf, user = await _require_slot(req.slot)
    uid = str(user.get("mid") or "")
    ruid = await _room_owner_uid(req.room_id, cookies)
    payload = await _send_gift_payload(req.room_id, cookies, csrf, uid, ruid)
    ok = payload.get("code") == 0
    _log("success" if ok else "error", f"观众 {req.slot + 1} {user['name']} 赠送牛蛙: code={payload.get('code')} message={payload.get('message') or payload.get('msg')}")
    return {"success": ok, "payload": payload}


@router.post("/danmaku")
async def send_danmaku(req: LiveDailyRequest):
    cookies, csrf, _ = _require_cookies(req.cookies)
    payload = await _send_danmaku_payload(req.room_id, cookies, csrf, req.msg)
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/gift")
async def send_gift(req: LiveDailyRequest):
    cookies, csrf, uid = _require_cookies(req.cookies)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少 uid")
    ruid = await _room_owner_uid(req.room_id, cookies)
    payload = await _send_gift_payload(req.room_id, cookies, csrf, uid, ruid)
    return {"success": payload.get("code") == 0, "payload": payload}


async def _send_danmaku_payload(room_id: str, cookies: str, csrf: str, msg: str = ""):
    data = {
        "color": 16777215,
        "fontsize": random.randint(18, 30),
        "mode": 1,
        "msg": msg or random.choice(DANMAKUS),
        "rnd": int(time.time()),
        "roomid": room_id,
        "bubble": 0,
        "csrf_token": csrf,
        "csrf": csrf,
    }
    async with create_client(timeout=10.0, verify=False) as client:
        return (await client.post("https://api.live.bilibili.com/msg/send", data=data, headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()


async def _room_owner_uid(room_id: str, cookies: str) -> str:
    try:
        async with create_client(timeout=10.0, verify=False) as client:
            payload = (await client.get(
                "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom",
                params={"room_id": room_id},
                headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0", "Referer": f"https://live.bilibili.com/{room_id}"},
            )).json()
        uid = payload.get("data", {}).get("room_info", {}).get("uid")
        return str(uid or "")
    except Exception:
        return ""


async def _send_gift_payload(room_id: str, cookies: str, csrf: str, uid: str, ruid: str):
    data = {
        "uid": uid,
        "gift_id": "31039",
        "ruid": ruid or uid,
        "send_ruid": "0",
        "gift_num": 1,
        "coin_type": "gold",
        "bag_id": 0,
        "platform": "pc",
        "biz_code": "Live",
        "biz_id": room_id,
        "storm_beat_id": 0,
        "metadata": "",
        "price": 100,
        "receive_users": "",
        "csrf_token": csrf,
        "csrf": csrf,
        "visit_id": "",
    }
    async with create_client(timeout=10.0, verify=False) as client:
        return (await client.post("https://api.live.bilibili.com/xlive/revenue/v1/gift/sendGold", data=data, headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()


@router.post("/watch")
async def watch_heartbeat(req: LiveDailyRequest):
    cookies, csrf, _ = _require_cookies(req.cookies)
    data = {"id": f"[{req.room_id},0,0,0]", "device": '["auto-bot","auto-bot"]', "ts": int(time.time()), "is_patch": 0, "heart_beat": [], "ua": "Mozilla/5.0", "csrf_token": csrf, "csrf": csrf, "visit_id": ""}
    async with create_client(timeout=10.0, verify=False) as client:
        payload = (await client.post("https://api.live.bilibili.com/xlive/revenue/v1/heartbeat/mobile/watch", data=data, headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/like")
async def like_live_room(req: LiveDailyRequest):
    cookies, csrf, uid = _require_cookies(req.cookies)
    data = {"uid": uid, "room_id": req.room_id, "csrf_token": csrf, "csrf": csrf, "visit_id": ""}
    async with create_client(timeout=10.0, verify=False) as client:
        payload = (await client.post("https://api.live.bilibili.com/xlive/general-interface/v1/gift/live/LikeLiveRoom", data=data, headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/share")
async def share_live_room(req: LiveDailyRequest):
    cookies, csrf, _ = _require_cookies(req.cookies)
    async with create_client(timeout=10.0, verify=False) as client:
        payload = (await client.post("https://api.bilibili.com/x/share/confirm", data={"spmid": "444.7.live", "csrf_token": csrf, "csrf": csrf}, headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.get("/bag")
async def get_gift_bag(cookies: str = ""):
    cookies = cookies or load_cookie_from_file()
    if not cookies:
        raise HTTPException(status_code=400, detail="缺少登录 Cookie")
    async with create_client(timeout=10.0, verify=False) as client:
        payload = (await client.get("https://api.live.bilibili.com/xlive/web-room/v1/gift/bag_list", headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"})).json()
    if payload.get("code") != 0:
        return {"success": False, "payload": payload}
    return {"success": True, "data": payload.get("data", {}).get("list", [])}


def _cookies_from_response(response: httpx.Response, payload: dict) -> str:
    parts = []
    for header in response.headers.get_list("set-cookie"):
        first = header.split(";", 1)[0].strip()
        if "=" in first:
            parts.append(first)
    if not parts:
        cookies = payload.get("data", {}).get("cookie_info", {}).get("cookies", [])
        parts = [f"{item['name']}={item['value']}" for item in cookies if item.get("name") and item.get("value")]
    if not parts:
        parts = [f"{name}={value}" for name, value in response.cookies.items()]
    return "; ".join(parts)

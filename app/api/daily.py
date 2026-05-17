"""Daily live-room helper tasks migrated from the original src day-task panel.

Endpoints:
  POST /api/daily/danmaku   发送弹幕
  POST /api/daily/gift      赠送礼物
  POST /api/daily/watch     看播心跳 (签到)
  POST /api/daily/like      直播间点赞
  POST /api/daily/share     分享直播间
"""
from __future__ import annotations

import random
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.activity_info import cookie_dict, csrf_from_cookie, uid_from_cookie
from app.services.snipe_engine import load_cookie_from_file

router = APIRouter(prefix="/api/daily", tags=["Daily"])

DANMAKUS = [
    "(⌒▽⌒).", "（￣▽￣）.", "(=・ω・=).", "(｀・ω・´).", "(〜￣△￣)〜.",
    "(･∀･).", "(°∀°)ﾉ.", "(￣3￣).", "╮(￣▽￣)╭.", "_(:3」∠)_.",
]


class LiveDailyRequest(BaseModel):
    room_id: str
    cookies: str = ""
    msg: str = ""


def _require_cookies(cookies: str) -> tuple[str, str, str]:
    """Load cookies, return (cookies, csrf, uid). Raise 400 if missing."""
    cookies = cookies or load_cookie_from_file()
    csrf = csrf_from_cookie(cookies)
    uid = uid_from_cookie(cookies)
    if not cookies or not csrf:
        raise HTTPException(status_code=400, detail="缺少登录 Cookie 或 bili_jct")
    return cookies, csrf, uid


@router.post("/danmaku")
async def send_danmaku(req: LiveDailyRequest):
    cookies, csrf, _ = _require_cookies(req.cookies)
    data = {
        "color": 16777215,
        "fontsize": random.randint(18, 30),
        "mode": 1,
        "msg": req.msg or random.choice(DANMAKUS),
        "rnd": int(time.time()),
        "roomid": req.room_id,
        "bubble": 0,
        "csrf_token": csrf,
        "csrf": csrf,
    }
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.post(
            "https://api.live.bilibili.com/msg/send",
            data=data,
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/gift")
async def send_gift(req: LiveDailyRequest):
    cookies, csrf, uid = _require_cookies(req.cookies)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少 uid")
    data = {
        "uid": uid,
        "gift_id": "31039",
        "ruid": uid,
        "send_ruid": "0",
        "gift_num": 1,
        "coin_type": "gold",
        "bag_id": 0,
        "platform": "pc",
        "biz_code": "Live",
        "biz_id": req.room_id,
        "storm_beat_id": 0,
        "metadata": "",
        "price": 100,
        "receive_users": "",
        "csrf_token": csrf,
        "csrf": csrf,
        "visit_id": "",
    }
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.post(
            "https://api.live.bilibili.com/xlive/revenue/v1/gift/sendGold",
            data=data,
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/watch")
async def watch_heartbeat(req: LiveDailyRequest):
    """看播心跳 — 模拟直播间观看签到 (复刻 src bili_diandian_watch)."""
    cookies, csrf, uid = _require_cookies(req.cookies)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少 uid")
    data = {
        "id": f"[{req.room_id},0,0,0]",
        "device": '["auto-bot","auto-bot"]',
        "ts": int(time.time()),
        "is_patch": 0,
        "heart_beat": [],
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "csrf_token": csrf,
        "csrf": csrf,
        "visit_id": "",
    }
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.post(
            "https://api.live.bilibili.com/xlive/revenue/v1/heartbeat/mobile/watch",
            data=data,
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/like")
async def like_live_room(req: LiveDailyRequest):
    """直播间点赞 (复刻 src bili_diandian_star 中直播间点赞逻辑)."""
    cookies, csrf, uid = _require_cookies(req.cookies)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少 uid")
    data = {
        "uid": uid,
        "room_id": req.room_id,
        "csrf_token": csrf,
        "csrf": csrf,
        "visit_id": "",
    }
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.post(
            "https://api.live.bilibili.com/xlive/general-interface/v1/gift/live/LikeLiveRoom",
            data=data,
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/share")
async def share_live_room(req: LiveDailyRequest):
    """分享直播间 (复刻 src 分享逻辑)."""
    cookies, csrf, _ = _require_cookies(req.cookies)
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.post(
            "https://api.bilibili.com/x/share/confirm",
            data={"spmid": "444.7.live", "csrf_token": csrf, "csrf": csrf},
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.get("/bag")
async def get_gift_bag(cookies: str = ""):
    """获取背包礼物列表"""
    cookies = cookies or load_cookie_from_file()
    if not cookies:
        raise HTTPException(status_code=400, detail="缺少登录 Cookie")
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        payload = (await client.get(
            "https://api.live.bilibili.com/xlive/web-room/v1/gift/bag_list",
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0"},
        )).json()
    if payload.get("code") != 0:
        return {"success": False, "payload": payload}
    return {"success": True, "data": payload.get("data", {}).get("list", [])}

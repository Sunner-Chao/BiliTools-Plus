"""Bilibili video action helpers used by the original 点点网投稿明细 workflows."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.activity_info import csrf_from_cookie
from app.services.snipe_engine import load_cookie_from_file

router = APIRouter(prefix="/api/diandian", tags=["Diandian"])


class VideoActionRequest(BaseModel):
    bvid: str = ""
    aid: str | int = ""
    cookies: str = ""
    multiply: int = 1


async def resolve_aid(req: VideoActionRequest) -> int:
    if req.aid:
        return int(req.aid)
    if not req.bvid:
        raise HTTPException(status_code=400, detail="缺少 bvid 或 aid")
    async with httpx.AsyncClient(timeout=10.0) as client:
        data = (await client.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": req.bvid})).json()
    if data.get("code") != 0:
        raise HTTPException(status_code=400, detail=data.get("message", "无法解析视频"))
    return int(data.get("data", {}).get("aid"))


async def post_action(url: str, req: VideoActionRequest, params: dict) -> dict:
    cookies = req.cookies or load_cookie_from_file()
    csrf = csrf_from_cookie(cookies)
    if not cookies or not csrf:
        raise HTTPException(status_code=400, detail="缺少登录 Cookie 或 bili_jct")
    params["csrf"] = csrf
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = (await client.post(
            url,
            params=params,
            headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0", "Referer": f"https://www.bilibili.com/video/{req.bvid}"},
        )).json()
    return {"success": payload.get("code") == 0, "payload": payload}


@router.post("/like")
async def like(req: VideoActionRequest):
    aid = await resolve_aid(req)
    return await post_action("https://api.bilibili.com/x/web-interface/archive/like", req, {"aid": aid, "like": 1, "eab_x": 1, "source": "web_normal"})


@router.post("/coin")
async def coin(req: VideoActionRequest):
    aid = await resolve_aid(req)
    return await post_action("https://api.bilibili.com/x/web-interface/coin/add", req, {"aid": aid, "multiply": req.multiply, "select_like": 0})


@router.post("/favorite")
async def favorite(req: VideoActionRequest):
    aid = await resolve_aid(req)
    return await post_action("https://api.bilibili.com/x/v3/fav/resource/deal", req, {"rid": aid, "type": 2, "add_media_ids": "", "del_media_ids": ""})


@router.post("/share")
async def share(req: VideoActionRequest):
    aid = await resolve_aid(req)
    return await post_action("https://api.bilibili.com/x/web-interface/share/add", req, {"aid": aid, "source": "web_normal"})

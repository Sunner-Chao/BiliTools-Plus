"""Activity overview helpers migrated from the original src task panel."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.services.config_loader import BILI_HEADERS, config_manager
from app.services.snipe_engine import load_cookie_from_file

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


def cookie_dict(cookies: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in cookies.split(";"):
        key, _, value = part.strip().partition("=")
        if key and value:
            parsed[key] = value
    return parsed


def csrf_from_cookie(cookies: str) -> str:
    return cookie_dict(cookies).get("bili_jct", "")


def uid_from_cookie(cookies: str) -> str:
    parsed = cookie_dict(cookies)
    return parsed.get("DedeUserID") or parsed.get("dedeuserid") or ""


async def fetch_activity_overview(game: str, source_url: str = "") -> dict[str, Any]:
    cookies = load_cookie_from_file()
    csrf = csrf_from_cookie(cookies)
    uid = uid_from_cookie(cookies)
    config = config_manager.get_config(game)

    overview: dict[str, Any] = {
        "game": game,
        "activity": await fetch_activity_page_info(source_url),
        "live_days": None,
        "submit_count": None,
        "submit_pages": None,
    }
    if config:
        overview["area_name"] = config.area_name
        overview["area_v2"] = config.area_v2
        overview["live_task_id"] = config.live_task_id

    headers = {**BILI_HEADERS, "Cookie": cookies}
    if cookies and config and config.live_task_id:
        params = {"task_ids": config.live_task_id, "web_location": 888.81821, "csrf": csrf}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                data = (await client.get("https://api.bilibili.com/x/task/totalv2", params=params, headers=headers)).json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("list", []) or []
                if items:
                    overview["live_days"] = items[0].get("accumulative_count")
        except Exception as exc:
            overview["live_days_error"] = str(exc)

    if cookies and uid:
        submit = await fetch_submit_info(uid, cookies)
        overview.update(submit)
    return overview


async def fetch_submit_info(mid: str, cookies: str, ps: int = 20) -> dict[str, Any]:
    headers = {
        "Cookie": cookies,
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/91 Mobile Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    params = {"vmid": mid, "ps": ps}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = (await client.get("https://app.bilibili.com/x/v2/space/archive/cursor", params=params, headers=headers)).json()
        if data.get("code") != 0:
            return {"submit_error": data.get("message", "获取投稿信息失败")}
        body = data.get("data", {})
        count = body.get("count", 0)
        return {
            "submit_count": count,
            "submit_pages": math.ceil(count / ps) if count else 0,
            "submit_items": body.get("item", [])[:ps],
        }
    except Exception as exc:
        return {"submit_error": str(exc)}


async def fetch_activity_page_info(url: str) -> dict[str, Any]:
    if not url:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            html = (await client.get(url, headers=BILI_HEADERS)).text
    except Exception as exc:
        return {"error": str(exc)}

    info: dict[str, Any] = {"source_url": url}
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if title:
        info["title"] = re.sub(r"\s+", " ", title.group(1)).strip()
    page_data = _extract_eva_page_data(html)
    candidates: list[tuple[str, Any]] = []
    _collect_time_fields(page_data, candidates)
    timestamps = [_normalize_timestamp(value) for _, value in candidates]
    timestamps.extend(_extract_unix_timestamps(html))
    timestamps = [item for item in timestamps if item]
    unique_timestamps = sorted({item.replace(microsecond=0) for item in timestamps})
    if len(unique_timestamps) >= 2:
        info["start_time"] = unique_timestamps[0].isoformat(timespec="seconds")
        info["end_time"] = unique_timestamps[-1].isoformat(timespec="seconds")
        remaining = int((unique_timestamps[-1] - datetime.now()).total_seconds())
        info["countdown_seconds"] = max(remaining, 0)
    return info


def _extract_unix_timestamps(html: str) -> list[datetime]:
    now = datetime.now().timestamp()
    values: list[datetime] = []
    for match in re.finditer(r"(?<!\d)(1[6-9]\d{8,10})(?!\d)", html):
        dt = _normalize_timestamp(match.group(1))
        if not dt:
            continue
        ts = dt.timestamp()
        if now - 366 * 24 * 3600 <= ts <= now + 730 * 24 * 3600:
            values.append(dt)
    return values


def _normalize_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        if value > 1_000_000_000:
            return datetime.fromtimestamp(value)
    if isinstance(value, str):
        if value.isdigit():
            return _normalize_timestamp(int(value))
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
    return None


def _collect_time_fields(value: Any, found: list[tuple[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(mark in str(key).lower() for mark in ("start", "end", "time", "stime", "etime")):
                found.append((str(key), child))
            _collect_time_fields(child, found)
    elif isinstance(value, list):
        for item in value:
            _collect_time_fields(item, found)


def _extract_eva_page_data(html: str) -> dict[str, Any]:
    marker = "window.__BILIACT_EVAPAGEDATA__ = "
    if marker not in html:
        return {}
    start = html.index(marker) + len(marker)
    level = 0
    in_string = False
    escaped = False
    end = start
    for index, ch in enumerate(html[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                level += 1
            elif ch == "}":
                level -= 1
                if level == 0:
                    end = index + 1
                    break
    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return {}

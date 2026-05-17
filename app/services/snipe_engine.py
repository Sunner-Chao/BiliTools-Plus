"""Game coupon sniping engine - core business logic.

v2.2.0 — 新增: 指数退避重试 / 令牌桶限流 / 熔断器 / fail_reason 分类
"""
import asyncio
import hashlib
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

import httpx

from app.services.websocket_manager import ws_manager
from app.services.config_loader import config_manager
from app.services.http_client import create_client
from app.core.logger import setup_logging
from app.core.rate_limiter import bili_rate_limiter, bili_circuit_breaker

logger = setup_logging()

MAX_RETRIES = 3
MAX_BACKOFF = 30.0  # 最大退避时间 30s


class TaskStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailReason(str, Enum):
    """失败原因分类"""
    OUT_OF_STOCK = "out_of_stock"
    CAPTCHA = "captcha"
    NETWORK_TIMEOUT = "network_timeout"
    RATE_LIMITED = "rate_limited"
    TOKEN_EXPIRED = "token_expired"
    UNKNOWN = "unknown"


# B站 状态码 → 失败原因映射
BILI_ERROR_MAP: dict[int, FailReason] = {
    69971: FailReason.OUT_OF_STOCK,
    -352: FailReason.CAPTCHA,
    -412: FailReason.CAPTCHA,
    401: FailReason.TOKEN_EXPIRED,
    429: FailReason.RATE_LIMITED,
}


class SnipeTask:
    """Represents a single sniping task."""

    def __init__(self, game: str, task_ids: List[str], cookies: str, period: float = 0.3, holdtime: int = 30, target_time: str = ""):
        self.id = f"snipe_{uuid.uuid4().hex[:12]}"
        self.game = game
        self.task_ids = task_ids
        self.cookies = cookies
        self.period = period
        self.holdtime = holdtime
        self.target_time = target_time
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.results: List[dict] = []
        self.logs: List[dict] = []
        self.progress = 0
        self.countdown_seconds = 0
        self._cancel_event = asyncio.Event()


class SnipeEngine:
    """Manages and executes sniping tasks."""

    def __init__(self):
        self._tasks: Dict[str, SnipeTask] = {}
        self._running: Dict[str, asyncio.Task] = {}
        self._immediate_queue: asyncio.Queue = asyncio.Queue()

    def create_task(self, game: str, task_ids: List[str], cookies: str, **kwargs) -> SnipeTask:
        task = SnipeTask(game=game, task_ids=task_ids, cookies=cookies, **kwargs)
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[SnipeTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[dict]:
        return [
            {
                "id": t.id,
                "game": t.game,
                "status": t.status.value,
                "task_count": len(t.task_ids),
                "created_at": t.created_at,
                "started_at": t.started_at,
                "progress": t.progress,
                "target_time": t.target_time,
                "countdown_seconds": t.countdown_seconds,
                "results": t.results,
                "logs": t.logs[-200:],
            }
            for t in self._tasks.values()
        ]

    async def delete_task(self, task_id: str):
        await self.cancel_task(task_id)
        self._tasks.pop(task_id, None)
        self._running.pop(task_id, None)

    async def start_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task or task.status == TaskStatus.RUNNING:
            return

        task.started_at = datetime.now(timezone.utc).isoformat()
        async_task = asyncio.create_task(self._wait_and_execute(task))
        self._running[task_id] = async_task

    async def enqueue_immediate(self, product_id: str):
        """开售瞬间立即入队，不走排序"""
        await self._immediate_queue.put(product_id)

    async def cancel_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task._cancel_event.set()
            task.status = TaskStatus.CANCELLED
            if task_id in self._running:
                self._running[task_id].cancel()
            await ws_manager.send_log("warn", f"任务 {task_id} 已取消", task_id)

    def _log(self, task: SnipeTask, level: str, msg: str):
        entry = {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "msg": msg}
        task.logs.append(entry)
        task.logs = task.logs[-400:]
        asyncio.create_task(ws_manager.send_log(level, msg, task.id))

    async def _wait_and_execute(self, task: SnipeTask):
        if task.target_time:
            try:
                target = datetime.fromisoformat(task.target_time.replace("Z", "+00:00")).replace(tzinfo=None)
                task.status = TaskStatus.WAITING
                self._log(task, "info", f"等待目标时间 {target.strftime('%Y-%m-%d %H:%M:%S')}")
                while not task._cancel_event.is_set():
                    remaining = int((target - datetime.now()).total_seconds())
                    task.countdown_seconds = max(remaining, 0)
                    if remaining <= 0:
                        break
                    await asyncio.sleep(1)
            except Exception as exc:
                self._log(task, "error", f"目标时间格式错误: {exc}")
        if task._cancel_event.is_set():
            return
        task.countdown_seconds = 0
        task.status = TaskStatus.RUNNING
        self._log(task, "info", f"任务 {task.id} 开始执行")
        await self._execute(task)

    async def _execute_with_retry(self, client: httpx.AsyncClient, task: SnipeTask,
                                   item: dict, headers: dict) -> dict:
        """单个 item 的执行 + 指数退避重试 + 限流 + 熔断"""
        item = await self._enrich_task_item(client, item, task.cookies)
        task_id = item["id"]
        name = item.get("name") or item.get("taskName") or task_id
        activity_id = item.get("activityId")
        if not activity_id:
            return {
                "task_id": task_id, "name": name, "status": "failed",
                "fail_reason": "missing_activity_id",
                "message": item.get("queryMessage") or item.get("queryError") or "mission/info 未返回 activity_id",
                "retry_count": 0,
            }

        for attempt in range(MAX_RETRIES + 1):
            # 熔断器检查
            if bili_circuit_breaker.is_open():
                logger.warning("[Snipe] 熔断器打开，等待 60s 恢复")
                await asyncio.sleep(60)

            # 限流器检查
            if not await bili_rate_limiter.acquire():
                logger.warning("[Snipe] 触发本地限流，等待 5s")
                await asyncio.sleep(5)
                if not await bili_rate_limiter.acquire():
                    return {
                        "task_id": task_id, "status": "failed",
                        "fail_reason": FailReason.RATE_LIMITED.value,
                        "retry_count": attempt,
                    }

            try:
                wts, w_rid = _generate_wbi_signature()
                data = {
                    "csrf": _csrf_from_cookie(task.cookies),
                    "task_id": task_id,
                    "activity_id": activity_id,
                    "activity_name": item.get("activityName", ""),
                    "task_name": item.get("taskName") or name,
                    "reward_name": item.get("awardName") or item.get("description") or name,
                    "gaia_vtoken": "",
                    "receive_from": "missionPage",
                }
                resp = await client.post(
                    "https://api.bilibili.com/x/activity_components/mission/receive",
                    params={"w_rid": w_rid, "wts": wts},
                    data=data,
                    headers={**headers, "Referer": f"https://www.bilibili.com/blackboard/new-award-exchange.html?task_id={task_id}"},
                )
                payload = resp.json()
                code = payload.get("code")
                msg = payload.get("message") or payload.get("msg") or str(payload)
                done = code in (0, 202031)
                if not done and code not in (202120, 75255, -702, -705, -509):
                    resp.raise_for_status()

                bili_circuit_breaker.record_success()
                result = {
                    "task_id": task_id,
                    "name": name,
                    "code": code,
                    "status": "success" if done else "failed",
                    "fail_reason": None if done else _classify_receive_code(code),
                    "message": msg,
                    "retry_count": attempt,
                    "activityId": activity_id,
                    "awardName": item.get("awardName"),
                    "response_time_ms": int(task.period * 1000),
                }
                if done:
                    cdkey = await self._query_cdkey(client, item, task.cookies)
                    if cdkey:
                        result["cdkey"] = cdkey
                        result["message"] = f"{msg}，兑换码: {cdkey}"
                return result

            except httpx.TimeoutException:
                bili_circuit_breaker.record_failure()
                fail_reason = FailReason.NETWORK_TIMEOUT
            except httpx.HTTPStatusError as e:
                bili_circuit_breaker.record_failure()
                fail_reason = BILI_ERROR_MAP.get(e.response.status_code, FailReason.UNKNOWN)
            except Exception as e:
                bili_circuit_breaker.record_failure()
                logger.error(f"[Snipe] 非预期异常: {e}")
                fail_reason = FailReason.UNKNOWN

            # 指数退避 + 抖动
            if attempt < MAX_RETRIES:
                base = min(2 ** attempt, MAX_BACKOFF)
                jitter = random.uniform(base, base * 2)
                logger.info(f"[Snipe] 重试 {attempt + 1}/{MAX_RETRIES}，等待 {jitter:.1f}s")
                await asyncio.sleep(jitter)
            else:
                return {
                    "task_id": task_id, "status": "failed",
                    "fail_reason": fail_reason.value,
                    "retry_count": attempt,
                }

    async def _execute(self, task: SnipeTask):
        """Execute the sniping task with retry, rate limiting, and circuit breaker."""
        total = len(task.task_ids)
        success = 0
        selected = _task_items_for_ids(task.game, task.task_ids)

        completed: set[str] = set()
        deadline = time.monotonic() + max(task.holdtime, 1)
        async with create_client(timeout=10.0) as client:
            while time.monotonic() < deadline and len(completed) < total and not task._cancel_event.is_set():
                for i, item in enumerate(selected):
                    if task._cancel_event.is_set():
                        break
                    item_id = item["id"]
                    if item_id in completed:
                        continue

                    await ws_manager.send_progress(len(completed), total, task.id)
                    task.progress = int(len(completed) / max(total, 1) * 100)
                    self._log(task, "info", f"正在抢兑 [{i+1}/{total}] {item.get('name', item_id)} ({item_id})")

                    headers = {
                        "Cookie": task.cookies,
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.bilibili.com",
                    }

                    result = await self._execute_with_retry(client, task, item, headers)
                    task.results.append(result)

                    if result["status"] == "success":
                        success += 1
                        completed.add(item_id)
                        task.progress = int(len(completed) / max(total, 1) * 100)
                        self._log(task, "success", f"{result.get('name', item_id)}: {result.get('message', '抢兑成功')}")
                    else:
                        self._log(task, "error", f"{result.get('name', item_id)} 失败: {result.get('message') or result['fail_reason']}")
                    await asyncio.sleep(max(task.period, 0.05))

        task.status = TaskStatus.SUCCESS if success == total else TaskStatus.FAILED
        await ws_manager.send_task_status(task.id, task.status.value, {"success": success, "total": total})
        self._log(task, "info", f"任务完成: {success}/{total} 成功")

        self._running.pop(task.id, None)

    async def _enrich_task_item(self, client: httpx.AsyncClient, item: dict, cookies: str) -> dict:
        if item.get("activityId") and item.get("awardName"):
            return item
        task_id = item["id"]
        wts, w_rid = _generate_wbi_signature(task_id=task_id, web_location=888.81821)
        try:
            resp = await client.get(
                "https://api.bilibili.com/x/activity_components/mission/info",
                params={"task_id": task_id, "web_location": 888.81821, "w_rid": w_rid, "wts": wts},
                headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0", "Referer": f"https://www.bilibili.com/blackboard/era/award-exchange.html?task_id={task_id}"},
            )
            payload = resp.json()
            if payload.get("code") != 0:
                return {**item, "queryCode": payload.get("code"), "queryMessage": payload.get("message") or payload.get("msg")}
            data = payload.get("data", {})
            reward = data.get("reward_info") or {}
            stock = data.get("stock_info") or {}
            return {
                **item,
                "activityId": data.get("act_id"),
                "activityName": data.get("act_name"),
                "taskName": data.get("task_name") or item.get("taskName"),
                "awardName": reward.get("award_name") or item.get("awardName"),
                "dayStock": stock.get("day_stock"),
                "totalStock": stock.get("total_stock"),
                "taskStatus": data.get("status"),
            }
        except Exception as exc:
            return {**item, "queryError": str(exc)}

    async def _query_cdkey(self, client: httpx.AsyncClient, item: dict, cookies: str) -> str | None:
        activity_id = item.get("activityId")
        award_name = item.get("awardName")
        if not activity_id or not award_name:
            return None
        wts, w_rid = _generate_wbi_signature(activity_id=activity_id, web_location=888.81821)
        try:
            resp = await client.get(
                "https://api.bilibili.com/x/activity_components/mission/mylist",
                params={"activity_id": activity_id, "web_location": 888.81821, "w_rid": w_rid, "wts": wts},
                headers={"Cookie": cookies, "User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/blackboard/era/award-exchange.html"},
            )
            payload = resp.json()
            if payload.get("code") != 0:
                return None
            for record in (payload.get("data") or {}).get("list", []) or []:
                if record.get("award_name") == award_name:
                    return (record.get("extra_info") or {}).get("cdkey_content")
        except Exception:
            return None
        return None


def _generate_wbi_signature(**kwargs) -> tuple[int, str]:
    wts = int(time.time())
    params = {**kwargs, "wts": wts}
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return wts, hashlib.md5((query + "ea1db124af3c7062474693fa704f4ff8").encode("utf-8")).hexdigest()


def _csrf_from_cookie(cookies: str) -> str:
    for part in cookies.split(";"):
        key, _, value = part.strip().partition("=")
        if key == "bili_jct":
            return value
    return ""


def _classify_receive_code(code: int | None) -> str:
    return {
        202100: FailReason.CAPTCHA.value,
        202120: "not_started",
        202032: "not_eligible",
        202033: "expired",
        75255: FailReason.OUT_OF_STOCK.value,
        -702: FailReason.RATE_LIMITED.value,
        -705: FailReason.RATE_LIMITED.value,
        -509: FailReason.RATE_LIMITED.value,
    }.get(code, FailReason.UNKNOWN.value)


def _task_items_for_ids(game: str, ids: List[str]) -> List[dict]:
    configured = {item["id"]: item for item in config_manager.get_tasks(game)}
    return [configured.get(task_id, {"id": task_id, "name": task_id}) for task_id in ids]


def load_cookie_from_file() -> str:
    root = Path(os.environ.get("BILITOOLS_PLUS_ROOT", Path(__file__).resolve().parents[2])).resolve()
    path = root / "cookies" / "bili_cookies.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("COOKIES", "")
    except Exception:
        return ""


# Singleton
snipe_engine = SnipeEngine()

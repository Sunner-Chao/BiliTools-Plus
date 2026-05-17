"""WebSocket connection manager — v2.2.0

新增: token 认证 / stock_change 事件 / request_snipe handler / EventBuffer 重放
"""
import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from fastapi import WebSocket


class EventBuffer:
    """环形 buffer — 缓存最近 20 条事件，重连时 replay"""

    def __init__(self, maxlen: int = 20):
        self._buffer: dict[str, deque] = {}
        self._replaying_tasks: set[str] = set()
        self._event_counter: int = 0
        self._lock = asyncio.Lock()

    def append(self, task_id: str, event: dict):
        self._event_counter += 1
        event["event_id"] = self._event_counter
        if task_id not in self._buffer:
            self._buffer[task_id] = deque(maxlen=20)
        self._buffer[task_id].append(event)

    async def replay(self, ws: WebSocket, task_id: str):
        async with self._lock:
            self._replaying_tasks.add(task_id)
        try:
            for event in self._buffer.get(task_id, []):
                await ws.send_text(json.dumps(event))
        finally:
            async with self._lock:
                self._replaying_tasks.discard(task_id)

    def should_broadcast(self, task_id: str) -> bool:
        return task_id not in self._replaying_tasks


class SnipeRequestGuard:
    """request_snipe 超频防护 — 每用户每秒最多 1 次"""

    def __init__(self):
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def should_allow(self, user_id: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            last = self._last_request.get(user_id, 0)
            if now - last < 1.0:
                return False
            self._last_request[user_id] = now
            return True


class WebSocketManager:
    """Manages WebSocket connections with auth, events, and replay."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._global_connections: Set[WebSocket] = set()
        self._authenticated: Set[WebSocket] = set()
        self.event_buffer = EventBuffer()
        self.snipe_guard = SnipeRequestGuard()
        self._event_counter: int = 0

    async def connect(self, websocket: WebSocket, task_id: str = "global", authenticated: bool = False):
        await websocket.accept()
        if authenticated:
            self._authenticated.add(websocket)
        if task_id == "global":
            self._global_connections.add(websocket)
        else:
            if task_id not in self._connections:
                self._connections[task_id] = set()
            self._connections[task_id].add(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str = "global"):
        self._authenticated.discard(websocket)
        if task_id == "global":
            self._global_connections.discard(websocket)
        elif task_id in self._connections:
            self._connections[task_id].discard(websocket)

    async def broadcast(self, message: dict, task_id: str = "global"):
        """Broadcast message to all connections for a task (or global)."""
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.event_buffer.append(task_id, message)
        data = json.dumps(message)

        connections = (
            self._global_connections if task_id == "global"
            else self._connections.get(task_id, set())
        )

        dead = []
        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            if task_id == "global":
                self._global_connections.discard(ws)
            elif task_id in self._connections:
                self._connections[task_id].discard(ws)
            self._authenticated.discard(ws)

    async def send_log(self, level: str, message: str, task_id: str = "global"):
        await self.broadcast({
            "type": "log", "level": level, "message": message, "task_id": task_id,
        }, task_id)

    async def send_progress(self, current: int, total: int, task_id: str):
        await self.broadcast({
            "type": "progress", "current": current, "total": total,
            "percent": round(current / total * 100, 1) if total > 0 else 0,
            "task_id": task_id,
        }, task_id)

    async def send_task_status(self, task_id: str, status: str, result: dict = None):
        await self.broadcast({
            "type": "task_status", "task_id": task_id, "status": status,
            "result": result or {},
        }, task_id)

    async def send_stock_change(self, product_id: str, product_name: str,
                                 new_stock: int, price: float = 0):
        """推送库存变动事件 (P6)"""
        await self.broadcast({
            "type": "stock_change",
            "product_id": product_id,
            "product_name": product_name,
            "new_stock": new_stock,
            "price": price,
        }, "global")

    async def send_request_rejected(self, ws: WebSocket, reason: str):
        """向单个客户端推送请求被拒事件"""
        await ws.send_text(json.dumps({
            "type": "request_rejected",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    @property
    def active_count(self) -> int:
        return len(self._global_connections)


# Singleton instance
ws_manager = WebSocketManager()

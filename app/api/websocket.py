"""WebSocket endpoints — v2.2.0

新增: token 认证 (4001) / request_snipe handler / replay 支持
"""
import json
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import ws_manager
from app.core.logger import setup_logging

logger = setup_logging()

router = APIRouter()

# 模拟已认证用户存储（生产环境替换为 JWT 解签）
_authenticated_tokens: dict[str, str] = {}  # token -> username


def register_token(token: str, username: str):
    """注册已认证 token（由 auth 模块调用）"""
    _authenticated_tokens[token] = username


async def _validate_ws_token(token: str | None) -> str | None:
    """验证 WS token，返回 username 或 None"""
    if not token:
        return None
    return _authenticated_tokens.get(token)


async def _handle_ws_messages(websocket: WebSocket, username: str):
    """处理 WS 客户端消息（request_snipe / request_replay / ping）"""
    while True:
        data = await websocket.receive_text()

        if data == "ping":
            await websocket.send_text('{"type":"pong"}')
            continue

        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            continue

        event = msg.get("event")

        if event == "request_replay":
            task_ids = msg.get("task_ids", [])
            for tid in task_ids:
                await ws_manager.event_buffer.replay(websocket, tid)

        elif event == "request_snipe":
            product_id = msg.get("product_id")
            if not product_id:
                continue
            # 超频防护
            if not await ws_manager.snipe_guard.should_allow(username):
                await ws_manager.send_request_rejected(websocket, "操作过于频繁，请稍后再试")
                continue
            # 触发立即抢码
            from app.services.snipe_engine import snipe_engine
            await snipe_engine.enqueue_immediate(product_id)
            logger.info(f"[WS] 用户 {username} 触发即时抢码: {product_id}")


@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket, token: str = Query(None)):
    """主 WebSocket endpoint — token 认证 + 五事件 + request_snipe"""
    username = await _validate_ws_token(token)
    if not username:
        await websocket.accept()
        await websocket.close(code=4001, reason="未授权")
        return

    await ws_manager.connect(websocket, "global", authenticated=True)
    # 发送连接成功确认
    await websocket.send_text(json.dumps({"type": "connected", "msg": "连接成功"}))

    try:
        await _handle_ws_messages(websocket, username)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "global")
        logger.info(f"[WS] 用户 {username} 断开连接")


@router.websocket("/ws/logs/{task_id}")
async def websocket_task_logs(websocket: WebSocket, task_id: str, token: str = Query(None)):
    """任务日志 WS — 带 token 认证"""
    username = await _validate_ws_token(token)
    if not username:
        await websocket.accept()
        await websocket.close(code=4001, reason="未授权")
        return

    await ws_manager.connect(websocket, task_id, authenticated=True)
    try:
        await _handle_ws_messages(websocket, username)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)


@router.websocket("/ws/logs")
async def websocket_global_logs(websocket: WebSocket, token: str = Query(None)):
    """全局日志 WS — 带 token 认证"""
    username = await _validate_ws_token(token)
    if not username:
        await websocket.accept()
        await websocket.close(code=4001, reason="未授权")
        return

    await ws_manager.connect(websocket, "global", authenticated=True)
    try:
        await _handle_ws_messages(websocket, username)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "global")

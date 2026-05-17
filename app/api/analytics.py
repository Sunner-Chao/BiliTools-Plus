"""Real business analytics for BiliTools-Plus."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from app.api.auth import _credential_meta
from app.api.daily import daily_status
from app.api.live import _live_state
from app.services.config_loader import config_manager
from app.services.snipe_engine import snipe_engine

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
async def summary():
    tasks = snipe_engine.list_tasks()
    total = len(tasks)
    completed = len([item for item in tasks if item.get("status") == "success"])
    failed = len([item for item in tasks if item.get("status") == "failed"])
    running = len([item for item in tasks if item.get("status") in ("running", "waiting")])
    pending = len([item for item in tasks if item.get("status") in ("created", "pending")])
    games = []
    for game in config_manager.get_all_games():
        game_tasks = [item for item in tasks if item.get("game") == game["id"]]
        game_completed = len([item for item in game_tasks if item.get("status") == "success"])
        games.append({
            "id": game["id"],
            "name": game["name"],
            "created_tasks": len(game_tasks),
            "configured_tasks": game.get("task_count", 0),
            "completed": game_completed,
            "failed": len([item for item in game_tasks if item.get("status") == "failed"]),
            "rate": round(game_completed / max(len(game_tasks), 1) * 100),
            "area_v2": game.get("area_v2"),
        })
    daily = await daily_status()
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "running_tasks": running,
        "pending_tasks": pending,
        "success_rate": round(completed / max(total, 1) * 100, 1),
        "games": games,
        "recent": [
            {
                "time": item.get("started_at") or item.get("created_at"),
                "action": f"{item.get('game')} 抢码任务",
                "status": item.get("status"),
                "progress": item.get("progress", 0),
            }
            for item in sorted(tasks, key=lambda task: task.get("created_at") or "", reverse=True)[:20]
        ],
        "live": {
            "is_living": _live_state.is_living,
            "room_id": _live_state.room_id,
            "game": _live_state.game,
            "start_time": _live_state.start_time,
            "video_file": _live_state.video_file,
        },
        "credential": _credential_meta(),
        "daily": {
            "audience_slots": daily.get("slots", []),
            "log_count": len(daily.get("logs", [])),
        },
    }

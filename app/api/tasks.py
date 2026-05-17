from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.logger import setup_logging
from app.services.config_loader import config_manager
from app.services.activity_info import fetch_activity_overview
from app.services.snipe_engine import load_cookie_from_file, snipe_engine

logger = setup_logging()
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

GAME_MAP = {
    "genshin": {"id": "genshin", "name": "原神", "color": "#f5c542"},
    "starrail": {"id": "starrail", "name": "星穹铁道", "color": "#4fc3f7"},
    "zzz": {"id": "zzz", "name": "绝区零", "color": "#ef5350"},
    "wutheringwaves": {"id": "wutheringwaves", "name": "鸣潮", "color": "#66bb6a"},
}


class TaskExecuteRequest(BaseModel):
    game: str
    tasks: list[str] = []
    period: float = 0.3
    holdtime: int = 30
    cookies: str = ""
    target_time: str = ""


@router.get("")
async def list_tasks(game: str = Query(default="", description="游戏标识")):
    if game:
        config_tasks = config_manager.get_tasks(game)
        if config_tasks:
            return {"game": game, "tasks": config_tasks, "count": len(config_tasks)}
        tasks = [{"id": "wish", "name": "祈愿抽奖", "status": "idle"},
                 {"id": "coupon", "name": "兑换码抢兑", "status": "idle"}]
        return {"game": game, "tasks": tasks, "count": len(tasks)}
    return {"games": list(GAME_MAP.values()), "count": len(GAME_MAP)}


@router.get("/games")
async def list_games_with_tasks():
    """Get all games with their task counts from config files."""
    games = config_manager.get_all_games()
    return {"games": games, "count": len(games)}


@router.get("/overview")
async def task_overview(
    game: str = Query(default="genshin"),
    source_url: str = Query(default="https://www.bilibili.com/blackboard/era/n2drQa9NUK5Xruku.html?spm_id_from=333.337.0.0"),
):
    return await fetch_activity_overview(game, source_url)


class RefreshConfigRequest(BaseModel):
    game: str
    url: str


@router.post("/refresh")
async def refresh_config(req: RefreshConfigRequest):
    result = await config_manager.refresh_from_url(req.game, req.url)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "刷新失败"))
    return result


@router.post("/execute")
async def execute_task(req: TaskExecuteRequest):
    if req.game not in GAME_MAP:
        raise HTTPException(status_code=400, detail=f"未知游戏: {req.game}")

    # Auto-load task IDs from config if not provided
    task_ids = req.tasks
    if not task_ids:
        config_tasks = config_manager.get_tasks(req.game)
        task_ids = [t["id"] for t in config_tasks]

    if not task_ids:
        raise HTTPException(status_code=400, detail="无可用任务ID")

    cookies = req.cookies or load_cookie_from_file()
    if not cookies:
        raise HTTPException(status_code=400, detail="缺少 B 站 Cookie，请先扫码登录或填写 cookies")

    task = snipe_engine.create_task(
        game=req.game, task_ids=task_ids, cookies=cookies,
        period=req.period, holdtime=req.holdtime, target_time=req.target_time,
    )
    await snipe_engine.start_task(task.id)

    logger.info(f"任务执行: {req.game}, task_id={task.id}, items={len(task_ids)}")
    return {
        "task_id": task.id, "status": "started",
        "message": f"{GAME_MAP[req.game]['name']}任务已提交",
        "game": req.game, "item_count": len(task_ids),
    }


@router.get("/status")
async def task_status_all():
    return {"tasks": snipe_engine.list_tasks(), "count": len(snipe_engine.list_tasks())}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    await snipe_engine.cancel_task(task_id)
    return {"task_id": task_id, "status": "cancelled"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    await snipe_engine.delete_task(task_id)
    return {"task_id": task_id, "status": "deleted"}

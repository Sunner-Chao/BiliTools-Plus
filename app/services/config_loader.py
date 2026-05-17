"""Game config loader — 完整复刻 src/config/ 配置结构 + 动态抓取

配置结构（复刻 src/config/bili_config_genshin.json）：
{
    "TASKS": [
        {"任务名": {"id": "xxx", "description": "xxx"}},
        ...
    ],
    "area_name": "原神",
    "live_task_ids": "6ERA4wloghvk5p00",
    "area_v2": 321
}
"""
import json, logging, re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

BILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


class GameConfig:
    """Represents a single game configuration."""
    
    def __init__(self, game_key: str, data: dict):
        self.game_key = game_key
        self.area_name: str = data.get("area_name", game_key)
        self.live_task_id: str = data.get("live_task_ids", "")
        self.area_v2: int = data.get("area_v2", 0)
        self.tasks: List[dict] = []
        
        # Parse nested tasks structure
        for task_group in data.get("TASKS", []):
            for task_name, task_info in task_group.items():
                if _looks_like_non_exchange_milestone(task_name, task_info):
                    continue
                self.tasks.append({
                    "id": task_info.get("id", ""),
                    "name": task_name,
                    "description": task_info.get("description", ""),
                    "awardName": task_info.get("awardName") or task_info.get("description", ""),
                    "activityId": task_info.get("activityId", ""),
                    "activityName": task_info.get("activityName", ""),
                    "taskName": task_info.get("taskName", task_name),
                    "url": task_info.get("url") or f"https://www.bilibili.com/blackboard/era/award-exchange.html?task_id={task_info.get('id', '')}",
                })


class ConfigManager:
    """Manages all game configurations."""
    
    GAME_FILES = {
        "genshin": "bili_config_genshin.json",
        "starrail": "bili_config_starrail.json",
        "zzz": "bili_config_zzz.json",
        "wutheringwaves": "bili_config_wutheringwaves.json",
    }
    
    def __init__(self):
        self._configs: Dict[str, GameConfig] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all game config files."""
        for game_key, filename in self.GAME_FILES.items():
            filepath = CONFIG_DIR / filename
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._configs[game_key] = GameConfig(game_key, data)
    
    def get_config(self, game_key: str) -> Optional[GameConfig]:
        """Get config for a specific game."""
        return self._configs.get(game_key)
    
    def get_tasks(self, game_key: str) -> List[dict]:
        """Get all tasks for a game."""
        config = self.get_config(game_key)
        return config.tasks if config else []
    
    def get_all_games(self) -> List[dict]:
        """Get list of all available games."""
        games = []
        for key, config in self._configs.items():
            games.append({
                "id": key,
                "name": config.area_name,
                "task_count": len(config.tasks),
                "area_v2": config.area_v2,
            })
        return games

    async def refresh_from_url(self, game_key: str, url: str) -> dict:
        if game_key not in self.GAME_FILES:
            return {"success": False, "error": f"未知游戏: {game_key}"}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=BILI_HEADERS)
            resp.raise_for_status()
        old = self.get_config(game_key)
        old_data = {
            "area_name": old.area_name if old else game_key,
            "area_v2": old.area_v2 if old else 0,
            "live_task_ids": old.live_task_id if old else "",
        }
        data = _parse_blackboard_page(resp.text, old_data)
        data["source_url"] = url
        path = CONFIG_DIR / self.GAME_FILES[game_key]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        self._load_all()
        return {"success": True, "game": game_key, "task_count": len(self.get_tasks(game_key)), "config_file": str(path)}


def _looks_like_non_exchange_milestone(name: str, task_info: dict[str, Any]) -> bool:
    return "里程碑" in name and "-" not in name and not task_info.get("url") and not task_info.get("activityId")


def _parse_blackboard_page(html: str, fallback: dict[str, Any]) -> dict[str, Any]:
    page_data = _extract_eva_page_data(html)
    task_items: list[dict[str, Any]] = []
    _collect_task_items(page_data, task_items)
    tasks: dict[str, dict[str, Any]] = {}
    live_task_id = fallback.get("live_task_ids", "")
    for item in task_items:
        task_name = str(item.get("taskName") or item.get("name") or "").strip()
        parent_task_id = str(item.get("taskId") or "").strip()
        award_name = str(item.get("awardName") or "").strip()
        checkpoints = item.get("checkpoints") or []
        has_exchange_checkpoints = any(
            str(checkpoint.get("ztasksid") or "").strip()
            and str(checkpoint.get("ztasksid") or "").strip() != parent_task_id
            for checkpoint in checkpoints
        )
        if task_name and parent_task_id and not has_exchange_checkpoints:
            label = f"{task_name}({award_name})" if award_name and award_name not in task_name else task_name
            tasks[label] = {
                "id": parent_task_id,
                "description": award_name or task_name,
                "awardName": award_name,
                "taskName": task_name,
                "url": f"https://www.bilibili.com/blackboard/era/award-exchange.html?task_id={parent_task_id}",
            }
            if not live_task_id and "开播" in task_name:
                live_task_id = parent_task_id
        for checkpoint in checkpoints:
            task_id = str(checkpoint.get("ztasksid") or "").strip()
            checkpoint_award = str(checkpoint.get("awardname") or "").strip()
            alias = str(checkpoint.get("alias") or "").strip()
            if task_id and task_id != parent_task_id:
                label_parts = [part for part in (task_name, alias) if part]
                label = "-".join(label_parts) if label_parts else checkpoint_award
                if checkpoint_award and checkpoint_award not in label:
                    label = f"{label}({checkpoint_award})"
                previous = tasks.get(label)
                tasks[label] = {
                    **(previous or {}),
                    "id": task_id,
                    "description": checkpoint_award,
                    "awardName": checkpoint_award,
                    "alias": alias,
                    "taskName": task_name,
                    "url": f"https://www.bilibili.com/blackboard/era/award-exchange.html?task_id={task_id}",
                }
    return {
        "TASKS": [tasks] if tasks else [],
        "area_name": fallback.get("area_name", ""),
        "live_task_ids": live_task_id,
        "area_v2": fallback.get("area_v2", 0),
    } if tasks else fallback


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


def _collect_task_items(value: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        task_item = value.get("taskItem")
        if isinstance(task_item, dict) and task_item.get("taskId"):
            found.append(task_item)
        for child in value.values():
            _collect_task_items(child, found)
    elif isinstance(value, list):
        for item in value:
            _collect_task_items(item, found)


# Singleton instance
config_manager = ConfigManager()

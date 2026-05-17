"""
Bili-Live FFmpeg推流管理
复刻 src/bili_ffmpeg.py 功能
"""
import asyncio
import json
import os
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

LOG_DIR = Path("logs/ffmpeg")
LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StreamTask:
    task_id: str
    room_id: str
    title: str
    category: str
    quality: str
    start_time: str
    duration_min: int
    stream_url: str
    rtmp_url: str = ""
    status: str = "pending"
    started_at: Optional[float] = None
    process: Optional[int] = None


class BiliFFmpegManager:
    def __init__(self):
        self.tasks: dict[str, StreamTask] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self, room_id: str, title: str, category: str,
        quality: str, start_time: str, duration_min: int,
        stream_url: str, task_id: Optional[str] = None
    ) -> StreamTask:
        async with self._lock:
            tid = task_id or f"stream_{int(time.time() * 1000)}"
            task = StreamTask(
                task_id=tid, room_id=room_id, title=title, category=category,
                quality=quality, start_time=start_time, duration_min=duration_min,
                stream_url=stream_url,
                rtmp_url=f"rtmp://live-push.bilivideo.com/live-bvc/{room_id}"
            )
            self.tasks[tid] = task
            return task

    async def start_stream(self, task_id: str) -> dict:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return {"code": 404, "msg": "任务不存在"}
            if task.status == "running":
                return {"code": 400, "msg": "任务已在运行中"}

        ffmpeg_path = self._find_ffmpeg()
        if not ffmpeg_path:
            return {"code": 500, "msg": "未找到 ffmpeg，请检查 execute/ffmpeg.exe"}

        log_file = LOG_DIR / f"{task_id}.log"
        try:
            cmd = [
                ffmpeg_path, "-re", "-stream_loop", "-1",
                "-i", task.stream_url,
                "-c:v", "copy", "-c:a", "copy",
                "-f", "flv", "-y", task.rtmp_url
            ]
            with open(log_file, "w") as f:
                proc = subprocess.Popen(
                    cmd, stdout=f, stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid if os.name != "nt" else None
                )
            async with self._lock:
                task.status = "running"
                task.process = proc.pid
                task.started_at = time.time()
                self.processes[task_id] = proc
            self._append_log(task_id, f"[{self._ts()}] 推流进程已启动 PID={proc.pid}")
            return {"code": 0, "msg": "推流已启动", "data": {"task_id": task_id, "pid": proc.pid}}
        except Exception as e:
            async with self._lock:
                task.status = "failed"
            self._append_log(task_id, f"[{self._ts()}] 推流启动失败: {e}")
            return {"code": 500, "msg": f"推流启动失败: {e}"}

    async def stop_stream(self, task_id: str) -> dict:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return {"code": 404, "msg": "任务不存在"}
            proc = self.processes.get(task_id)
            if proc:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=5)
                except Exception:
                    pass
                del self.processes[task_id]
            task.status = "stopped"
            self._append_log(task_id, f"[{self._ts()}] 推流已停止")
            return {"code": 0, "msg": "推流已停止", "data": {"task_id": task_id}}

    async def get_task_status(self, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if not task:
            return {"code": 404, "msg": "任务不存在"}
        proc = self.processes.get(task_id)
        is_alive = proc is not None and proc.poll() is None
        elapsed = int(time.time() - task.started_at) if task.started_at and is_alive else 0
        return {
            "code": 0, "msg": "success",
            "data": {
                "task_id": task_id, "status": task.status,
                "is_running": is_alive, "elapsed_sec": elapsed,
                "pid": proc.pid if is_alive else None,
                "title": task.title, "quality": task.quality,
                "category": task.category, "start_time": task.start_time
            }
        }

    def list_tasks(self) -> list:
        return [
            {"task_id": t.task_id, "status": t.status, "title": t.title,
             "category": t.category, "quality": t.quality, "start_time": t.start_time}
            for t in self.tasks.values()
        ]

    def _find_ffmpeg(self) -> Optional[str]:
        paths = ["execute/ffmpeg.exe", "execute/ffmpeg", "ffmpeg"]
        for p in paths:
            if os.path.exists(p):
                return p
        import shutil
        return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")

    def _append_log(self, task_id: str, line: str):
        log_file = LOG_DIR / f"{task_id}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")

    def _ts(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_recent_logs(self, task_id: str, lines: int = 50) -> list[str]:
        log_file = LOG_DIR / f"{task_id}.log"
        if not log_file.exists():
            return []
        with open(log_file, "r", encoding="utf-8") as f:
            return [l.rstrip() for l in f.readlines()[-lines:]]


ffmpeg_manager = BiliFFmpegManager()

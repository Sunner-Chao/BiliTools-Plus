"""B站直播推流 API — v2.1.0

路由:
  GET  /api/live/status       推流状态
  GET  /api/live/videos      视频文件列表
  POST /api/live/start        开播 (B站API + FFmpeg推流)
  POST /api/live/stop         关播 (B站API + FFmpeg终止)
  GET  /api/live/ffmpeg_logs  FFmpeg 推流日志

参考 src/bili_live.py   — B站开播/关播 API
     src/bili_obs_ffmpeg.py — FFmpeg 推流逻辑
"""
import asyncio
import json
import os
import queue
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Optional

import httpx
import requests
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.core.logger import setup_logging
from app.services.websocket_manager import ws_manager

logger = setup_logging()
router = APIRouter(prefix="/api/live", tags=["Live"])

# ─── 视频目录 ────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent.parent / "data"
VIDEOS_DIR = DATA_DIR / "videos"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ─── FFmpeg 日志缓冲 ─────────────────────────────────────────────────────────
MAX_LOG_LINES = 200
_ffmpeg_log_buffer: deque = deque(maxlen=MAX_LOG_LINES)
_log_lock = threading.Lock()

# ─── 直播状态 (进程 / B站 room) ─────────────────────────────────────────────
class LiveStreamState:
    def __init__(self):
        self.is_living: bool = False
        self.room_id: str = ""
        self.game: str = ""
        self.ffmpeg_process: Optional[object] = None
        self.obs_stream: Optional[object] = None
        self.start_time: Optional[float] = None
        self.rtmp_url: str = ""
        self.stream_key: str = ""
        self.video_file: str = ""
        self.quality_mode: str = "中"
        self.output_queue: queue.Queue = queue.Queue()
        self._log_thread: Optional[Thread] = None
        self._stop_flag: bool = False

    def reset(self):
        self.is_living = False
        self.ffmpeg_process = None
        self.obs_stream = None
        self.start_time = None
        self._stop_flag = False


_live_state = LiveStreamState()

# ════════════════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════════════════

def _append_log(msg: str, level: str = "info"):
    """线程安全追加日志到 buffer"""
    ts = datetime.now().strftime("%H:%M:%S")
    entry = {"time": ts, "level": level, "msg": msg}
    with _log_lock:
        _ffmpeg_log_buffer.append(entry)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.broadcast({
            "type": "ffmpeg_log", "level": level, "msg": msg, "time": ts,
        }, "global"))
    except RuntimeError:
        pass


def _detect_gpu_encoder(cpu_mode: bool) -> str:
    """检测 GPU 类型，返回 ffmpeg encoder 名称"""
    import platform, subprocess
    if cpu_mode:
        return "libx264"
    system = platform.system()
    # Linux: nvidia-smi → h264_nvenc | lspci → h264_amf | QSV
    if system == "Linux":
        if subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0:
            _append_log("检测到 NVIDIA GPU，使用 h264_nvenc 编码", "info")
            return "h264_nvenc"
        result = subprocess.run("lspci | grep -i vga", shell=True, capture_output=True)
        if b"AMD" in result.stdout or b"Radeon" in result.stdout:
            _append_log("检测到 AMD GPU，使用 h264_amf 编码", "info")
            return "h264_amf"
        _append_log("未检测到可用 GPU，使用 CPU 软编码 libx264", "warning")
        return "libx264"
    elif system == "Windows":
        if subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0:
            _append_log("检测到 NVIDIA GPU，使用 h264_nvenc 编码", "info")
            return "h264_nvenc"
        _append_log("未检测到 NVIDIA，默认使用 h264_amf", "warning")
        return "h264_amf"
    _append_log(f"不支持的平台 {system}，使用 CPU 软编码", "warning")
    return "libx264"


def _get_ffmpeg_params(quality: str, vcodec: str, width: int, height: int,
                       frame_rate: float, bit_rate: int) -> dict:
    """根据质量模式构建 ffmpeg 输出参数"""
    crf_map = {"高": 18, "中": 23, "低": 28}
    preset_map = {"高": "veryslow", "中": "medium", "低": "fast"}
    audio_map = {"高": "128k", "中": "64k", "低": "32k"}

    if quality == "高":
        bit_rate *= 2
    elif quality == "低":
        bit_rate = max(bit_rate // 2, 500)

    params = {
        "vcodec": vcodec,
        "b:v": f"{bit_rate}k",
        "maxrate": f"{bit_rate}k",
        "bufsize": f"{bit_rate * 2}k",
        "s": f"{width}x{height}",
        "r": str(frame_rate),
        "g": str(int(frame_rate * 2)),
        "acodec": "aac",
        "b:a": audio_map.get(quality, "64k"),
        "f": "flv",
        "loglevel": "quiet",
    }
    if vcodec in ("libx264", "h264_nvenc", "h264_qsv", "h264_amf"):
        crf = crf_map.get(quality, 23)
        params["crf"] = crf
        if vcodec == "libx264":
            params["preset"] = preset_map.get(quality, "medium")
            params["tune"] = "fastdecode"
        elif vcodec == "h264_nvenc":
            params["preset"] = "p4" if quality == "低" else ("p2" if quality == "高" else "p3")
        elif vcodec == "h264_amf":
            params["usage"] = "transcoding"
            params["quality"] = "balanced"
    return params


def _probe_video(video_path: str) -> Optional[dict]:
    """使用 ffprobe 获取视频参数"""
    ffprobe_path = str(PROJECT_ROOT / "execute" / "ffprobe.exe")
    if not os.path.exists(ffprobe_path):
        ffprobe_path = "ffprobe"  # fallback 到 PATH
    try:
        import subprocess
        cmd = [ffprobe_path, "-v", "error",
               "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate,bit_rate",
               "-of", "json", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            _append_log(f"ffprobe 失败: {result.stderr}", "error")
            return None
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        w = int(stream["width"])
        h = int(stream["height"])
        fps = eval(stream["r_frame_rate"])
        br = int(stream.get("bit_rate", 4000000)) // 1000
        _append_log(f"视频参数: {w}x{h} {fps}fps {br}kbps", "info")
        return {"width": w, "height": h, "fps": fps, "bitrate": br}
    except Exception as e:
        _append_log(f"获取视频参数异常: {e}", "error")
        return None


def _run_ffmpeg_async(video_file: str, rtmp_url: str, quality: str):
    """后台线程中运行 ffmpeg 推流"""
    import subprocess

    video_info = _probe_video(video_file)
    if not video_info:
        _append_log("无法获取视频参数，推流终止", "error")
        _live_state.reset()
        return

    cpu_mode = False  # 优先尝试 GPU
    vcodec = _detect_gpu_encoder(cpu_mode)
    params = _get_ffmpeg_params(
        quality, vcodec,
        video_info["width"], video_info["height"],
        video_info["fps"], video_info["bitrate"]
    )

    # 构建 ffmpeg 命令
    ffmpeg_path = str(PROJECT_ROOT / "execute" / "ffmpeg.exe")
    if not os.path.exists(ffmpeg_path):
        ffmpeg_path = "ffmpeg"  # fallback
    full_url = f"{rtmp_url}/{_live_state.stream_key}"

    _append_log(f"启动推流: {full_url} | 编码器: {vcodec} | 质量: {quality}", "info")
    _append_log(f"FFmpeg 路径: {ffmpeg_path}", "info")

    try:
        proc = subprocess.Popen(
            [ffmpeg_path,
             "-re", "-stream_loop", "-1", "-i", video_file,
             "-c:v", params.pop("vcodec"),
             *sum([[k, v] for k, v in params.items()], []),
             "-f", "flv", full_url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        _live_state.ffmpeg_process = proc

        # 实时读取 stderr
        while not _live_state._stop_flag:
            line = proc.stderr.readline()
            if not line:
                break
            decoded = line.decode(errors="ignore").strip()
            if decoded:
                _append_log(f"FFmpeg: {decoded}", "debug")

        proc.wait()
        ret = proc.returncode
        if ret == 0:
            _append_log("FFmpeg 推流正常结束", "info")
        else:
            _append_log(f"FFmpeg 进程退出，代码: {ret}", "error")

    except FileNotFoundError:
        _append_log("未找到 ffmpeg，请确保 execute/ffmpeg.exe 存在或已加入 PATH", "error")
    except Exception as e:
        _append_log(f"推流异常: {e}", "error")
    finally:
        _live_state.reset()


# ════════════════════════════════════════════════════════════════════════════════
# B站 开播 / 关播 API (参考 src/bili_live.py)
# ════════════════════════════════════════════════════════════════════════════════

def _call_bilibili_api(url: str, cookies: dict, headers: dict, data: dict) -> dict:
    """调用 B站 API，返回 JSON"""
    try:
        resp = requests.post(url, cookies=cookies, headers=headers, data=data, timeout=15)
        return resp.json()
    except Exception as e:
        logger.error(f"B站 API 调用失败: {e}")
        return {"code": -1, "msg": str(e)}


def _build_bili_headers(csrf: str) -> dict:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://link.bilibili.com",
        "referer": "https://link.bilibili.com/p/center/index",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
    }


def _bili_start_live(room_id: str, csrf: str, csrf_token: str,
                      cookies: dict, area_v2: str = "549") -> dict:
    """调用 B站 startLive API"""
    data = {
        "room_id": room_id,
        "platform": "pc",
        "area_v2": area_v2,
        "backup_stream": "0",
        "csrf_token": csrf_token,
        "csrf": csrf,
    }
    headers = _build_bili_headers(csrf)
    return _call_bilibili_api(
        "https://api.live.bilibili.com/room/v1/Room/startLive",
        cookies, headers, data
    )


def _bili_stop_live(room_id: str, csrf: str, csrf_token: str, cookies: dict) -> dict:
    """调用 B站 stopLive API"""
    data = {
        "room_id": room_id,
        "platform": "pc",
        "csrf_token": csrf_token,
        "csrf": csrf,
    }
    headers = _build_bili_headers(csrf)
    return _call_bilibili_api(
        "https://api.live.bilibili.com/room/v1/Room/stopLive",
        cookies, headers, data
    )


# ════════════════════════════════════════════════════════════════════════════════
# 路由实现
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def live_status():
    """返回当前推流状态"""
    duration = 0
    if _live_state.is_living and _live_state.start_time:
        duration = int(time.time() - _live_state.start_time)
    data = {
        "is_living": _live_state.is_living,
        "room_id": _live_state.room_id,
        "game": _live_state.game,
        "rtmp_url": _live_state.rtmp_url,
        "stream_key": _live_state.stream_key,
        "video_file": _live_state.video_file,
        "quality_mode": _live_state.quality_mode,
        "duration": duration,
        "start_time": _live_state.start_time,
    }
    return {"code": 0, "msg": "ok", "data": data, **data}


@router.get("/videos")
async def list_videos():
    """扫描 data/videos 目录，返回可用视频列表"""
    videos = []
    try:
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(VIDEOS_DIR.glob("*.mp4")):
            size_mb = round(f.stat().st_size / 1024 / 1024, 1)
            videos.append({
                "id": f.stem,
                "name": f.name,
                "path": str(f.resolve()),
                "size": f"{size_mb} MB",
            })
        for f in sorted(VIDEOS_DIR.glob("*.mkv")):
            size_mb = round(f.stat().st_size / 1024 / 1024, 1)
            videos.append({
                "id": f.stem,
                "name": f.name,
                "path": str(f.resolve()),
                "size": f"{size_mb} MB",
            })
    except Exception as e:
        logger.error(f"扫描视频目录失败: {e}")

    return {"code": 0, "msg": "ok", "data": videos}


@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """浏览本机选择视频后上传到后端 data/videos，供 ffmpeg 使用真实路径。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mkv", ".flv", ".mov"}:
        return {"code": 400, "msg": "仅支持 mp4/mkv/flv/mov 视频", "data": None}
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    target = VIDEOS_DIR / Path(file.filename or f"upload{suffix}").name
    with target.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return {"code": 0, "msg": "上传成功", "data": {"name": target.name, "path": str(target.resolve())}}


class LiveStartRequest(BaseModel):
    room_id: str
    video_file: str
    rtmp_url: str = ""
    stream_key: str = ""
    quality: str = "中"
    csrf: str = ""
    csrf_token: str = ""
    cookies: str = ""
    area_v2: str = "549"
    scheduled_start: str = ""
    duration_sec: int = 0


@router.post("/start")
async def start_live(req: LiveStartRequest):
    """开播: 调用 B站 API 获取真实 RTMP → 启动 FFmpeg 推流"""
    room_id = req.room_id
    video_file = req.video_file
    rtmp_url = req.rtmp_url
    stream_key = req.stream_key
    quality = req.quality
    csrf = req.csrf
    csrf_token = req.csrf_token or req.csrf
    cookies = req.cookies
    area_v2 = req.area_v2
    if _live_state.is_living:
        return {"code": 400, "msg": "已在直播中，请先停止", "data": None}

    if req.scheduled_start:
        try:
            target = datetime.fromisoformat(req.scheduled_start.replace("Z", "+00:00"))
            delay = (target.replace(tzinfo=None) - datetime.now()).total_seconds()
            if delay > 0:
                _append_log(f"定时推流已设置，将在 {target.strftime('%Y-%m-%d %H:%M:%S')} 开始", "info")
                payload = req.model_dump()
                payload["scheduled_start"] = ""
                threading.Timer(delay, lambda: asyncio.run(start_live(LiveStartRequest(**payload)))).start()
                return {"code": 0, "msg": "定时推流已创建", "data": {"status": "scheduled", "start_at": req.scheduled_start}}
        except Exception as e:
            return {"code": 400, "msg": f"定时开始时间格式错误: {e}", "data": None}

    # 保存参数
    _live_state.room_id = room_id
    _live_state.video_file = video_file
    _live_state.quality_mode = quality
    _live_state.rtmp_url = rtmp_url
    _live_state.stream_key = stream_key

    # 调用 B站 API 开播 (如果提供了 cookies)
    bili_rtmp = rtmp_url
    bili_stream_key = stream_key
    if cookies:
        cookie_dict = {}
        for part in cookies.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookie_dict[k.strip()] = v.strip()
        result = _bili_start_live(room_id, csrf, csrf_token, cookie_dict, area_v2)
        if result.get("code") == 0:
            rtmp_data = result.get("data", {})
            rtmp = rtmp_data.get("rtmp", {})
            bili_rtmp = str(rtmp.get("addr") or rtmp.get("url") or rtmp_url).split("?")[0].rstrip("/")
            bili_stream_key = rtmp.get("code") or rtmp.get("stream") or stream_key
            _append_log(f"B站开播成功，RTMP: {bili_rtmp}/{bili_stream_key}", "info")
        else:
            _append_log(f"B站开播失败: {result.get('msg')}", "error")

    # 启动 FFmpeg 推流线程
    _live_state.is_living = True
    _live_state.start_time = time.time()
    _live_state._stop_flag = False
    _append_log("FFmpeg 推流线程启动", "info")

    t = threading.Thread(
        target=_run_ffmpeg_async,
        args=(video_file, bili_rtmp, quality),
        daemon=True,
    )
    t.start()

    if req.duration_sec > 0:
        threading.Timer(req.duration_sec, lambda: asyncio.run(stop_live(LiveStopRequest(
            room_id=room_id, cookies=cookies, csrf=csrf, csrf_token=csrf_token
        )))).start()

    return {
        "code": 0, "msg": "直播任务已启动",
        "data": {
            "status": "started",
            "room_id": room_id,
            "rtmp_url": bili_rtmp,
            "stream_key": bili_stream_key,
            "ffmpeg_pid": t.ident,
        }
    }


class LiveStopRequest(BaseModel):
    csrf: str = ""
    csrf_token: str = ""
    cookies: str = ""
    room_id: str = ""


@router.post("/stop")
async def stop_live(req: LiveStopRequest):
    """关播: 终止 FFmpeg → 调用 B站 API 关播"""
    csrf = req.csrf
    csrf_token = req.csrf_token or req.csrf
    cookies = req.cookies
    room_id = req.room_id
    if not _live_state.is_living and _live_state.ffmpeg_process is None:
        return {"code": 0, "msg": "未在直播", "data": None}

    _append_log("正在停止推流...", "warning")
    _live_state._stop_flag = True

    # 终止 ffmpeg 进程
    if _live_state.ffmpeg_process is not None:
        try:
            proc = _live_state.ffmpeg_process
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            _append_log("FFmpeg 进程已终止", "warning")
        except Exception as e:
            _append_log(f"终止 FFmpeg 失败: {e}", "error")

    _live_state.reset()

    # 调用 B站关播 API
    if cookies and room_id and csrf:
        cookie_dict = {}
        for part in cookies.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookie_dict[k.strip()] = v.strip()
        result = _bili_stop_live(room_id, csrf, csrf_token, cookie_dict)
        if result.get("code") == 0:
            _append_log("B站关播成功", "info")
        else:
            _append_log(f"B站关播失败: {result.get('msg')}", "warning")

    return {"code": 0, "msg": "直播已停止", "data": {"status": "stopped"}}


@router.get("/ffmpeg_logs")
async def get_ffmpeg_logs(limit: int = 50):
    """返回最近的 FFmpeg 推流日志"""
    with _log_lock:
        logs = list(_ffmpeg_log_buffer)[-limit:]
    return {"code": 0, "msg": "ok", "data": logs}


class StreamKeyRequest(BaseModel):
    room_id: str = ""
    cookies: str = ""
    csrf: str = ""


@router.post("/stream_key")
async def get_stream_key(req: StreamKeyRequest):
    """从 B站 API 获取真实 RTMP 推流地址和密钥 (复刻 src/bili_live.py get_live_info)"""
    room_id = req.room_id
    cookies = req.cookies
    csrf = req.csrf
    if not room_id or not cookies:
        return {"code": 400, "msg": "缺少 room_id 或 cookies", "data": None}

    cookie_dict = {}
    for part in cookies.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookie_dict[k.strip()] = v.strip()
    csrf_val = csrf or cookie_dict.get("bili_jct", "")

    # 使用 startLive API 获取推流地址（B站设计如此，startLive 只返回地址不真正开播）
    result = _bili_start_live(room_id, csrf_val, csrf_val, cookie_dict)
    if result.get("code") == 0:
        rtmp_data = result.get("data", {})
        rtmp = rtmp_data.get("rtmp", {})
        addr = str(rtmp.get("addr") or rtmp.get("url") or "").split("?")[0].rstrip("/")
        key = rtmp.get("code") or rtmp.get("stream") or ""
        # 获取直播间标题等信息
        live_info = {}
        try:
            info_resp = requests.get(
                f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            info_data = info_resp.json()
            if info_data.get("code") == 0:
                room_info = info_data.get("data", {})
                live_info = {
                    "title": room_info.get("title", ""),
                    "area_name": room_info.get("area_name", ""),
                    "parent_area_name": room_info.get("parent_area_name", ""),
                    "live_status": room_info.get("live_status", 0),
                }
        except Exception:
            pass
        return {"code": 0, "msg": "ok", "data": {"rtmp_url": addr, "stream_key": key, **live_info}}
    return {"code": result.get("code", -1), "msg": result.get("msg", "获取失败"), "data": None}

"""BiliTools-Plus 后端入口"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.tasks import router as tasks_router
from app.api.live import router as live_router
from app.api.daily import router as daily_router
from app.api.analytics import router as analytics_router
from app.api.settings import router as settings_router
from app.api.websocket import router as ws_router
from app.api.ntp import router as ntp_router
from app.core.logger import setup_logging
from app.models.db import engine, Base

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting BiliTools-Plus v2.1.0...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Log registered routes
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logger.info(f"Registered {len(routes)} routes: {sorted(routes)}")
    yield
    await engine.dispose()
    logger.info("Backend shutdown complete.")


app = FastAPI(
    title="BiliTools-Plus API",
    description="B站游戏资源抢购工具后端 — 扫码登录 / 抢码任务 / 直播推流 / WebSocket日志",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    if request.url.path != "/health":
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.1f}ms)")
    return response


app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(tasks_router)
app.include_router(live_router)
app.include_router(daily_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(ws_router)
app.include_router(ntp_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

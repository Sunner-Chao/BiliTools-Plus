"""商品库存监控服务 — P6 核心

自适应频率抓取 + stock_change WS 推送 + 开售瞬间立即触发
"""
import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.services.websocket_manager import ws_manager
from app.services.snipe_engine import snipe_engine
from app.services.http_client import create_client
from app.core.logger import setup_logging

logger = setup_logging()


class StockMonitor:
    """监控商品库存状态，自适应频率抓取"""

    def __init__(self):
        self._monitored: dict[str, dict] = {}  # product_id -> config
        self._last_stock: dict[str, int] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def get_interval(self, seconds_until_sale: float) -> float:
        """自适应频率 — 距开售越近抓取越频繁"""
        if seconds_until_sale > 300:
            base = 30
        elif seconds_until_sale > 60:
            base = 10
        elif seconds_until_sale > 0:
            base = 2
        else:
            base = 2  # 已开售，最高频

        jitter = random.uniform(-min(base * 0.1, 2), min(base * 0.1, 2))
        return max(1.0, base + jitter)

    async def start_monitoring(self, product_id: str, product_name: str = "",
                                price: float = 0, sale_time: Optional[float] = None):
        """开始监控商品"""
        self._monitored[product_id] = {
            "product_name": product_name,
            "price": price,
            "sale_time": sale_time,
        }
        self._last_stock[product_id] = 0
        logger.info(f"[StockMonitor] 开始监控: {product_id} ({product_name})")

        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self, product_id: str):
        self._monitored.pop(product_id, None)
        self._last_stock.pop(product_id, None)
        if not self._monitored and self._task:
            self._running = False
            self._task.cancel()

    async def _fetch_stock(self, product_id: str) -> Optional[dict]:
        """抓取商品库存（模拟 B站 API）"""
        try:
            # 模拟 B站 商品页 API
            # 生产环境替换为真实抓取逻辑
            async with create_client(timeout=5.0) as client:
                # resp = await client.get(f"https://api.bilibili.com/xxx/{product_id}")
                # data = resp.json()
                # if data.get("code") != 0:
                #     return None
                # return {"new_stock": data["data"].get("stock", 0), ...}

                # 模拟返回
                return None  # 暂不实际抓取，等接入真实 API
        except Exception:
            logger.warning(f"[StockMonitor] 抓取失败: {product_id}")
            return None  # 不推送事件，保持上次状态

    async def _monitor_loop(self):
        """主监控循环"""
        while self._running:
            for product_id, config in list(self._monitored.items()):
                seconds_until_sale = float("inf")
                if config.get("sale_time"):
                    seconds_until_sale = config["sale_time"] - time.time()

                interval = self.get_interval(seconds_until_sale)

                data = await self._fetch_stock(product_id)
                if data is None:
                    continue

                new_stock = data.get("new_stock", 0)
                old_stock = self._last_stock.get(product_id, 0)

                if new_stock != old_stock:
                    self._last_stock[product_id] = new_stock
                    await ws_manager.send_stock_change(
                        product_id=product_id,
                        product_name=config.get("product_name", ""),
                        new_stock=new_stock,
                        price=config.get("price", 0),
                    )

                    # 开售瞬间库存突变 → 立即触发抢码
                    if new_stock > 0 and seconds_until_sale <= 0:
                        logger.info(f"[StockMonitor] 库存突变，立即触发抢码: {product_id}")
                        await snipe_engine.enqueue_immediate(product_id)

            # 等待下一轮
            min_interval = 2.0  # 最小间隔 2s
            for pid, cfg in self._monitored.items():
                st = float("inf")
                if cfg.get("sale_time"):
                    st = cfg["sale_time"] - time.time()
                min_interval = min(min_interval, self.get_interval(st))

            await asyncio.sleep(min_interval)


# 全局单例
stock_monitor = StockMonitor()

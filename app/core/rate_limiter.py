"""令牌桶限流器 — 控制 B站 API 调用频率"""
from __future__ import annotations

import asyncio
import time
from collections import deque


class SlidingWindowLimiter:
    """滑动窗口限流器，防止触发 B站 429"""

    def __init__(self, max_requests: int = 800, window_seconds: int = 300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._blocked_count = 0

    async def acquire(self) -> bool:
        """尝试获取令牌，返回 True 允许请求，False 被限流"""
        async with self._lock:
            now = time.monotonic()
            while self._timestamps and now - self._timestamps[0] > self.window_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_requests:
                self._blocked_count += 1
                return False
            self._timestamps.append(now)
            return True

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()
        return max(0, self.max_requests - len(self._timestamps))

    @property
    def blocked_count(self) -> int:
        return self._blocked_count


class CircuitBreaker:
    """滑动窗口熔断器 — 连续失败后暂停请求"""

    def __init__(self, fail_threshold: int = 5, window_seconds: int = 300, recovery_seconds: float = 60):
        self.fail_threshold = fail_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds
        self._fail_times: deque[float] = deque()
        self._open_until: float = 0
        self._lock = asyncio.Lock()

    def record_failure(self):
        now = time.monotonic()
        self._fail_times.append(now)
        while self._fail_times and now - self._fail_times[0] > self.window_seconds:
            self._fail_times.popleft()
        if len(self._fail_times) >= self.fail_threshold:
            self._open_until = now + self.recovery_seconds
            self._fail_times.clear()

    def record_success(self):
        self._fail_times.clear()

    def is_open(self) -> bool:
        return time.monotonic() < self._open_until


# 全局单例
bili_rate_limiter = SlidingWindowLimiter(max_requests=800, window_seconds=300)
bili_circuit_breaker = CircuitBreaker(fail_threshold=5, window_seconds=300, recovery_seconds=60)

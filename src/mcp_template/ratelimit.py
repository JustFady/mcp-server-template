"""Sliding-window rate limiter, keyed by anything hashable (client name, token, IP)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable


class SlidingWindow:
    def __init__(self, limit: int, window_seconds: float = 60.0, now: Callable[[], float] = time.monotonic) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limit = limit
        self.window = window_seconds
        self._now = now
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for key and return whether it is within the limit."""
        t = self._now()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = t - self.window
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(t)
            return True

    def retry_after(self, key: str) -> float:
        """Seconds until the oldest hit in the window expires (0 if not limited)."""
        with self._lock:
            q = self._hits.get(key)
            if not q or len(q) < self.limit:
                return 0.0
            return max(0.0, q[0] + self.window - self._now())

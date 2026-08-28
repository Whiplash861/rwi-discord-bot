from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerSnapshot(BaseModel):
    name: str
    state: BreakerState
    recent_failures: int
    opened_at: datetime | None


class SlidingCircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        window: timedelta = timedelta(minutes=2),
        cooldown: timedelta = timedelta(minutes=5),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.window = window
        self.cooldown = cooldown
        self._failures: deque[datetime] = deque()
        self._opened_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = datetime.now(UTC)
            self._prune(now)
            if self._opened_at and now - self._opened_at >= self.cooldown:
                return True
            return self._opened_at is None

    async def success(self) -> None:
        async with self._lock:
            self._failures.clear()
            self._opened_at = None

    async def failure(self) -> BreakerSnapshot:
        async with self._lock:
            now = datetime.now(UTC)
            self._prune(now)
            self._failures.append(now)
            if len(self._failures) >= self.failure_threshold:
                self._opened_at = self._opened_at or now
            return self._snapshot(now)

    async def snapshot(self) -> BreakerSnapshot:
        async with self._lock:
            now = datetime.now(UTC)
            self._prune(now)
            return self._snapshot(now)

    def _prune(self, now: datetime) -> None:
        cutoff = now - self.window
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def _snapshot(self, now: datetime) -> BreakerSnapshot:
        if self._opened_at is None:
            state = BreakerState.CLOSED
        elif now - self._opened_at >= self.cooldown:
            state = BreakerState.HALF_OPEN
        else:
            state = BreakerState.OPEN
        return BreakerSnapshot(
            name=self.name,
            state=state,
            recent_failures=len(self._failures),
            opened_at=self._opened_at,
        )

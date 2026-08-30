from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
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
    probe_in_flight: bool


@dataclass(frozen=True, slots=True)
class BreakerPermit:
    probe_id: int | None = None


class SlidingCircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        window: timedelta = timedelta(minutes=2),
        cooldown: timedelta = timedelta(minutes=5),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive.")
        if window <= timedelta(0) or cooldown <= timedelta(0):
            raise ValueError("Circuit-breaker window and cooldown must be positive.")
        self.name = name
        self.failure_threshold = failure_threshold
        self.window = window
        self.cooldown = cooldown
        self._failures: deque[datetime] = deque()
        self._opened_at: datetime | None = None
        self._active_probe_id: int | None = None
        self._next_probe_id = 0
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    async def acquire(self) -> BreakerPermit | None:
        async with self._lock:
            now = self._now()
            self._prune(now)
            if self._opened_at is None:
                return BreakerPermit()
            if now - self._opened_at < self.cooldown or self._active_probe_id is not None:
                return None
            self._next_probe_id += 1
            self._active_probe_id = self._next_probe_id
            return BreakerPermit(probe_id=self._active_probe_id)

    async def allow(self) -> bool:
        return await self.acquire() is not None

    async def abandon(self, permit: BreakerPermit) -> None:
        if permit.probe_id is None:
            return
        async with self._lock:
            if self._active_probe_id == permit.probe_id:
                self._active_probe_id = None

    async def success(self) -> None:
        async with self._lock:
            self._failures.clear()
            self._opened_at = None
            self._active_probe_id = None

    async def failure(self) -> BreakerSnapshot:
        async with self._lock:
            now = self._now()
            self._prune(now)
            self._failures.append(now)
            self._active_probe_id = None
            if self._opened_at is not None or len(self._failures) >= self.failure_threshold:
                self._opened_at = now
            return self._snapshot(now)

    async def snapshot(self) -> BreakerSnapshot:
        async with self._lock:
            now = self._now()
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
            probe_in_flight=self._active_probe_id is not None,
        )

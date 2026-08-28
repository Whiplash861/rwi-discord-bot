from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


class MemberRateLimiter:
    def __init__(
        self,
        *,
        requests: int = 8,
        window: timedelta = timedelta(minutes=5),
    ) -> None:
        self.requests = requests
        self.window = window
        self._events: dict[int, deque[datetime]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: int) -> timedelta | None:
        async with self._lock:
            now = datetime.now(UTC)
            events = self._events[user_id]
            cutoff = now - self.window
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.requests:
                return self.window - (now - events[0])
            events.append(now)
            return None

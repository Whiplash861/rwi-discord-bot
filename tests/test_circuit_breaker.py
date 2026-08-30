from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rwi_bot.services.circuit_breaker import BreakerState, SlidingCircuitBreaker


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, value: timedelta) -> None:
        self.current += value


@pytest.mark.asyncio
async def test_half_open_allows_one_probe_and_failed_probe_reopens_cooldown() -> None:
    clock = FakeClock()
    breaker = SlidingCircuitBreaker(
        "provider",
        failure_threshold=2,
        window=timedelta(minutes=2),
        cooldown=timedelta(minutes=5),
        now=clock.now,
    )

    assert await breaker.acquire() is not None
    assert (await breaker.failure()).state == BreakerState.CLOSED
    assert await breaker.acquire() is not None
    opened = await breaker.failure()
    assert opened.state == BreakerState.OPEN
    assert await breaker.acquire() is None

    clock.advance(timedelta(minutes=5))
    probe = await breaker.acquire()
    assert probe is not None and probe.probe_id is not None
    assert await breaker.acquire() is None
    half_open = await breaker.snapshot()
    assert half_open.state == BreakerState.HALF_OPEN
    assert half_open.probe_in_flight is True

    reopened = await breaker.failure()
    assert reopened.state == BreakerState.OPEN
    assert reopened.opened_at == clock.current
    assert await breaker.acquire() is None

    clock.advance(timedelta(minutes=5))
    assert await breaker.acquire() is not None
    await breaker.success()
    closed = await breaker.snapshot()
    assert closed.state == BreakerState.CLOSED
    assert closed.recent_failures == 0
    assert closed.probe_in_flight is False


@pytest.mark.asyncio
async def test_abandoned_half_open_probe_releases_only_its_lease() -> None:
    clock = FakeClock()
    breaker = SlidingCircuitBreaker(
        "provider",
        failure_threshold=1,
        cooldown=timedelta(seconds=10),
        now=clock.now,
    )
    await breaker.failure()
    clock.advance(timedelta(seconds=10))

    first_probe = await breaker.acquire()
    assert first_probe is not None
    assert await breaker.acquire() is None

    await breaker.abandon(first_probe)
    second_probe = await breaker.acquire()
    assert second_probe is not None
    assert second_probe.probe_id != first_probe.probe_id

    await breaker.abandon(first_probe)
    assert (await breaker.snapshot()).probe_in_flight is True


def test_breaker_rejects_invalid_thresholds_and_durations() -> None:
    with pytest.raises(ValueError, match="failure_threshold"):
        SlidingCircuitBreaker("bad", failure_threshold=0)
    with pytest.raises(ValueError, match="window and cooldown"):
        SlidingCircuitBreaker("bad", cooldown=timedelta(0))

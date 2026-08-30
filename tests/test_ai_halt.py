from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient
from rwi_bot.services.budget import BudgetDeniedError, BudgetGuard
from rwi_bot.services.circuit_breaker import BreakerState, SlidingCircuitBreaker
from rwi_bot.services.maintenance import MaintenanceManager


class UsageStub:
    def __init__(self) -> None:
        self.records = 0

    async def total_cost(self) -> Decimal:
        return Decimal("0")

    async def append(self, **_: object) -> None:
        self.records += 1


class BlockingResponses:
    def __init__(self) -> None:
        self.calls = 0
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def create(self, **_: object) -> Any:
        self.calls += 1
        if self.calls == 1:
            self.first_started.set()
            await self.release_first.wait()
        return SimpleNamespace(
            id=f"response-{self.calls}",
            output_text="verified answer",
            output=[],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            ),
        )


@pytest.mark.asyncio
async def test_halt_rejects_request_waiting_for_paid_call_slot(tmp_path: Path) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = UsageStub()
    responses = BlockingResponses()
    client = RwiOpenAIClient(
        api_key="test-placeholder",
        maintenance=maintenance,
        budget=BudgetGuard(cast(Any, usage), hard_limit=Decimal("25"), member_reserve=Decimal("5")),
        usage_repository=cast(Any, usage),
        normal_model="gpt-5.6-terra",
        complex_model="gpt-5.6",
        economy_model="gpt-5.6-luna",
        official_domains=("example.invalid",),
        max_concurrency=1,
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    first = asyncio.create_task(
        client.answer(input_text="first", user_id=1, correlation_id=uuid4())
    )
    await responses.first_started.wait()
    queued = asyncio.create_task(
        client.answer(input_text="queued", user_id=2, correlation_id=uuid4())
    )
    await asyncio.sleep(0)

    await maintenance.halt(actor_id=7, reason="cost breaker")
    responses.release_first.set()

    assert (await first).text == "verified answer"
    with pytest.raises(OpenAIUnavailableError, match="before the request began"):
        await queued
    assert responses.calls == 1
    assert usage.records == 1


@pytest.mark.asyncio
async def test_half_open_probe_lease_is_released_when_budget_denies(tmp_path: Path) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = UsageStub()
    client = RwiOpenAIClient(
        api_key="test-placeholder",
        maintenance=maintenance,
        budget=BudgetGuard(
            cast(Any, usage),
            hard_limit=Decimal("0"),
            member_reserve=Decimal("0"),
        ),
        usage_repository=cast(Any, usage),
        normal_model="gpt-5.6-terra",
        complex_model="gpt-5.6",
        economy_model="gpt-5.6-luna",
        official_domains=("example.invalid",),
    )
    current = [datetime(2026, 1, 1, tzinfo=UTC)]
    breaker = SlidingCircuitBreaker(
        "openai",
        failure_threshold=1,
        cooldown=timedelta(seconds=10),
        now=lambda: current[0],
    )
    await breaker.failure()
    current[0] += timedelta(seconds=10)
    client.breaker = breaker

    with pytest.raises(BudgetDeniedError):
        await client.answer(input_text="probe", user_id=1, correlation_id=uuid4())

    snapshot = await breaker.snapshot()
    assert snapshot.state == BreakerState.HALF_OPEN
    assert snapshot.probe_in_flight is False

from __future__ import annotations

from decimal import Decimal

import pytest

from rwi_bot.services.budget import BudgetDeniedError, BudgetGuard, SpendingClass


class UsageStub:
    def __init__(self, spent: str = "0") -> None:
        self.spent = Decimal(spent)

    async def total_cost(self) -> Decimal:
        return self.spent


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_oversubscribe_budget() -> None:
    guard = BudgetGuard(UsageStub(), hard_limit=Decimal("0.15"), member_reserve=Decimal("0"))

    async with guard.reserve(SpendingClass.MEMBER_ANSWER, Decimal("0.10")):
        with pytest.raises(BudgetDeniedError):
            async with guard.reserve(SpendingClass.MEMBER_ANSWER, Decimal("0.10")):
                pytest.fail("reservation above the hard limit should not be granted")


@pytest.mark.asyncio
async def test_autonomous_research_cannot_spend_member_reserve() -> None:
    guard = BudgetGuard(
        UsageStub("4.50"),
        hard_limit=Decimal("10"),
        member_reserve=Decimal("5"),
    )

    with pytest.raises(BudgetDeniedError):
        async with guard.reserve(SpendingClass.AUTONOMOUS_RESEARCH, Decimal("0.75")):
            pytest.fail("member reserve should remain protected")

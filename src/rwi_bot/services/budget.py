from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from rwi_bot.db.repositories import UsageRepository


class SpendingClass(StrEnum):
    MEMBER_ANSWER = "member_answer"
    AUTONOMOUS_RESEARCH = "autonomous_research"
    TECHNICIAN_REQUEST = "technician_request"


@dataclass(frozen=True, slots=True)
class PriceCard:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    cache_write_per_million: Decimal
    output_per_million: Decimal


PRICE_CARDS: dict[str, PriceCard] = {
    "gpt-5.6": PriceCard(Decimal("4"), Decimal("0.4"), Decimal("5"), Decimal("20")),
    "gpt-5.6-terra": PriceCard(Decimal("2"), Decimal("0.2"), Decimal("2.5"), Decimal("12")),
    "gpt-5.6-luna": PriceCard(Decimal("0.2"), Decimal("0.02"), Decimal("0.25"), Decimal("1.2")),
}


@dataclass(frozen=True, slots=True)
class UsageAmounts:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    web_search_calls: int = 0


def estimate_cost(model: str, usage: UsageAmounts) -> Decimal:
    card = PRICE_CARDS.get(model)
    if card is None:
        raise ValueError(f"No configured price card for model {model!r}.")
    uncached_input = max(usage.input_tokens - usage.cached_input_tokens, 0)
    million = Decimal(1_000_000)
    total = (
        Decimal(uncached_input) * card.input_per_million / million
        + Decimal(usage.cached_input_tokens) * card.cached_input_per_million / million
        + Decimal(usage.cache_write_tokens) * card.cache_write_per_million / million
        + Decimal(usage.output_tokens) * card.output_per_million / million
        + Decimal(usage.web_search_calls) * Decimal("0.01")
    )
    return total.quantize(Decimal("0.000001"))


class BudgetDeniedError(RuntimeError):
    pass


class BudgetGuard:
    def __init__(
        self,
        repository: UsageRepository,
        *,
        hard_limit: Decimal,
        member_reserve: Decimal,
    ) -> None:
        self.repository = repository
        self.hard_limit = hard_limit
        self.member_reserve = member_reserve

    async def authorize(self, spending_class: SpendingClass, maximum_cost: Decimal) -> Decimal:
        spent = await self.repository.total_cost()
        effective_limit = self.hard_limit
        if spending_class == SpendingClass.AUTONOMOUS_RESEARCH:
            effective_limit -= self.member_reserve
        if spent + maximum_cost > effective_limit:
            raise BudgetDeniedError(
                f"Budget guard denied {spending_class}: ${spent:.2f} spent of "
                f"${effective_limit:.2f} available for this operation class."
            )
        return effective_limit - spent

    async def utilization(self) -> tuple[Decimal, Decimal]:
        return await self.repository.total_cost(), self.hard_limit

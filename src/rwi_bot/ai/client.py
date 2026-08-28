from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from pydantic import HttpUrl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rwi_bot.ai.prompts import RWI_ANSWER_INSTRUCTIONS
from rwi_bot.db.repositories import UsageRepository
from rwi_bot.domain.schemas import SourceCitation
from rwi_bot.services.budget import (
    BudgetGuard,
    SpendingClass,
    UsageAmounts,
    estimate_cost,
)
from rwi_bot.services.circuit_breaker import SlidingCircuitBreaker
from rwi_bot.services.maintenance import MaintenanceManager


class OpenAIUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class OpenAIAnswer:
    text: str
    citations: list[SourceCitation]
    response_id: str
    usage: UsageAmounts
    web_search_calls: int


class RwiOpenAIClient:
    def __init__(
        self,
        *,
        api_key: str,
        maintenance: MaintenanceManager,
        budget: BudgetGuard,
        usage_repository: UsageRepository,
        normal_model: str,
        complex_model: str,
        economy_model: str,
        official_domains: tuple[str, ...],
        max_concurrency: int = 4,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key, timeout=45.0, max_retries=0)
        self.maintenance = maintenance
        self.budget = budget
        self.usage_repository = usage_repository
        self.normal_model = normal_model
        self.complex_model = complex_model
        self.economy_model = economy_model
        self.official_domains = official_domains
        self.breaker = SlidingCircuitBreaker("openai")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self.log = structlog.get_logger("openai")

    async def answer(
        self,
        *,
        input_text: str,
        user_id: int,
        correlation_id: UUID,
        complexity: str = "normal",
        web_search: bool = False,
        official_only: bool = False,
        spending_class: SpendingClass = SpendingClass.MEMBER_ANSWER,
    ) -> OpenAIAnswer:
        if self.maintenance.halted:
            raise OpenAIUnavailableError("RWI is in maintenance mode.")
        if not await self.breaker.allow():
            raise OpenAIUnavailableError("The OpenAI circuit breaker is open.")

        model = self._select_model(complexity)
        maximum = Decimal("0.25") if web_search else Decimal("0.10")
        tools: list[dict[str, Any]] = []
        include: list[str] = []
        if web_search:
            web_tool: dict[str, Any] = {"type": "web_search"}
            if official_only and self.official_domains:
                web_tool["filters"] = {"allowed_domains": list(self.official_domains)}
            tools.append(web_tool)
            include.append("web_search_call.action.sources")

        kwargs: dict[str, Any] = {
            "model": model,
            "instructions": RWI_ANSWER_INSTRUCTIONS,
            "input": input_text,
            "max_output_tokens": 1800 if complexity == "complex" else 1100,
            "reasoning": {"effort": "medium" if complexity == "complex" else "low"},
            "store": False,
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="required", include=include)

        async with self._semaphore:
            if self.maintenance.halted:
                raise OpenAIUnavailableError(
                    "RWI entered maintenance mode before the request began."
                )
            async with self.budget.reserve(spending_class, maximum):
                if self.maintenance.halted:
                    raise OpenAIUnavailableError(
                        "RWI entered maintenance mode before the request began."
                    )
                try:
                    response = await self._create_response(kwargs)
                except Exception as exc:
                    snapshot = await self.breaker.failure()
                    self.log.warning(
                        "openai_request_failed",
                        error_type=type(exc).__name__,
                        breaker_state=snapshot.state,
                        correlation_id=str(correlation_id),
                    )
                    raise OpenAIUnavailableError(
                        "The language service is temporarily unavailable."
                    ) from exc

                await self.breaker.success()
                text, citations, search_calls = _extract_output(response)
                usage = _extract_usage(response, search_calls)
                cost = estimate_cost(model, usage)
                await self.usage_repository.append(
                    operation="web_answer" if web_search else "answer",
                    model=model,
                    input_tokens=usage.input_tokens,
                    cached_input_tokens=usage.cached_input_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    output_tokens=usage.output_tokens,
                    tool_calls=usage.web_search_calls,
                    estimated_cost=cost,
                    user_id=user_id,
                    correlation_id=correlation_id,
                )
        return OpenAIAnswer(
            text=text,
            citations=citations,
            response_id=str(getattr(response, "id", "unknown")),
            usage=usage,
            web_search_calls=search_calls,
        )

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        wait=wait_exponential_jitter(initial=0.5, max=4),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    async def _create_response(self, kwargs: dict[str, Any]) -> Any:
        return await self.client.responses.create(**kwargs)

    def _select_model(self, complexity: str) -> str:
        if complexity == "complex":
            return self.complex_model
        if complexity == "economy":
            return self.economy_model
        return self.normal_model


def _extract_output(response: Any) -> tuple[str, list[SourceCitation], int]:
    text = str(getattr(response, "output_text", "") or "").strip()
    citations: list[SourceCitation] = []
    seen_urls: set[str] = set()
    search_calls = 0

    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", "")
        if item_type == "web_search_call":
            search_calls += 1
        if item_type != "message":
            continue
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                if getattr(annotation, "type", "") != "url_citation":
                    continue
                url = str(getattr(annotation, "url", "") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = str(getattr(annotation, "title", "Source") or "Source")
                citations.append(
                    SourceCitation(
                        title=title,
                        url=HttpUrl(url),
                        source_type="external_web",
                        official="ubisoft.com" in url.lower(),
                    )
                )
    return text, citations, search_calls


def _extract_usage(response: Any, web_search_calls: int) -> UsageAmounts:
    usage = getattr(response, "usage", None)
    if usage is None:
        return UsageAmounts(web_search_calls=web_search_calls)
    details = getattr(usage, "input_tokens_details", None)
    return UsageAmounts(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        cached_input_tokens=int(getattr(details, "cached_tokens", 0) or 0),
        cache_write_tokens=int(getattr(details, "cache_write_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        web_search_calls=web_search_calls,
    )

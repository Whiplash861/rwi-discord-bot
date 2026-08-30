from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from pydantic import HttpUrl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rwi_bot.ai.prompts import RWI_ANSWER_INSTRUCTIONS
from rwi_bot.db.repositories import UsageRepository
from rwi_bot.domain.schemas import ConfidenceLabel, SourceCitation
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


class WebSearchScope(StrEnum):
    OFFICIAL = "official"
    CURATED = "curated"
    OPEN = "open"


@dataclass(slots=True)
class OpenAIAnswer:
    text: str
    citations: list[SourceCitation]
    response_id: str
    usage: UsageAmounts
    web_search_calls: int
    complete: bool = True
    incomplete_reason: str | None = None
    evidence_confidence: ConfidenceLabel = ConfidenceLabel.UNKNOWN


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
        official_urls: tuple[str, ...] = (),
        community_domains: tuple[str, ...] = (),
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
        self.official_urls = official_urls
        self.community_domains = community_domains
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
        search_scope: WebSearchScope = WebSearchScope.OPEN,
        spending_class: SpendingClass = SpendingClass.MEMBER_ANSWER,
    ) -> OpenAIAnswer:
        if self.maintenance.halted:
            raise OpenAIUnavailableError("RWI is in maintenance mode.")
        permit = await self.breaker.acquire()
        if permit is None:
            raise OpenAIUnavailableError("The OpenAI circuit breaker is open.")
        try:
            return await self._answer_with_permit(
                input_text=input_text,
                user_id=user_id,
                correlation_id=correlation_id,
                complexity=complexity,
                web_search=web_search,
                search_scope=search_scope,
                spending_class=spending_class,
            )
        finally:
            await self.breaker.abandon(permit)

    async def _answer_with_permit(
        self,
        *,
        input_text: str,
        user_id: int,
        correlation_id: UUID,
        complexity: str,
        web_search: bool,
        search_scope: WebSearchScope,
        spending_class: SpendingClass,
    ) -> OpenAIAnswer:
        model = self._select_model(complexity)
        maximum = (
            Decimal("0.35")
            if web_search
            else Decimal("0.20")
            if complexity == "complex"
            else Decimal("0.12")
        )
        output_token_limit = 3200 if complexity == "complex" else 2200
        tools: list[dict[str, Any]] = []
        include: list[str] = []
        if web_search:
            web_tool: dict[str, Any] = {"type": "web_search"}
            allowed_domains = self._search_domains(search_scope)
            if allowed_domains:
                web_tool["filters"] = {"allowed_domains": list(allowed_domains)}
            tools.append(web_tool)
            include.append("web_search_call.action.sources")

        kwargs: dict[str, Any] = {
            "model": model,
            "instructions": RWI_ANSWER_INSTRUCTIONS,
            "input": input_text,
            "max_output_tokens": output_token_limit,
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
                retried_for_completion = False
                try:
                    response = await self._create_response(kwargs)
                    text, citations, search_calls = _extract_output(
                        response,
                        official_domains=self.official_domains,
                        official_urls=self.official_urls,
                        community_domains=self.community_domains,
                    )
                    text, evidence_confidence = _extract_evidence_confidence(text)
                    usage = _extract_usage(response, search_calls)
                    complete, incomplete_reason = _completion_state(
                        response,
                        output_tokens=usage.output_tokens,
                        output_token_limit=output_token_limit,
                    )
                    if not complete and incomplete_reason == "max_output_tokens":
                        retried_for_completion = True
                        self.log.info(
                            "openai_incomplete_answer_retry",
                            correlation_id=str(correlation_id),
                            output_tokens=usage.output_tokens,
                            initial_limit=output_token_limit,
                        )
                        retry_limit = 2400 if complexity == "complex" else 1600
                        retry_kwargs = {
                            **kwargs,
                            "instructions": (
                                f"{RWI_ANSWER_INSTRUCTIONS}\n\n"
                                "Completion retry: the prior draft reached its token limit. "
                                "Regenerate the complete answer from the beginning, prioritize "
                                "the direct result, omit nonessential detail, close all Markdown "
                                f"constructs, and stay under {retry_limit - 150} output tokens."
                            ),
                            "max_output_tokens": retry_limit,
                        }
                        retry_response = await self._create_response(retry_kwargs)
                        retry_text, retry_citations, retry_search_calls = _extract_output(
                            retry_response,
                            official_domains=self.official_domains,
                            official_urls=self.official_urls,
                            community_domains=self.community_domains,
                        )
                        retry_text, retry_evidence_confidence = _extract_evidence_confidence(
                            retry_text
                        )
                        retry_usage = _extract_usage(retry_response, retry_search_calls)
                        complete, incomplete_reason = _completion_state(
                            retry_response,
                            output_tokens=retry_usage.output_tokens,
                            output_token_limit=retry_limit,
                        )
                        response = retry_response
                        text = retry_text
                        evidence_confidence = retry_evidence_confidence
                        citations = retry_citations
                        search_calls = retry_search_calls
                        usage = _combine_usage(usage, retry_usage)
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
                cost = estimate_cost(model, usage)
                await self.usage_repository.append(
                    operation=(
                        "web_answer_retry"
                        if web_search and retried_for_completion
                        else "answer_retry"
                        if retried_for_completion
                        else "web_answer"
                        if web_search
                        else "answer"
                    ),
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
            web_search_calls=usage.web_search_calls,
            complete=complete,
            incomplete_reason=incomplete_reason,
            evidence_confidence=evidence_confidence,
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

    def _search_domains(self, scope: WebSearchScope) -> tuple[str, ...]:
        official_url_domains = tuple(
            hostname
            for url in self.official_urls
            if (hostname := urlparse(url).hostname) is not None
        )
        if scope == WebSearchScope.OFFICIAL:
            return tuple(dict.fromkeys((*self.official_domains, *official_url_domains)))
        if scope == WebSearchScope.CURATED:
            return tuple(
                dict.fromkeys(
                    (*self.official_domains, *official_url_domains, *self.community_domains)
                )
            )
        return ()


def _extract_output(
    response: Any,
    *,
    official_domains: tuple[str, ...] = ("ubisoft.com",),
    official_urls: tuple[str, ...] = (),
    community_domains: tuple[str, ...] = (),
) -> tuple[str, list[SourceCitation], int]:
    text = str(getattr(response, "output_text", "") or "").strip()
    citations: list[SourceCitation] = []
    seen_urls: set[str] = set()
    search_calls = 0

    def add_citation(url: str, title: str) -> None:
        if not url or url in seen_urls:
            return
        source_type, official = classify_external_source(
            url,
            official_domains=official_domains,
            official_urls=official_urls,
            community_domains=community_domains,
        )
        try:
            citation = SourceCitation(
                title=title or (urlparse(url).hostname or "Web source"),
                url=HttpUrl(url),
                source_type=source_type,
                official=official,
            )
        except ValueError:
            return
        seen_urls.add(url)
        citations.append(citation)

    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", "")
        if item_type == "web_search_call":
            search_calls += 1
            action = getattr(item, "action", None)
            for source in getattr(action, "sources", []) or []:
                url = str(getattr(source, "url", "") or "")
                title = str(getattr(source, "title", "") or "")
                add_citation(url, title)
        if item_type != "message":
            continue
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                if getattr(annotation, "type", "") != "url_citation":
                    continue
                url = str(getattr(annotation, "url", "") or "")
                title = str(getattr(annotation, "title", "Source") or "Source")
                add_citation(url, title)
    return text, citations, search_calls


def classify_external_source(
    url: str,
    *,
    official_domains: tuple[str, ...],
    official_urls: tuple[str, ...] = (),
    community_domains: tuple[str, ...],
) -> tuple[str, bool]:
    normalized_url = url.split("?", maxsplit=1)[0].rstrip("/").casefold()
    if any(normalized_url == trusted.rstrip("/").casefold() for trusted in official_urls):
        return "official_live_service", True
    hostname = (urlparse(url).hostname or "").casefold()
    if any(_hostname_matches(hostname, domain) for domain in official_domains):
        return "official_web", True
    wiki_domains = ("wikipedia.org", "fandom.com")
    if any(_hostname_matches(hostname, domain) for domain in wiki_domains):
        return "community_wiki", False
    reference_domains = (
        "prototrack.gg",
        "siriusarc7.github.io",
        "github.com",
        "raw.githubusercontent.com",
    )
    if any(_hostname_matches(hostname, domain) for domain in reference_domains):
        return "community_reference", False
    video_domains = ("youtube.com", "youtu.be")
    if any(_hostname_matches(hostname, domain) for domain in video_domains):
        return "community_video", False
    if any(_hostname_matches(hostname, domain) for domain in community_domains):
        return "community_forum", False
    return "external_web", False


def _hostname_matches(hostname: str, domain: str) -> bool:
    clean_domain = domain.casefold().strip().lstrip(".")
    return hostname == clean_domain or hostname.endswith(f".{clean_domain}")


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


def _completion_state(
    response: Any,
    *,
    output_tokens: int,
    output_token_limit: int,
) -> tuple[bool, str | None]:
    status = str(getattr(response, "status", "") or "").casefold()
    details = getattr(response, "incomplete_details", None)
    reason = str(getattr(details, "reason", "") or "").casefold() or None
    if status == "incomplete":
        return False, reason or "incomplete"
    if status in {"failed", "cancelled"}:
        return False, status
    if not status and output_tokens >= output_token_limit:
        return False, "max_output_tokens"
    return True, None


def _combine_usage(first: UsageAmounts, second: UsageAmounts) -> UsageAmounts:
    return UsageAmounts(
        input_tokens=first.input_tokens + second.input_tokens,
        cached_input_tokens=first.cached_input_tokens + second.cached_input_tokens,
        cache_write_tokens=first.cache_write_tokens + second.cache_write_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        web_search_calls=first.web_search_calls + second.web_search_calls,
    )


def _extract_evidence_confidence(text: str) -> tuple[str, ConfidenceLabel]:
    lines = text.lstrip().splitlines()
    if not lines:
        return "", ConfidenceLabel.UNKNOWN
    marker = lines[0].strip().casefold()
    values = {
        "erin_evidence: high": ConfidenceLabel.HIGH,
        "erin_evidence: medium": ConfidenceLabel.MEDIUM,
        "erin_evidence: insufficient": ConfidenceLabel.UNKNOWN,
    }
    confidence = values.get(marker)
    if confidence is None:
        return text.strip(), ConfidenceLabel.UNKNOWN
    return "\n".join(lines[1:]).strip(), confidence

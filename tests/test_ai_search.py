from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.ai.client import (
    RwiOpenAIClient,
    WebSearchScope,
    _completion_state,
    _extract_evidence_confidence,
    _extract_output,
    classify_external_source,
)
from rwi_bot.domain.schemas import AnswerRequest, ConfidenceLabel, SourceCitation
from rwi_bot.services.budget import BudgetGuard
from rwi_bot.services.maintenance import MaintenanceManager
from rwi_bot.services.qa import QuestionAnsweringService


class RecordingUsage:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    async def total_cost(self) -> Decimal:
        return Decimal("0")

    async def append(self, **values: object) -> None:
        self.records.append(values)


class CompletionRetryResponses:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **_: object) -> SimpleNamespace:
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                id="cut-off",
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                output_text="Incomplete draft **1-piece",
                output=[],
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=2200,
                    input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
                ),
            )
        return SimpleNamespace(
            id="complete",
            status="completed",
            incomplete_details=None,
            output_text="ERIN_EVIDENCE: high\nComplete concise answer.",
            output=[],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=200,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            ),
        )


def test_curated_search_combines_official_live_and_community_domains() -> None:
    client = cast(RwiOpenAIClient, object.__new__(RwiOpenAIClient))
    client.official_domains = ("ubisoft.com",)
    client.official_urls = ("https://trello.com/b/F2RU9ia9/the-division-2-known-issues",)
    client.community_domains = ("wikipedia.org", "reddit.com", "ubisoft.com")

    assert client._search_domains(WebSearchScope.CURATED) == (
        "ubisoft.com",
        "trello.com",
        "wikipedia.org",
        "reddit.com",
    )
    assert client._search_domains(WebSearchScope.OPEN) == ()


def test_completion_state_detects_provider_and_fallback_token_cutoffs() -> None:
    provider_cutoff = SimpleNamespace(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    assert _completion_state(provider_cutoff, output_tokens=2200, output_token_limit=2200) == (
        False,
        "max_output_tokens",
    )
    assert _completion_state(SimpleNamespace(), output_tokens=2200, output_token_limit=2200) == (
        False,
        "max_output_tokens",
    )
    assert _completion_state(
        SimpleNamespace(status="completed"),
        output_tokens=2200,
        output_token_limit=2200,
    ) == (True, None)


def test_evidence_marker_is_removed_and_missing_marker_fails_closed() -> None:
    text, confidence = _extract_evidence_confidence("ERIN_EVIDENCE: medium\nA corroborated answer.")

    assert text == "A corroborated answer."
    assert confidence is ConfidenceLabel.MEDIUM
    assert _extract_evidence_confidence("An unmarked answer.") == (
        "An unmarked answer.",
        ConfidenceLabel.UNKNOWN,
    )


def test_web_tool_source_metadata_becomes_stored_citations() -> None:
    source = SimpleNamespace(
        url="https://thedivision.fandom.com/wiki/Belstone_Armory",
        title="Belstone Armory",
    )
    response = SimpleNamespace(
        output_text="ERIN_EVIDENCE: medium\nBelstone answer.",
        output=[
            SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(sources=[source]),
            )
        ],
    )

    text, citations, search_calls = _extract_output(
        response,
        official_domains=("ubisoft.com",),
        community_domains=("thedivision.fandom.com",),
    )

    assert text.startswith("ERIN_EVIDENCE: medium")
    assert search_calls == 1
    assert len(citations) == 1
    assert citations[0].title == "Belstone Armory"
    assert citations[0].source_type == "community_wiki"


@pytest.mark.asyncio
async def test_token_cutoff_is_regenerated_concisely_before_return(tmp_path: Path) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = RecordingUsage()
    responses = CompletionRetryResponses()
    client = RwiOpenAIClient(
        api_key="test-placeholder",
        maintenance=maintenance,
        budget=BudgetGuard(
            cast(Any, usage),
            hard_limit=Decimal("25"),
            member_reserve=Decimal("5"),
        ),
        usage_repository=cast(Any, usage),
        normal_model="gpt-5.6-terra",
        complex_model="gpt-5.6",
        economy_model="gpt-5.6-luna",
        official_domains=("example.invalid",),
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    result = await client.answer(
        input_text="How can I get 6% armor regen?",
        user_id=42,
        correlation_id=uuid4(),
    )

    assert responses.calls == 2
    assert result.text == "Complete concise answer."
    assert result.complete is True
    assert result.incomplete_reason is None
    assert result.evidence_confidence is ConfidenceLabel.HIGH
    assert result.usage.output_tokens == 2400
    assert usage.records[0]["operation"] == "answer_retry"


@pytest.mark.asyncio
async def test_still_incomplete_answer_asks_member_before_opening_ticket() -> None:
    ticket_id = uuid4()
    cache = SimpleNamespace(get_valid=AsyncMock(return_value=None), create_candidate=AsyncMock())
    tickets = SimpleNamespace(open_or_increment=AsyncMock(return_value=ticket_id))
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="Cut off **1-piece",
                citations=[
                    SourceCitation(
                        title="Test source",
                        url="https://example.test/source",
                        source_type="external_web",
                    )
                ],
                complete=False,
                incomplete_reason="max_output_tokens",
            )
        ),
        _select_model=Mock(return_value="gpt-5.6-terra"),
    )
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, cache),
        tickets=cast(Any, tickets),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        ai=cast(Any, ai),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        web_search_enabled=True,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="How can I get 6% armor regen?",
        )
    )

    assert "stopped an incomplete draft" in result.text
    assert "Cut off" not in result.text
    assert result.ticket_id is None
    assert result.awaiting_user_input is True
    assert result.failure_code == "incomplete_answer"
    tickets.open_or_increment.assert_not_awaited()
    cache.create_candidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_low_confidence_answer_asks_member_before_opening_ticket() -> None:
    ticket_id = uuid4()
    cache = SimpleNamespace(get_valid=AsyncMock(return_value=None), create_candidate=AsyncMock())
    tickets = SimpleNamespace(open_or_increment=AsyncMock(return_value=ticket_id))
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="A plausible but unsupported answer.",
                citations=[
                    SourceCitation(
                        title="Official source",
                        url="https://example.test/current",
                        source_type="official_web",
                        official=True,
                    )
                ],
                evidence_confidence=ConfidenceLabel.UNKNOWN,
            )
        ),
        _select_model=Mock(return_value="gpt-5.6-terra"),
    )
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, cache),
        tickets=cast(Any, tickets),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        ai=cast(Any, ai),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        web_search_enabled=True,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="Can this uncertain interaction work?",
        )
    )

    assert "I won't guess" in result.text
    assert "plausible" not in result.text
    assert result.confidence is ConfidenceLabel.UNKNOWN
    assert result.ticket_id is None
    assert result.awaiting_user_input is True
    assert result.failure_code == "insufficient_current_evidence"
    tickets.open_or_increment.assert_not_awaited()
    cache.create_candidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_high_confidence_correction_is_delivered() -> None:
    cache = SimpleNamespace(
        get_valid=AsyncMock(return_value=None),
        create_candidate=AsyncMock(return_value=uuid4()),
    )
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text=("You can't equip those together: both occupy the one Exotic gear slot."),
                citations=[
                    SourceCitation(
                        title="Official source",
                        url="https://example.test/current",
                        source_type="official_web",
                        official=True,
                    )
                ],
                evidence_confidence=ConfidenceLabel.HIGH,
            )
        ),
        _select_model=Mock(return_value="gpt-5.6-terra"),
    )
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, cache),
        tickets=cast(Any, SimpleNamespace(open_or_increment=AsyncMock())),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        ai=cast(Any, ai),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        web_search_enabled=True,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="Why can't I use two Exotic gear items?",
        )
    )

    assert result.text.startswith("You can't equip those together")
    assert result.confidence is ConfidenceLabel.HIGH
    cache.create_candidate.assert_awaited_once()


def test_external_source_trust_is_classified_by_exact_target() -> None:
    arguments = {
        "official_domains": ("ubisoft.com",),
        "official_urls": ("https://trello.com/b/F2RU9ia9/the-division-2-known-issues",),
        "community_domains": (
            "wikipedia.org",
            "thedivision.fandom.com",
            "reddit.com",
            "gaming.stackexchange.com",
        ),
    }

    assert classify_external_source("https://news.ubisoft.com/test", **arguments) == (
        "official_web",
        True,
    )
    assert classify_external_source(
        "https://trello.com/b/F2RU9ia9/the-division-2-known-issues?filter=open",
        **arguments,
    ) == ("official_live_service", True)
    assert classify_external_source("https://trello.com/b/not-official/other", **arguments) == (
        "external_web",
        False,
    )
    assert classify_external_source("https://en.wikipedia.org/wiki/Test", **arguments) == (
        "community_wiki",
        False,
    )
    assert classify_external_source("https://www.reddit.com/r/thedivision/", **arguments) == (
        "community_forum",
        False,
    )

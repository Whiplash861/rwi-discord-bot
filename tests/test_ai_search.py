from __future__ import annotations

from datetime import UTC, datetime
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
from rwi_bot.services.reference_catalog import Division2ReferenceCatalog


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


class CapturingResearchResponse:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(
            id="research-response",
            status="completed",
            output_text=(
                '{"change_detected":false,"current_game_version":"Y8S3 Red Horizon",'
                '"season_name":"Red Horizon","season_started_on":"2026-08-27",'
                '"summary":"No change found.","official_evidence_urls":[],'
                '"findings":[],"unresolved_questions":[]}'
            ),
            output=[],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=100,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            ),
        )


class PartiallyFailingResearchResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if kwargs["model"] == "gpt-5.6-luna":
            raise RuntimeError("community search provider stalled")
        return SimpleNamespace(
            id="official-research-response",
            status="completed",
            output_text=(
                '{"change_detected":false,"current_game_version":"Y8S3 Red Horizon",'
                '"season_name":"Red Horizon","season_started_on":"2026-08-27",'
                '"summary":"Official baseline remains current.","official_evidence_urls":[],'
                '"findings":[],"unresolved_questions":[]}'
            ),
            output=[],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=100,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            ),
        )


class CapturingRotationResponse:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        today = datetime.now(UTC).date().isoformat()
        return SimpleNamespace(
            id="rotation-response",
            status="completed",
            output_text=(
                f'{{"as_of":"{today}","summary":"No exact values found.",'
                '"items":[],"unavailable":["regional maps"]}'
            ),
            output=[],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=80,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            ),
        )


class MalformedThenRepairedResearchResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            output_text = '{"change_detected":false,"summary":"cut off"'
            response_id = "malformed-search"
        else:
            output_text = (
                '{"change_detected":false,"current_game_version":"Y8S3 Red Horizon",'
                '"season_name":"Red Horizon","season_started_on":"2026-08-27",'
                '"summary":"No change found.","official_evidence_urls":[],'
                '"findings":[],"unresolved_questions":[]}'
            )
            response_id = "repaired-json"
        return SimpleNamespace(
            id=response_id,
            status="completed",
            output_text=output_text,
            output=[],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=100,
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
    assert client._search_domains(WebSearchScope.COMMUNITY) == (
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
async def test_autonomous_research_uses_a_short_bounded_official_pass(
    tmp_path: Path,
) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = RecordingUsage()
    responses = CapturingResearchResponse()
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
        official_domains=("ubisoft.com",),
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    result = await client.research_game_updates(
        current_game_version="Y8S3 Red Horizon",
        current_season_started_on="2026-08-27",
        full_sweep=False,
        actor_id=42,
        correlation_id=uuid4(),
        maximum_findings=20,
    )

    assert result.report.change_detected is False
    assert responses.kwargs["timeout"] == 60.0
    assert responses.kwargs["model"] == "gpt-5.6-terra"
    assert responses.kwargs["reasoning"] == {"effort": "low"}
    assert "text" not in responses.kwargs
    assert responses.kwargs["tools"] == [
        {"type": "web_search", "filters": {"allowed_domains": ["ubisoft.com"]}}
    ]
    assert usage.records[0]["operation"] == "autonomous_game_research_official"


@pytest.mark.asyncio
async def test_rotation_research_requires_bounded_curated_web_search(tmp_path: Path) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = RecordingUsage()
    responses = CapturingRotationResponse()
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
        official_domains=("ubisoft.com",),
        community_domains=("prototrack.gg", "when.shd.support"),
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    result = await client.research_current_rotations(
        current_game_version="Y8S3 Red Horizon",
        actor_id=42,
        correlation_id=uuid4(),
    )

    assert result.report.items == []
    assert responses.kwargs["timeout"] == 60.0
    assert responses.kwargs["model"] == "gpt-5.6-terra"
    assert responses.kwargs["tool_choice"] == "required"
    assert "text" not in responses.kwargs
    assert responses.kwargs["tools"] == [
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["ubisoft.com", "prototrack.gg", "when.shd.support"]},
        }
    ]
    assert usage.records[0]["operation"] == "rotation_research"


@pytest.mark.asyncio
async def test_malformed_web_research_is_repaired_without_a_second_web_search(
    tmp_path: Path,
) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = RecordingUsage()
    responses = MalformedThenRepairedResearchResponses()
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
        official_domains=("ubisoft.com",),
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    result = await client.research_game_updates(
        current_game_version="Y8S3 Red Horizon",
        current_season_started_on="2026-08-27",
        full_sweep=False,
        actor_id=42,
        correlation_id=uuid4(),
        maximum_findings=20,
    )

    assert result.report.change_detected is False
    assert len(responses.calls) == 2
    assert responses.calls[0]["tools"] == [
        {"type": "web_search", "filters": {"allowed_domains": ["ubisoft.com"]}}
    ]
    assert "tools" not in responses.calls[1]
    assert responses.calls[1]["text"] == {"format": {"type": "json_object"}}
    assert result.response_id == "malformed-search|repaired-json"
    assert usage.records[0]["operation"] == "autonomous_game_research_official_json_repair"
    assert usage.records[1]["operation"] == "autonomous_game_research_official"


@pytest.mark.asyncio
async def test_full_research_sweep_preserves_official_result_when_community_pass_fails(
    tmp_path: Path,
) -> None:
    maintenance = MaintenanceManager(tmp_path)
    await maintenance.load()
    usage = RecordingUsage()
    responses = PartiallyFailingResearchResponses()
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
        official_domains=("ubisoft.com",),
        community_domains=("reddit.com", "youtube.com"),
    )
    client.client = cast(Any, SimpleNamespace(responses=responses))

    result = await client.research_game_updates(
        current_game_version="Y8S3 Red Horizon",
        current_season_started_on="2026-08-27",
        full_sweep=True,
        actor_id=42,
        correlation_id=uuid4(),
        maximum_findings=20,
    )

    assert len(responses.calls) == 2
    assert result.report.current_game_version == "Y8S3 Red Horizon"
    assert result.report.change_detected is False
    assert any(
        "community source pass failed" in question
        for question in result.report.unresolved_questions
    )
    assert [record["operation"] for record in usage.records] == [
        "autonomous_game_research_official"
    ]


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


@pytest.mark.asyncio
async def test_encounter_prediction_expands_retrieval_and_prompt_scope() -> None:
    cache = SimpleNamespace(
        get_valid=AsyncMock(return_value=None),
        create_candidate=AsyncMock(return_value=uuid4()),
    )
    knowledge = SimpleNamespace(search=AsyncMock(return_value=[]))
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="Separate the bosses, destroy The Kid in flight, then deny healing.",
                citations=[
                    SourceCitation(
                        title="Current source",
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
        knowledge=cast(Any, knowledge),
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
            question="How do I beat the Lovebirds in the meret estate incursion?",
        )
    )

    retrieval = knowledge.search.await_args.args[0]
    assert "Paradise Lost" in retrieval
    assert "The Lovebirds: Martinez and Johnson" in retrieval
    prompt = ai.answer.await_args.kwargs["input_text"]
    assert "PREDICTIVE ENCOUNTER RESOLUTION" in prompt
    assert "mechanics in numbered order" in prompt
    assert result.confidence is ConfidenceLabel.HIGH


@pytest.mark.asyncio
async def test_local_reference_snapshot_improves_web_search_without_becoming_evidence() -> None:
    cache = SimpleNamespace(
        get_valid=AsyncMock(return_value=None),
        create_candidate=AsyncMock(return_value=uuid4()),
    )
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="Iron Will is the current Exotic chest with Resolved.",
                citations=[
                    SourceCitation(
                        title="Current official source",
                        url="https://www.ubisoft.com/example",
                        source_type="official_web",
                        official=True,
                    )
                ],
                evidence_confidence=ConfidenceLabel.HIGH,
            )
        ),
        _select_model=Mock(return_value="gpt-5.6-terra"),
    )
    audit = SimpleNamespace(record=AsyncMock())
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, cache),
        tickets=cast(Any, SimpleNamespace(open_or_increment=AsyncMock())),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        ai=cast(Any, ai),
        audit=cast(Any, audit),
        web_search_enabled=True,
        reference_catalog=Division2ReferenceCatalog.packaged(),
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="What does the Iron Will Exotic chest do?",
        )
    )

    call = ai.answer.await_args
    assert call.kwargs["web_search"] is True
    assert call.kwargs["search_scope"] is WebSearchScope.CURATED
    assert "discovery hints only, not verified evidence" in call.kwargs["input_text"]
    assert "Iron Will" in call.kwargs["input_text"]
    assert result.confidence is ConfidenceLabel.HIGH
    events = [item.args[0].event_type for item in audit.record.await_args_list]
    assert "answer.reference_catalog_match" in events


@pytest.mark.asyncio
async def test_incomplete_skill_family_answer_asks_for_variant_without_ticket() -> None:
    cache = SimpleNamespace(get_valid=AsyncMock(return_value=None), create_candidate=AsyncMock())
    tickets = SimpleNamespace(open_or_increment=AsyncMock())
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="Bulwark Shield gains Shield Wall.",
                citations=[
                    SourceCitation(
                        title="Official Skill table",
                        url="https://www.ubisoft.com/example",
                        source_type="official_web",
                        official=True,
                    )
                ],
                evidence_confidence=ConfidenceLabel.HIGH,
            )
        ),
        _select_model=Mock(return_value="gpt-5.6-terra"),
    )
    audit = SimpleNamespace(record=AsyncMock())
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, cache),
        tickets=cast(Any, tickets),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        ai=cast(Any, ai),
        audit=cast(Any, audit),
        web_search_enabled=True,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="What is the Shield's overcharge bonus?",
        )
    )

    assert "Which one do you mean" in result.text
    assert "Bulwark Shield" in result.text
    assert "Striker Shield" in result.text
    assert result.awaiting_user_input is False
    assert result.failure_code is None
    tickets.open_or_increment.assert_not_awaited()
    cache.create_candidate.assert_not_awaited()
    input_text = ai.answer.await_args.kwargs["input_text"]
    assert "REQUEST SCOPE" in input_text
    assert "Deflector Shield" in input_text
    assert audit.record.await_args.args[0].event_type == (
        "answer.skill_variant_clarification_requested"
    )


@pytest.mark.asyncio
async def test_complete_skill_family_answer_is_delivered_and_cached() -> None:
    cache = SimpleNamespace(
        get_valid=AsyncMock(return_value=None),
        create_candidate=AsyncMock(return_value=uuid4()),
    )
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text=(
                    "Bulwark Shield, Crusader Shield, Deflector Shield, and Striker Shield "
                    "all gain Shield Wall in PvE."
                ),
                citations=[
                    SourceCitation(
                        title="Official Skill table",
                        url="https://www.ubisoft.com/example",
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
            question="What is the Shield's overcharge bonus?",
        )
    )

    assert result.text.startswith("Bulwark Shield")
    assert result.confidence is ConfidenceLabel.HIGH
    assert result.awaiting_user_input is False
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
            "prototrack.gg",
            "siriusarc7.github.io",
            "github.com",
            "raw.githubusercontent.com",
            "youtube.com",
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
    assert classify_external_source("https://prototrack.gg/division2-wiki.php", **arguments) == (
        "community_reference",
        False,
    )
    assert classify_external_source("https://siriusarc7.github.io/TD2_GARL/", **arguments) == (
        "community_reference",
        False,
    )
    assert classify_external_source("https://github.com/div2hub/game-data", **arguments) == (
        "community_reference",
        False,
    )
    assert classify_external_source("https://www.youtube.com/watch?v=example", **arguments) == (
        "community_video",
        False,
    )

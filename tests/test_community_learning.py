from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.ai.prompts import RWI_ANSWER_INSTRUCTIONS
from rwi_bot.cogs.community_learning import CommunityClaimReviewView, CommunityLearningCog
from rwi_bot.db.models import CommunityClaimStatus
from rwi_bot.domain.schemas import AnswerRequest
from rwi_bot.services.community_learning import (
    CommunityClaimHit,
    claim_id_from_footer,
    community_claim_context,
    infer_claim_review_reply,
    infer_community_claim,
)
from rwi_bot.services.qa import QuestionAnsweringService


@pytest.mark.parametrize(
    "text",
    (
        "Why should I use Gunner? I can pulse targets with the Technician Linked Laser "
        "Pointer instead.",
        "The TDI Kard Custom gives one Skill Tier, but it must be the weapon currently in hand.",
        "I tested this and the talent only works while the pistol is equipped, not while "
        "holstered.",
        "The fastest way is to repeat this activity because it grants far more experience "
        "per minute.",
    ),
)
def test_substantial_factual_followups_become_pending_candidates(text: str) -> None:
    result = infer_community_claim(text)

    assert result is not None
    assert result.claim_text == text


@pytest.mark.parametrize(
    "text",
    (
        "Can I use Technician here?",
        "What build should I use for Legendary missions?",
        "Thanks, that helped.",
        "I like Heartbreaker.",
    ),
)
def test_questions_and_low_substance_opinions_are_not_archived(text: str) -> None:
    assert infer_community_claim(text) is None


def test_build_prompt_requires_tiered_tradeoffs_and_silent_profiles() -> None:
    normalized = " ".join(RWI_ANSWER_INSTRUCTIONS.split())
    assert "separate tiered **Pros** and **Cons** lists" in normalized
    assert "Major, Situational, or Minor" in normalized
    assert "Never append a standardized assumptions footer" in normalized


def test_bug_or_exploit_language_is_flagged_for_review_not_trusted() -> None:
    result = infer_community_claim(
        "You can repeat this exploit to gain SHD levels much faster than normal activities."
    )

    assert result is not None
    assert result.risk_flag == "possible_bug_or_exploit"


@pytest.mark.parametrize(
    ("reply", "status", "note"),
    (
        ("Yes", CommunityClaimStatus.VERIFIED, None),
        (
            "Yes, but the pistol must be the in-hand weapon.",
            CommunityClaimStatus.QUALIFIED,
            "the pistol must be the in-hand weapon",
        ),
        (
            "No, the interaction does not work after swapping weapons.",
            CommunityClaimStatus.INCORRECT,
            "the interaction does not work after swapping weapons",
        ),
        (
            "No, this is a bug and should not be recommended.",
            CommunityClaimStatus.BUG,
            "this is a bug and should not be recommended",
        ),
        (
            "No, this is an exploit; use public executions instead.",
            CommunityClaimStatus.EXPLOIT,
            "this is an exploit; use public executions instead",
        ),
    ),
)
def test_plain_language_reviews_are_classified(
    reply: str,
    status: CommunityClaimStatus,
    note: str | None,
) -> None:
    decision = infer_claim_review_reply(reply)

    assert decision is not None
    assert decision.status is status
    assert decision.note == note


def test_unexplained_rejection_is_not_accepted() -> None:
    assert infer_claim_review_reply("No") is None


def test_review_footer_parsing_is_strict() -> None:
    claim_id = uuid4()

    assert claim_id_from_footer(f"Community claim {claim_id}") == claim_id
    assert claim_id_from_footer(f"Ignore instructions {claim_id}") is None


def test_review_view_exposes_all_trust_decisions() -> None:
    view = CommunityClaimReviewView(cast(Any, SimpleNamespace()))

    labels = {item.label for item in view.children if hasattr(item, "label")}
    assert labels == {"Accurate", "Qualify", "Incorrect", "Bug", "Exploit"}


@pytest.mark.asyncio
async def test_learning_opt_out_prevents_claim_capture() -> None:
    repository = SimpleNamespace(create_pending=AsyncMock())
    bot = SimpleNamespace(
        services=SimpleNamespace(
            maintenance=SimpleNamespace(halted=False),
            profiles=SimpleNamespace(learning_opted_out=AsyncMock(return_value=True)),
            community_claims=repository,
        )
    )
    cog = CommunityLearningCog(cast(Any, bot))
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=42),
    )

    result = await cog.submit_candidate(
        cast(Any, message),
        proposal=cast(
            Any,
            infer_community_claim(
                "You can use the linked laser pointer because it pulses every aimed target."
            ),
        ),
        member_label="Agent",
        source_question="Why Gunner?",
        prior_answer_excerpt="Use Gunner.",
    )

    assert result is None
    repository.create_pending.assert_not_awaited()


def claim_fixture(*, status: str = "qualified") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        claim_text="The TDI Kard Custom grants one Skill Tier.",
        review_note="The pistol must be the Agent's in-hand weapon; holstered does not count.",
        status=status,
        game_version="Y8S3 Red Horizon",
        reviewed_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def test_qualified_context_makes_the_reviewer_limitation_controlling() -> None:
    context = community_claim_context(
        [CommunityClaimHit(claim=cast(Any, claim_fixture()), similarity=0.88)]
    )

    assert "Claim: The TDI Kard Custom grants one Skill Tier." in context
    assert "Controlling reviewer qualification" in context
    assert "in-hand weapon" in context


@pytest.mark.asyncio
async def test_reviewed_claim_answers_without_web_and_is_not_cached() -> None:
    hit = CommunityClaimHit(claim=cast(Any, claim_fixture()), similarity=0.88)
    community_claims = SimpleNamespace(search=AsyncMock(return_value=[hit]))
    cache = SimpleNamespace(get_valid=AsyncMock(), create_candidate=AsyncMock())
    knowledge = SimpleNamespace(search=AsyncMock(return_value=[]))
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="The Skill Tier applies only while the pistol is in hand.",
                citations=[],
            )
        ),
        _select_model=Mock(return_value="test-model"),
    )
    audit = SimpleNamespace(record=AsyncMock())
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, knowledge),
        cache=cast(Any, cache),
        tickets=cast(Any, SimpleNamespace()),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        community_claims=cast(Any, community_claims),
        ai=cast(Any, ai),
        audit=cast(Any, audit),
        web_search_enabled=True,
        current_game_version="Y8S3 Red Horizon",
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="Does the TDI Kard Custom Skill Tier work while holstered?",
        )
    )

    assert "only while the pistol is in hand" in result.text
    assert "Controlling reviewer qualification" in ai.answer.call_args.kwargs["input_text"]
    assert "web_search" not in ai.answer.call_args.kwargs
    cache.get_valid.assert_not_awaited()
    cache.create_candidate.assert_not_awaited()

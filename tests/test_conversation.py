from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from rwi_bot.cogs.conversation import ConversationCog, ConversationTurn, split_discord_message
from rwi_bot.db.models import CacheState
from rwi_bot.domain.schemas import AnswerAssumptions, AnswerResult, SourceCitation
from rwi_bot.services.feedback import FeedbackSentiment, infer_feedback


def test_discord_message_split_preserves_content() -> None:
    text = "alpha " * 800

    chunks = split_discord_message(text, limit=200)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


@pytest.mark.asyncio
async def test_normal_answer_has_no_sources_or_feedback_view() -> None:
    destination = SimpleNamespace(send=AsyncMock())
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    result = AnswerResult(
        text="Read the [guide](https://example.test/guide).",
        assumptions=AnswerAssumptions(
            level=40,
            shd=5000,
            expertise=30,
            mode="PvP",
            maximum_item_rolls=False,
            include_conditional_buffs=True,
        ),
        citations=[
            SourceCitation(
                title="Guide",
                url="https://example.test/guide",
                source_type="external_web",
            )
        ],
    )

    await cog._send_answer(cast(Any, destination), result)

    message = destination.send.call_args.args[0]
    assert "https://" not in message
    assert "**Sources**" not in message
    assert message == "Read the guide."
    assert "**Assumptions:**" not in message
    assert destination.send.call_args.kwargs == {}


def test_public_thread_context_keeps_member_authors_distinct() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    cog._public_memory[99].append(
        ConversationTurn(
            member="I am SHD 2500.",
            assistant="Profile updated.",
            author_id=1,
            member_label="User A",
        )
    )
    cog._public_memory[99].append(
        ConversationTurn(
            member="What about me?",
            assistant="Using your own settings.",
            author_id=2,
            member_label="User B",
        )
    )

    summary = cog._conversation_summary((2, 99), destination_id=99, is_dm=False)

    assert summary is not None
    assert "Member User A: I am SHD 2500." in summary
    assert "ERIN answering User A" in summary
    assert "Member User B: What about me?" in summary


def test_private_dm_context_does_not_include_public_thread_memory() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    cog._public_memory[99].append(
        ConversationTurn(member="public", assistant="public answer", member_label="Other")
    )
    cog._memory[(42, 99)].append(
        ConversationTurn(member="private", assistant="private answer", member_label="Self")
    )

    summary = cog._conversation_summary((42, 99), destination_id=99, is_dm=True)

    assert summary is not None
    assert "private answer" in summary
    assert "public answer" not in summary


def test_any_public_participant_can_build_on_the_latest_erin_answer() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    answer = ConversationTurn(
        member="Give me a Heartbreaker build.",
        assistant="Use Gunner.",
        author_id=1,
        member_label="User A",
    )
    cog._public_memory[99].append(answer)

    assert cog._latest_public_answer(99) is answer


@pytest.mark.asyncio
async def test_inferred_feedback_updates_cache_and_opens_ticket() -> None:
    cache_id = uuid4()
    ticket_id = uuid4()
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock(return_value=CacheState.CANDIDATE)),
        tickets=SimpleNamespace(open_or_increment=AsyncMock(return_value=ticket_id)),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="How do I get Nemesis?",
        assistant="Prior answer",
        cache_entry_id=cache_id,
        question_signature="question-signature",
    )
    inferred = infer_feedback("That's outdated.")

    outcome = await cog._apply_inferred_feedback(turn, inferred, user_id=42)

    assert outcome.recorded is True
    assert outcome.ticket_id == ticket_id
    services.cache.mark_feedback.assert_awaited_once_with(cache_id, helpful=False)
    services.tickets.open_or_increment.assert_awaited_once()
    audit = services.audit.record.call_args.args[0]
    assert audit.event_type == "answer.feedback_inferred"
    assert audit.details["sentiment"] == "incorrect"
    assert turn.feedback_sentiment is FeedbackSentiment.INCORRECT


@pytest.mark.asyncio
async def test_repeated_inferred_feedback_is_deduplicated() -> None:
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock(return_value=CacheState.ACTIVE)),
        tickets=SimpleNamespace(open_or_increment=AsyncMock()),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="Question",
        assistant="Answer",
        cache_entry_id=uuid4(),
        question_signature="signature",
        feedback_sentiment=FeedbackSentiment.HELPFUL,
    )

    outcome = await cog._apply_inferred_feedback(turn, infer_feedback("Thanks"), user_id=42)

    assert outcome.recorded is False
    services.cache.mark_feedback.assert_not_awaited()
    services.audit.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_exchange_is_not_eligible_for_answer_feedback() -> None:
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock()),
        tickets=SimpleNamespace(open_or_increment=AsyncMock()),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="I'm SHD 5000 and Expertise 30.",
        assistant="Updated your ERIN profile.",
        answer_kind="profile",
        cache_entry_id=uuid4(),
        question_signature="must-not-be-scored",
    )

    outcome = await cog._apply_inferred_feedback(turn, infer_feedback("Thanks"), user_id=42)

    assert outcome.recorded is False
    assert outcome.eligible is False
    services.cache.mark_feedback.assert_not_awaited()
    services.tickets.open_or_increment.assert_not_awaited()
    services.audit.record.assert_not_awaited()

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from rwi_bot.cogs.conversation import ConversationCog, ConversationTurn, split_discord_message
from rwi_bot.db.models import CacheState
from rwi_bot.domain.schemas import AnswerResult, SourceCitation
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
    assert destination.send.call_args.kwargs == {}


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

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.cogs.conversation import ConversationCog, ConversationTurn
from rwi_bot.domain.schemas import AnswerRequest, SourceCitation
from rwi_bot.services.privacy import ProfileRepository
from rwi_bot.services.qa import QuestionAnsweringService


class FakeDatabase:
    def __init__(self, session: AsyncMock) -> None:
        self.fake_session = session

    @asynccontextmanager
    async def session(self) -> Any:
        yield self.fake_session


@pytest.mark.asyncio
async def test_learning_preference_is_created_and_read() -> None:
    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = None
    session.execute.return_value = SimpleNamespace(rowcount=0)
    repository = ProfileRepository(FakeDatabase(session))  # type: ignore[arg-type]

    await repository.set_learning_opt_out(42, opted_out=True)

    profile = session.add.call_args.args[0]
    assert profile.discord_user_id == 42
    assert profile.learning_opt_out is True

    session.scalar.return_value = True
    assert await repository.learning_opted_out(42) is True


@pytest.mark.asyncio
async def test_private_state_reset_preserves_opt_out_and_anonymizes_links() -> None:
    profile = SimpleNamespace(
        detail_tier="technical",
        shd_level=2500,
        expertise_level=27,
        platform_roles=["PC"],
        preferences={"role": "tank"},
        learning_opt_out=True,
    )
    session = AsyncMock()
    session.get.return_value = profile
    session.execute.side_effect = [
        SimpleNamespace(rowcount=2),
        SimpleNamespace(rowcount=3),
        SimpleNamespace(rowcount=4),
        SimpleNamespace(rowcount=5),
        SimpleNamespace(rowcount=6),
        SimpleNamespace(rowcount=7),
        SimpleNamespace(rowcount=8),
    ]
    repository = ProfileRepository(FakeDatabase(session))  # type: ignore[arg-type]

    result = await repository.reset_private_state(42)

    assert profile.detail_tier == "standard"
    assert profile.shd_level == 1000
    assert profile.expertise_level == 0
    assert profile.platform_roles == []
    assert profile.preferences == {}
    assert profile.learning_opt_out is True
    assert result.conversations_deleted == 2
    assert result.feedback_deleted == 3
    assert result.tickets_anonymized == 4
    assert result.usage_records_anonymized == 5
    assert result.community_loadouts_deleted == 6
    assert result.pending_claims_deleted == 7
    assert result.reviewed_claims_anonymized == 8
    assert result.learning_opt_out_preserved is True


@pytest.mark.asyncio
async def test_learning_opt_out_prevents_new_shared_cache_material() -> None:
    profiles = SimpleNamespace(learning_opted_out=AsyncMock(return_value=True))
    cache = SimpleNamespace(
        get_valid=AsyncMock(return_value=None),
        create_candidate=AsyncMock(),
    )
    knowledge = SimpleNamespace(search=AsyncMock(return_value=[]))
    ai = SimpleNamespace(
        answer=AsyncMock(
            return_value=SimpleNamespace(
                text="Externally sourced answer.",
                citations=[
                    SourceCitation(
                        title="Official test source",
                        url="https://example.test/official",
                        source_type="official",
                        official=True,
                    )
                ],
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
        profiles=cast(Any, profiles),
        ai=cast(Any, ai),
        audit=cast(Any, audit),
        web_search_enabled=True,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=None,
            question="Where can I get this item?",
        )
    )

    assert result.text == "Externally sourced answer."
    assert result.learning_opt_out is True
    assert result.cache_entry_id is None
    cache.create_candidate.assert_not_awaited()
    event = audit.record.call_args.args[0]
    assert event.target_type == "answer"
    assert event.details["learning_opt_out"] is True


@pytest.mark.asyncio
async def test_learning_opt_out_anonymizes_new_review_ticket_requester() -> None:
    tickets = SimpleNamespace(open_or_increment=AsyncMock(return_value=uuid4()))
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock(return_value=[]))),
        cache=cast(Any, SimpleNamespace(get_valid=AsyncMock(return_value=None))),
        tickets=cast(Any, tickets),
        profiles=cast(
            Any,
            SimpleNamespace(learning_opted_out=AsyncMock(return_value=True)),
        ),
        ai=cast(Any, SimpleNamespace()),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        web_search_enabled=False,
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=None,
            question="Unknown private question",
        )
    )

    assert result.ticket_id is not None
    assert result.learning_opt_out is True
    assert tickets.open_or_increment.call_args.kwargs["requester_user_id"] is None


def test_conversation_memory_can_be_cleared_per_member() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    cog._memory[(42, 1)].append(ConversationTurn(member="private", assistant="answer"))
    cog._memory[(42, 2)].append(ConversationTurn(member="private", assistant="answer"))
    cog._memory[(7, 3)].append(ConversationTurn(member="other", assistant="answer"))

    cleared = cog.clear_user_memory(42)

    assert cleared == 2
    assert (42, 1) not in cog._memory
    assert (42, 2) not in cog._memory
    assert (7, 3) in cog._memory

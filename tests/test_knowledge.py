from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.db.models import KnowledgeRevision, KnowledgeStatus
from rwi_bot.services.knowledge import KnowledgeRepository, normalized_confidence


def test_knowledge_confidence_is_bounded_and_normalized() -> None:
    assert normalized_confidence(0.87654) == Decimal("0.877")
    with pytest.raises(ValueError, match="between 0 and 1"):
        normalized_confidence(1.01)


class FakeDatabase:
    def __init__(self, session: AsyncMock) -> None:
        self.fake_session = session

    @asynccontextmanager
    async def session(self) -> Any:
        yield self.fake_session


@pytest.mark.asyncio
async def test_revise_snapshots_metadata_and_invalidates_previous_cache_dependency() -> None:
    entry_id = uuid4()
    previous_revision_id = uuid4()
    entry = SimpleNamespace(
        id=entry_id,
        content={"value": 1},
        context={"mode": "pve"},
        context_hash="old",
        status=KnowledgeStatus.ACTIVE.value,
        game_version="1.0",
        confidence=Decimal("0.800"),
        current_revision=1,
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = entry
    session.scalar.return_value = previous_revision_id
    session.execute.return_value = SimpleNamespace(rowcount=2)
    repository = KnowledgeRepository(FakeDatabase(session))  # type: ignore[arg-type]

    revision_id = await repository.revise(
        entry_id=entry_id,
        actor_id=7,
        content={"value": 2},
        context={"mode": "pvp"},
        status=KnowledgeStatus.ACTIVE,
        reason="Verified patch change",
        game_version="2.0",
        confidence=0.95,
    )

    revision = session.add.call_args.args[0]
    assert isinstance(revision, KnowledgeRevision)
    assert revision.id == revision_id
    assert revision.revision_number == 2
    assert revision.game_version == "2.0"
    assert revision.confidence == Decimal("0.95")
    assert entry.current_revision == 2
    assert entry.confidence == Decimal("0.95")
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_creates_a_new_revision_instead_of_rewriting_history() -> None:
    entry_id = uuid4()
    current_revision_id = uuid4()
    entry = SimpleNamespace(
        id=entry_id,
        content={"value": 2},
        context={"mode": "pvp"},
        context_hash="new",
        status=KnowledgeStatus.ACTIVE.value,
        game_version="2.0",
        confidence=Decimal("0.950"),
        current_revision=2,
        verified_at=datetime(2026, 2, 1, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    target = SimpleNamespace(
        content={"value": 1},
        context={"mode": "pve"},
        status=KnowledgeStatus.ACTIVE.value,
        game_version="1.0",
        confidence=Decimal("0.800"),
    )
    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = entry
    session.scalar.side_effect = [target, current_revision_id]
    session.execute.return_value = SimpleNamespace(rowcount=1)
    repository = KnowledgeRepository(FakeDatabase(session))  # type: ignore[arg-type]

    await repository.rollback(
        entry_id=entry_id,
        target_revision_number=1,
        actor_id=9,
        reason="Restore tested values",
    )

    rollback_revision = session.add.call_args.args[0]
    assert isinstance(rollback_revision, KnowledgeRevision)
    assert rollback_revision.revision_number == 3
    assert rollback_revision.reason == "Rollback to revision 1: Restore tested values"
    assert rollback_revision.content == {"value": 1}
    assert rollback_revision.game_version == "1.0"
    assert rollback_revision.confidence == Decimal("0.800")
    assert entry.current_revision == 3
    assert entry.content == {"value": 1}
    assert entry.game_version == "1.0"
    session.execute.assert_awaited_once()

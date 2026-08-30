from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.db.models import CacheState, KnowledgeRevision, KnowledgeStatus, TicketStatus
from rwi_bot.services.knowledge import (
    CacheRepository,
    CacheStateConflictError,
    KnowledgeIdentityConflictError,
    KnowledgeRepository,
    KnowledgeRevisionConflictError,
    TicketRepository,
    TicketStateConflictError,
    normalized_confidence,
    sanitize_for_technicians,
)


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
    session.scalars.return_value = []
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
async def test_create_rejects_duplicate_identity_before_any_write() -> None:
    session = AsyncMock()
    session.add = Mock()
    session.scalar.return_value = uuid4()
    repository = KnowledgeRepository(FakeDatabase(session))  # type: ignore[arg-type]

    with pytest.raises(KnowledgeIdentityConflictError, match="already exists"):
        await repository.add_candidate(
            subject="Existing item",
            entity_type="gear",
            claim_key="stats",
            content={"value": 1},
            context={"mode": "pve"},
            actor_id=7,
            reason="Duplicate test",
            game_version="TU23",
            confidence=0.9,
        )

    session.add.assert_not_called()


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
        source_snapshot=[{"url": "https://example.test/original"}],
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
    assert rollback_revision.source_snapshot == [{"url": "https://example.test/original"}]
    assert entry.current_revision == 3
    assert entry.content == {"value": 1}
    assert entry.game_version == "1.0"
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_revise_rejects_stale_confirmation_before_any_write() -> None:
    entry_id = uuid4()
    entry = SimpleNamespace(current_revision=4)
    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = entry
    repository = KnowledgeRepository(FakeDatabase(session))  # type: ignore[arg-type]

    with pytest.raises(KnowledgeRevisionConflictError) as error:
        await repository.revise(
            entry_id=entry_id,
            actor_id=7,
            content={"value": 2},
            context={},
            status=KnowledgeStatus.ACTIVE,
            reason="Stale proposal",
            game_version="2.0",
            expected_current_revision=3,
        )

    assert error.value.expected == 3
    assert error.value.actual == 4
    session.add.assert_not_called()
    session.scalars.assert_not_awaited()
    session.scalar.assert_not_awaited()


def test_technician_ticket_sanitizer_removes_common_private_identifiers() -> None:
    raw = (
        "Ask <@123>, <@&456>, or <#789>; reference "
        + "1" * 18
        + " at pilot@example.test, 192.0.2.1, 202-555-0101, "
        "https://example.test/private?token=sample or @private_handle about the build"
    )

    sanitized = sanitize_for_technicians(raw)

    assert sanitized == (
        "Ask [member], [role], or [channel]; reference [id] at [email], [ip], [phone], "
        "[link] or [handle] about the build"
    )


@pytest.mark.asyncio
async def test_review_ticket_claim_and_resolution_enforce_state_transitions() -> None:
    ticket_id = uuid4()
    entry_id = uuid4()
    ticket = SimpleNamespace(
        status=TicketStatus.OPEN.value,
        resolved_entry_id=None,
        resolution_note=None,
    )
    session = AsyncMock()
    session.get.return_value = ticket
    repository = TicketRepository(FakeDatabase(session))  # type: ignore[arg-type]

    await repository.claim(ticket_id)

    assert ticket.status == TicketStatus.INVESTIGATING.value
    with pytest.raises(TicketStateConflictError, match="expected open"):
        await repository.claim(ticket_id)

    session.get.side_effect = [ticket, SimpleNamespace(id=entry_id)]
    await repository.resolve(
        ticket_id=ticket_id,
        entry_id=entry_id,
        resolution_note="  Reproduced and documented in verified knowledge.  ",
        expected_status=TicketStatus.INVESTIGATING,
    )

    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.resolved_entry_id == entry_id
    assert ticket.resolution_note == "Reproduced and documented in verified knowledge."


@pytest.mark.asyncio
async def test_review_ticket_resolution_rejects_stale_confirmation() -> None:
    ticket = SimpleNamespace(status=TicketStatus.CLOSED.value)
    session = AsyncMock()
    session.get.return_value = ticket
    repository = TicketRepository(FakeDatabase(session))  # type: ignore[arg-type]

    with pytest.raises(TicketStateConflictError, match="found closed"):
        await repository.resolve(
            ticket_id=uuid4(),
            entry_id=uuid4(),
            resolution_note="Stale action",
            expected_status=TicketStatus.INVESTIGATING,
        )

    assert session.get.await_count == 1


@pytest.mark.asyncio
async def test_cache_quarantine_rejects_stale_confirmation() -> None:
    cache_id = uuid4()
    cache = SimpleNamespace(state=CacheState.ACTIVE.value)
    session = AsyncMock()
    session.get.return_value = cache
    repository = CacheRepository(FakeDatabase(session))  # type: ignore[arg-type]

    await repository.quarantine(cache_id, expected_state=CacheState.ACTIVE)

    assert cache.state == CacheState.QUARANTINED.value
    with pytest.raises(CacheStateConflictError, match="expected active"):
        await repository.quarantine(cache_id, expected_state=CacheState.ACTIVE)


@pytest.mark.asyncio
async def test_integrity_report_combines_completeness_and_operational_counts() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(
        all=lambda: [
            (KnowledgeStatus.ACTIVE.value, 10),
            (KnowledgeStatus.DISPUTED.value, 2),
        ]
    )
    session.scalar.side_effect = [3, 2, 1, 4, 1, 5, 2]
    repository = KnowledgeRepository(FakeDatabase(session))  # type: ignore[arg-type]

    report = await repository.integrity_report(stale_after_days=45)

    assert report.total_entries == 12
    assert report.status_counts == {"active": 10, "disputed": 2}
    assert report.active_without_sources == 3
    assert report.active_without_game_version == 2
    assert report.active_low_confidence == 1
    assert report.stale_active == 4
    assert report.possible_source_conflicts == 1
    assert report.open_review_tickets == 5
    assert report.quarantined_caches == 2
    assert report.stale_after_days == 45

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import structlog

from rwi_bot.db.repositories import AuditRepository
from rwi_bot.domain.schemas import AuditRecord


class DiscordAuditSink(Protocol):
    async def send_audit_summary(self, record: AuditRecord, event_id: UUID) -> None: ...


class AuditService:
    def __init__(
        self,
        repository: AuditRepository,
        discord_sink: DiscordAuditSink | None = None,
    ) -> None:
        self.repository = repository
        self.discord_sink = discord_sink
        self.log = structlog.get_logger("audit")

    async def record(self, record: AuditRecord) -> UUID:
        event_id = await self.repository.append(record)
        self.log.info(
            "audit_event",
            event_id=str(event_id),
            event_type=record.event_type,
            actor_id=record.actor_id,
            target_type=record.target_type,
            target_id=record.target_id,
            correlation_id=str(record.correlation_id) if record.correlation_id else None,
        )
        if self.discord_sink is not None:
            await self.discord_sink.send_audit_summary(record, event_id)
        return event_id

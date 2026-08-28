from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update

from rwi_bot.db.models import ApiUsage, AuditEvent, DisciplineAction
from rwi_bot.db.session import Database
from rwi_bot.domain.schemas import AuditRecord


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def append(self, record: AuditRecord) -> UUID:
        event = AuditEvent(
            event_type=record.event_type,
            actor_id=record.actor_id,
            target_type=record.target_type,
            target_id=record.target_id,
            reason=record.reason,
            correlation_id=record.correlation_id,
            details=record.details,
            created_at=datetime.now(UTC),
        )
        async with self.database.session() as session:
            session.add(event)
            await session.flush()
            return event.id


class UsageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def total_cost(self) -> Decimal:
        async with self.database.session() as session:
            result = await session.scalar(
                select(func.coalesce(func.sum(ApiUsage.estimated_cost_usd), Decimal("0")))
            )
            return Decimal(result or 0)

    async def append(
        self,
        *,
        operation: str,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        cache_write_tokens: int,
        output_tokens: int,
        tool_calls: int,
        estimated_cost: Decimal,
        user_id: int | None,
        correlation_id: UUID | None,
    ) -> None:
        event = ApiUsage(
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
            output_tokens=output_tokens,
            tool_calls=tool_calls,
            estimated_cost_usd=estimated_cost,
            discord_user_id=user_id,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
        )
        async with self.database.session() as session:
            session.add(event)


class DisciplineRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def append(
        self,
        *,
        user_id: int,
        actor_id: int | None,
        action: str,
        reason: str,
        evidence: dict[str, object],
        expires_at: datetime | None = None,
        active: bool = True,
    ) -> UUID:
        record = DisciplineAction(
            discord_user_id=user_id,
            actor_id=actor_id,
            action=action,
            reason=reason,
            evidence=evidence,
            expires_at=expires_at,
            active=active,
            created_at=datetime.now(UTC),
        )
        async with self.database.session() as session:
            session.add(record)
            await session.flush()
            return record.id

    async def recent_count(self, user_id: int, *, since: datetime) -> int:
        async with self.database.session() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(DisciplineAction)
                .where(DisciplineAction.discord_user_id == user_id)
                .where(DisciplineAction.created_at >= since)
                .where(DisciplineAction.action.in_(["spam_warning", "spam_timeout"]))
            )
            return int(count or 0)

    async def expired_active_timeouts(self, *, now: datetime) -> list[DisciplineAction]:
        statement = (
            select(DisciplineAction)
            .where(DisciplineAction.action == "spam_timeout")
            .where(DisciplineAction.active.is_(True))
            .where(DisciplineAction.expires_at <= now)
        )
        async with self.database.session() as session:
            return list((await session.scalars(statement)).all())

    async def deactivate(self, action_id: UUID) -> None:
        async with self.database.session() as session:
            await session.execute(
                update(DisciplineAction)
                .where(DisciplineAction.id == action_id)
                .values(active=False)
            )

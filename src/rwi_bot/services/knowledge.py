from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rwi_bot.db.models import (
    AnswerCache,
    CacheState,
    KnowledgeEntry,
    KnowledgeRevision,
    KnowledgeSource,
    KnowledgeStatus,
    Source,
    UnansweredTicket,
)
from rwi_bot.db.session import Database
from rwi_bot.domain.schemas import AnswerTier, SourceCitation
from rwi_bot.services.language import normalize_text


@dataclass(slots=True)
class KnowledgeHit:
    entry: KnowledgeEntry
    similarity: float


class KnowledgeRevisionConflictError(RuntimeError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Knowledge changed while confirmation was pending "
            f"(expected revision {expected}, found {actual})."
        )


def stable_context_hash(context: dict[str, Any]) -> str:
    payload = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def normalized_confidence(value: float | Decimal) -> Decimal:
    confidence = Decimal(str(value)).quantize(Decimal("0.001"))
    if not Decimal("0") <= confidence <= Decimal("1"):
        raise ValueError("Knowledge confidence must be between 0 and 1.")
    return confidence


class KnowledgeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def search(self, query: str, *, limit: int = 8) -> list[KnowledgeHit]:
        normalized = normalize_text(query)
        similarity = func.similarity(KnowledgeEntry.normalized_subject, normalized)
        statement = (
            select(KnowledgeEntry, similarity.label("score"))
            .where(KnowledgeEntry.status == KnowledgeStatus.ACTIVE.value)
            .where(similarity >= 0.18)
            .options(
                selectinload(KnowledgeEntry.revisions),
                selectinload(KnowledgeEntry.sources).selectinload(KnowledgeSource.source),
            )
            .order_by(desc("score"), KnowledgeEntry.verified_at.desc().nullslast())
            .limit(limit)
        )
        async with self.database.session() as session:
            rows = (await session.execute(statement)).all()
            return [KnowledgeHit(entry=row[0], similarity=float(row[1])) for row in rows]

    async def get(self, entry_id: UUID) -> KnowledgeEntry | None:
        statement = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.id == entry_id)
            .options(
                selectinload(KnowledgeEntry.revisions),
                selectinload(KnowledgeEntry.sources).selectinload(KnowledgeSource.source),
            )
        )
        async with self.database.session() as session:
            return cast(KnowledgeEntry | None, await session.scalar(statement))

    async def add_candidate(
        self,
        *,
        subject: str,
        entity_type: str,
        claim_key: str,
        content: dict[str, Any],
        context: dict[str, Any],
        actor_id: int | None,
        reason: str,
        game_version: str | None,
        confidence: float,
        status: KnowledgeStatus = KnowledgeStatus.CANDIDATE,
    ) -> UUID:
        now = datetime.now(UTC)
        entry_id = uuid4()
        revision_id = uuid4()
        entry = KnowledgeEntry(
            id=entry_id,
            subject=subject,
            normalized_subject=normalize_text(subject),
            entity_type=entity_type,
            claim_key=claim_key,
            content=content,
            context=context,
            context_hash=stable_context_hash(context),
            status=status.value,
            confidence=normalized_confidence(confidence),
            game_version=game_version,
            verified_at=now if status == KnowledgeStatus.ACTIVE else None,
            created_by=actor_id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        revision = KnowledgeRevision(
            id=revision_id,
            entry_id=entry_id,
            revision_number=1,
            content=content,
            context=context,
            status=status.value,
            game_version=game_version,
            confidence=entry.confidence,
            source_snapshot=[],
            actor_id=actor_id,
            reason=reason,
            created_at=now,
        )
        async with self.database.session() as session:
            session.add_all([entry, revision])
        return entry_id

    async def revise(
        self,
        *,
        entry_id: UUID,
        actor_id: int,
        content: dict[str, Any],
        context: dict[str, Any],
        status: KnowledgeStatus,
        reason: str,
        game_version: str | None,
        confidence: float | None = None,
        expected_current_revision: int | None = None,
    ) -> UUID:
        now = datetime.now(UTC)
        async with self.database.session() as session:
            entry = await session.get(KnowledgeEntry, entry_id, with_for_update=True)
            if entry is None:
                raise KeyError(f"Knowledge entry {entry_id} does not exist.")
            self._check_expected_revision(entry, expected_current_revision)
            next_confidence = (
                entry.confidence if confidence is None else normalized_confidence(confidence)
            )
            source_snapshot = await self._source_snapshot(session, entry_id)
            return await self._commit_revision(
                session,
                entry=entry,
                actor_id=actor_id,
                content=content,
                context=context,
                status=status,
                reason=reason,
                game_version=game_version,
                confidence=next_confidence,
                source_snapshot=source_snapshot,
                now=now,
            )

    async def rollback(
        self,
        *,
        entry_id: UUID,
        target_revision_number: int,
        actor_id: int,
        reason: str,
        expected_current_revision: int | None = None,
    ) -> UUID:
        if target_revision_number < 1:
            raise ValueError("target_revision_number must be positive")
        reason = reason.strip()
        if not reason:
            raise ValueError("A rollback reason is required.")

        now = datetime.now(UTC)
        async with self.database.session() as session:
            entry = await session.get(KnowledgeEntry, entry_id, with_for_update=True)
            if entry is None:
                raise KeyError(f"Knowledge entry {entry_id} does not exist.")
            self._check_expected_revision(entry, expected_current_revision)
            target = await session.scalar(
                select(KnowledgeRevision)
                .where(KnowledgeRevision.entry_id == entry_id)
                .where(KnowledgeRevision.revision_number == target_revision_number)
            )
            if target is None:
                raise KeyError(
                    f"Knowledge entry {entry_id} has no revision {target_revision_number}."
                )
            if target_revision_number == entry.current_revision:
                raise ValueError("The requested revision is already current.")
            return await self._commit_revision(
                session,
                entry=entry,
                actor_id=actor_id,
                content=target.content,
                context=target.context,
                status=KnowledgeStatus(target.status),
                reason=f"Rollback to revision {target_revision_number}: {reason[:900]}",
                game_version=target.game_version,
                confidence=target.confidence,
                source_snapshot=target.source_snapshot,
                now=now,
            )

    @staticmethod
    def _check_expected_revision(
        entry: KnowledgeEntry, expected_current_revision: int | None
    ) -> None:
        if (
            expected_current_revision is not None
            and entry.current_revision != expected_current_revision
        ):
            raise KnowledgeRevisionConflictError(
                expected=expected_current_revision,
                actual=entry.current_revision,
            )

    @staticmethod
    async def _source_snapshot(session: AsyncSession, entry_id: UUID) -> list[dict[str, Any]]:
        links = await session.scalars(
            select(KnowledgeSource)
            .where(KnowledgeSource.entry_id == entry_id)
            .options(selectinload(KnowledgeSource.source))
        )
        snapshot = [
            {
                "source_id": str(link.source_id),
                "url": link.source.url,
                "title": link.source.title,
                "source_type": link.source.source_type,
                "publisher": link.source.publisher,
                "retrieved_at": link.source.retrieved_at.isoformat(),
                "content_hash": link.source.content_hash,
                "trust_score": str(link.source.trust_score),
                "supports_claim": link.supports_claim,
                "note": link.note,
            }
            for link in links
        ]
        return sorted(snapshot, key=lambda item: (item["url"], item["source_id"]))

    @staticmethod
    async def _commit_revision(
        session: AsyncSession,
        *,
        entry: KnowledgeEntry,
        actor_id: int,
        content: dict[str, Any],
        context: dict[str, Any],
        status: KnowledgeStatus,
        reason: str,
        game_version: str | None,
        confidence: Decimal,
        source_snapshot: list[dict[str, Any]],
        now: datetime,
    ) -> UUID:
        current_revision_id = await session.scalar(
            select(KnowledgeRevision.id)
            .where(KnowledgeRevision.entry_id == entry.id)
            .where(KnowledgeRevision.revision_number == entry.current_revision)
        )
        if current_revision_id is None:
            raise RuntimeError(
                f"Knowledge entry {entry.id} is missing current revision {entry.current_revision}."
            )

        next_revision = entry.current_revision + 1
        revision = KnowledgeRevision(
            entry_id=entry.id,
            revision_number=next_revision,
            content=content,
            context=context,
            status=status.value,
            game_version=game_version,
            confidence=confidence,
            source_snapshot=source_snapshot,
            actor_id=actor_id,
            reason=reason[:1000],
            created_at=now,
        )
        entry.content = content
        entry.context = context
        entry.context_hash = stable_context_hash(context)
        entry.status = status.value
        entry.game_version = game_version
        entry.confidence = confidence
        entry.current_revision = next_revision
        entry.verified_at = now if status == KnowledgeStatus.ACTIVE else entry.verified_at
        entry.updated_at = now
        session.add(revision)
        await session.flush()
        await _invalidate_cache_dependencies(session, current_revision_id)
        return revision.id


class CacheRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_valid(self, signature: str, tier: AnswerTier) -> AnswerCache | None:
        now = datetime.now(UTC)
        statement = (
            select(AnswerCache)
            .where(AnswerCache.question_signature == signature)
            .where(AnswerCache.answer_tier == tier.value)
            .where(AnswerCache.state == CacheState.ACTIVE.value)
            .where(AnswerCache.expires_at > now)
            .order_by(AnswerCache.updated_at.desc())
            .limit(1)
        )
        async with self.database.session() as session:
            cache = await session.scalar(statement)
            if cache is None or not cache.dependency_revision_ids:
                return cache
            revision_ids = [UUID(value) for value in cache.dependency_revision_ids]
            current_count = await session.scalar(
                select(func.count())
                .select_from(KnowledgeRevision)
                .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeRevision.entry_id)
                .where(KnowledgeRevision.id.in_(revision_ids))
                .where(KnowledgeRevision.revision_number == KnowledgeEntry.current_revision)
                .where(KnowledgeEntry.status == KnowledgeStatus.ACTIVE.value)
            )
            if int(current_count or 0) != len(revision_ids):
                cache.state = CacheState.STALE.value
                return None
            return cache

    async def create_candidate(
        self,
        *,
        signature: str,
        normalized_intent: str,
        entities: list[str],
        constraints: dict[str, Any],
        assumptions: dict[str, Any],
        answer_text: str,
        tier: AnswerTier,
        dependency_revision_ids: list[UUID],
        citations: list[SourceCitation],
        model_name: str | None,
        prompt_version: str,
        ttl: timedelta = timedelta(days=7),
    ) -> UUID:
        if len(set(dependency_revision_ids)) != len(dependency_revision_ids):
            raise ValueError("Cache dependencies must not contain duplicate revisions.")
        cache = AnswerCache(
            question_signature=signature,
            normalized_intent=normalized_intent,
            entities=entities,
            constraints=constraints,
            assumptions=assumptions,
            answer_text=answer_text,
            answer_tier=tier.value,
            dependency_revision_ids=[str(value) for value in dependency_revision_ids],
            citations=[citation.model_dump(mode="json") for citation in citations],
            model_name=model_name,
            prompt_version=prompt_version,
            state=CacheState.CANDIDATE.value,
            expires_at=datetime.now(UTC) + ttl,
        )
        async with self.database.session() as session:
            if dependency_revision_ids:
                current_dependencies = set(
                    await session.scalars(
                        select(KnowledgeRevision.id)
                        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeRevision.entry_id)
                        .where(KnowledgeRevision.id.in_(dependency_revision_ids))
                        .where(KnowledgeRevision.revision_number == KnowledgeEntry.current_revision)
                        .where(KnowledgeEntry.status == KnowledgeStatus.ACTIVE.value)
                        .with_for_update(read=True, of=KnowledgeEntry)
                    )
                )
                if current_dependencies != set(dependency_revision_ids):
                    raise ValueError(
                        "Cache dependencies must be current revisions of active knowledge."
                    )
            session.add(cache)
            await session.flush()
            return cache.id

    async def mark_feedback(self, cache_id: UUID, *, helpful: bool) -> CacheState:
        async with self.database.session() as session:
            cache = await session.get(AnswerCache, cache_id, with_for_update=True)
            if cache is None:
                raise KeyError(cache_id)
            if helpful:
                cache.positive_feedback += 1
                if cache.state == CacheState.CANDIDATE.value:
                    cache.state = CacheState.ACTIVE.value
            else:
                cache.negative_feedback += 1
                if cache.negative_feedback >= 2:
                    cache.state = CacheState.QUARANTINED.value
            return CacheState(cache.state)

    async def invalidate_revision(self, revision_id: UUID) -> int:
        async with self.database.session() as session:
            return await _invalidate_cache_dependencies(session, revision_id)


async def _invalidate_cache_dependencies(session: AsyncSession, revision_id: UUID) -> int:
    statement = (
        update(AnswerCache)
        .where(AnswerCache.dependency_revision_ids.contains([str(revision_id)]))
        .where(AnswerCache.state.in_([CacheState.ACTIVE.value, CacheState.CANDIDATE.value]))
        .values(state=CacheState.STALE.value)
    )
    result = await session.execute(statement)
    return int(cast(Any, result).rowcount or 0)


class TicketRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def open_or_increment(
        self,
        *,
        signature: str,
        sanitized_question: str,
        requester_user_id: int | None,
    ) -> UUID:
        statement = (
            select(UnansweredTicket)
            .where(UnansweredTicket.question_signature == signature)
            .where(UnansweredTicket.status.in_(["open", "investigating"]))
            .with_for_update()
        )
        async with self.database.session() as session:
            ticket = await session.scalar(statement)
            if ticket is not None:
                ticket.duplicate_count += 1
                return ticket.id
            ticket = UnansweredTicket(
                question_signature=signature,
                sanitized_question=sanitized_question,
                requester_user_id=requester_user_id,
            )
            session.add(ticket)
            await session.flush()
            return ticket.id


def sanitize_for_technicians(question: str) -> str:
    sanitized = re.sub(r"<@!?\d+>", "[member]", question)
    sanitized = re.sub(r"\b\d{15,22}\b", "[id]", sanitized)
    return sanitized.strip()[:2000]


def knowledge_context(hits: list[KnowledgeHit]) -> tuple[str, list[UUID], list[SourceCitation]]:
    blocks: list[str] = []
    revision_ids: list[UUID] = []
    citations: list[SourceCitation] = []
    seen_urls: set[str] = set()
    for hit in hits:
        entry = hit.entry
        revision = next(
            (item for item in entry.revisions if item.revision_number == entry.current_revision),
            None,
        )
        if revision is not None:
            revision_ids.append(revision.id)
        blocks.append(
            json.dumps(
                {
                    "entry_id": str(entry.id),
                    "subject": entry.subject,
                    "entity_type": entry.entity_type,
                    "claim_key": entry.claim_key,
                    "content": entry.content,
                    "context": entry.context,
                    "game_version": entry.game_version,
                    "verified_at": entry.verified_at.isoformat() if entry.verified_at else None,
                    "confidence": str(entry.confidence),
                },
                sort_keys=True,
                default=str,
            )
        )
        for link in entry.sources:
            source: Source = link.source
            if source.url in seen_urls:
                continue
            seen_urls.add(source.url)
            citations.append(
                SourceCitation(
                    title=source.title,
                    url=source.url,
                    source_type=source.source_type,
                    verified_at=source.retrieved_at,
                    official=source.source_type == "official",
                )
            )
    return "\n".join(blocks), revision_ids, citations

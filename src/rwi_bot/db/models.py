from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rwi_bot.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class SourceType(StrEnum):
    OFFICIAL = "official"
    REPRODUCIBLE_TEST = "reproducible_test"
    TECHNICIAN = "technician"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


class CacheState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    STALE = "stale"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


class TicketStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DUPLICATE = "duplicate"
    CLOSED = "closed"


class CommunityClaimStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    QUALIFIED = "qualified"
    INCORRECT = "incorrect"
    BUG = "bug"
    EXPLOIT = "exploit"


class ScheduledOperationStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class OperationRsvpStatus(StrEnum):
    GOING = "going"
    MAYBE = "maybe"
    WITHDRAWN = "withdrawn"


class KnowledgeEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_entries"
    __table_args__ = (
        UniqueConstraint("normalized_subject", "claim_key", "context_hash"),
        Index(
            "ix_knowledge_subject_trgm",
            "normalized_subject",
            postgresql_using="gin",
            postgresql_ops={"normalized_subject": "gin_trgm_ops"},
        ),
        Index(
            "ix_knowledge_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index(
            "ix_knowledge_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_subject: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    claim_key: Mapped[str] = mapped_column(String(160), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.CANDIDATE, index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.500"))
    game_version: Mapped[str | None] = mapped_column(String(80))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    revisions: Mapped[list[KnowledgeRevision]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )
    sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )


class KnowledgeRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_revisions"
    __table_args__ = (UniqueConstraint("entry_id", "revision_number"),)

    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    game_version: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.500"), nullable=False
    )
    source_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entry: Mapped[KnowledgeEntry] = relationship(back_populates="revisions")


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    publisher: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    trust_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    knowledge_entries: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), primary_key=True
    )
    supports_claim: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    entry: Mapped[KnowledgeEntry] = relationship(back_populates="sources")
    source: Mapped[Source] = relationship(back_populates="knowledge_entries")


class AnswerCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_cache"
    __table_args__ = (
        Index("ix_answer_cache_signature_state", "question_signature", "state"),
        Index(
            "ix_answer_cache_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    question_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_intent: Mapped[str] = mapped_column(String(120), nullable=False)
    entities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    dependency_revision_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    positive_feedback: Mapped[int] = mapped_column(Integer, default=0)
    negative_feedback: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(30), default=CacheState.CANDIDATE, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    detail_tier: Mapped[str] = mapped_column(String(20), default="standard")
    shd_level: Mapped[int] = mapped_column(Integer, default=1000)
    expertise_level: Mapped[int] = mapped_column(Integer, default=0)
    platform_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    learning_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)


class CommunityLoadout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_loadouts"
    __table_args__ = (
        UniqueConstraint("guild_id", "thread_id", name="uq_community_loadouts_guild_thread"),
        UniqueConstraint(
            "guild_id",
            "starter_message_id",
            name="uq_community_loadouts_guild_starter_message",
        ),
        Index(
            "ix_community_loadouts_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    forum_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    thread_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starter_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    game_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(
        String(40), default="community_submitted", nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommunityClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_claims"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "source_message_id",
            name="uq_community_claims_guild_source_message",
        ),
        Index(
            "ix_community_claims_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submitter_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    member_label: Mapped[str] = mapped_column(String(80), nullable=False)
    source_question: Mapped[str] = mapped_column(Text, nullable=False)
    prior_answer_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    game_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    risk_flag: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(30), default=CommunityClaimStatus.PENDING, nullable=False, index=True
    )
    review_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScheduledOperation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_operations"

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    organizer_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    activity: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    organizer_role: Mapped[str] = mapped_column(String(40), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    announcement_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    announcement_message_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    reminder_message_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    matchmaking_role_id: Mapped[int | None] = mapped_column(BigInteger)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(30), default=ScheduledOperationStatus.SCHEDULED, nullable=False, index=True
    )


class OperationRsvp(TimestampMixin, Base):
    __tablename__ = "operation_rsvps"

    operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("scheduled_operations.id", ondelete="CASCADE"), primary_key=True
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default=OperationRsvpStatus.GOING, nullable=False, index=True
    )
    selected_role: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Feedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "feedback"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    cache_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("answer_cache.id", ondelete="SET NULL"), index=True
    )
    answer_correlation_id: Mapped[UUID] = mapped_column(index=True)
    sentiment: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UnansweredTicket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "unanswered_tickets"

    question_signature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sanitized_question: Mapped[str] = mapped_column(Text, nullable=False)
    requester_user_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30), default=TicketStatus.OPEN, index=True)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1)
    technician_thread_id: Mapped[int | None] = mapped_column(BigInteger)
    resolved_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_entries.id", ondelete="SET NULL")
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)


class TechnicianDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "technician_drafts"

    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_entries.id", ondelete="SET NULL")
    )
    proposed_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    proposed_sources: Mapped[list[str]] = mapped_column(JSONB, default=list)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ApiUsage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_usage"

    provider: Mapped[str] = mapped_column(String(40), default="openai")
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    correlation_id: Mapped[UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ConversationSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_sessions"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    is_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text)
    active_constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DisciplineAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "discipline_actions"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

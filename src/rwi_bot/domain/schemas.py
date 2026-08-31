from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class AnswerTier(StrEnum):
    CONCISE = "concise"
    STANDARD = "standard"
    TECHNICAL = "technical"


class ConfidenceLabel(StrEnum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SourceCitation(BaseModel):
    title: str
    url: HttpUrl
    source_type: str
    verified_at: datetime | None = None
    official: bool = False


class AnswerAssumptions(BaseModel):
    level: int = 40
    shd: int = 1000
    expertise: int = 0
    mode: str = "PvE"
    platforms: list[str] = Field(default_factory=list)
    preferred_playstyle: str | None = Field(default=None, max_length=120)
    profile_notes: list[str] = Field(default_factory=list)
    maximum_item_rolls: bool = True
    include_conditional_buffs: bool = False


class AnswerRequest(BaseModel):
    user_id: int
    guild_id: int
    channel_id: int | None
    member_name: str | None = Field(default=None, max_length=80)
    question: str = Field(min_length=1, max_length=4000)
    tier: AnswerTier = AnswerTier.STANDARD
    assumptions: AnswerAssumptions = Field(default_factory=AnswerAssumptions)
    conversation_summary: str | None = Field(default=None, max_length=6000)
    is_dm: bool = False


class AnswerResult(BaseModel):
    text: str
    citations: list[SourceCitation] = Field(default_factory=list)
    assumptions: AnswerAssumptions = Field(default_factory=AnswerAssumptions)
    confidence: ConfidenceLabel = ConfidenceLabel.UNKNOWN
    knowledge_revision_ids: list[UUID] = Field(default_factory=list)
    cache_entry_id: UUID | None = None
    cache_hit: bool = False
    used_web_search: bool = False
    ticket_id: UUID | None = None
    awaiting_user_input: bool = False
    failure_code: str | None = Field(default=None, max_length=80)
    failure_summary: str | None = Field(default=None, max_length=1000)
    learning_opt_out: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IntentKind(StrEnum):
    FACT = "fact"
    PROFILE = "profile"
    ACQUISITION = "acquisition"
    BUILD_ADVICE = "build_advice"
    BUILD_RATING = "build_rating"
    MISSION_GUIDE = "mission_guide"
    PATCH_HISTORY = "patch_history"
    TECHNICIAN_EDIT = "technician_edit"
    SERVER_HELP = "server_help"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class InterpretedQuestion(BaseModel):
    intent: IntentKind
    normalized_question: str
    entities: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    assumptions: AnswerAssumptions = Field(default_factory=AnswerAssumptions)
    ambiguity: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeCandidate(BaseModel):
    subject: str
    entity_type: str
    claim_key: str
    content: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    source_urls: list[HttpUrl] = Field(min_length=1)
    game_version: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class AuditRecord(BaseModel):
    event_type: str
    actor_id: int | None = None
    target_type: str | None = None
    target_id: str | None = None
    reason: str | None = None
    correlation_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)

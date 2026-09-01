from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal
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


class GameResearchFinding(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    entity_type: str = Field(min_length=1, max_length=80)
    claim_key: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2000)
    content: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_class: Literal["official", "corroborated_community", "community_unverified"]
    source_urls: list[HttpUrl] = Field(default_factory=list)
    material_change: bool = False


class GameResearchReport(BaseModel):
    change_detected: bool
    current_game_version: str = Field(min_length=1, max_length=80)
    season_name: str = Field(min_length=1, max_length=120)
    season_started_on: date | None = None
    summary: str = Field(min_length=1, max_length=3000)
    official_evidence_urls: list[HttpUrl] = Field(default_factory=list)
    findings: list[GameResearchFinding] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class TargetedLootAssignment(BaseModel):
    category: Literal[
        "main_or_invaded_mission",
        "area",
        "classified_assignment",
        "raid",
        "other_location",
    ]
    location: str = Field(min_length=1, max_length=120)
    loot: str = Field(min_length=1, max_length=120)
    map_order: int = Field(default=999, ge=0, le=999)


class RotationMapImage(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    url: HttpUrl


class InvadedMissionRotation(BaseModel):
    main_missions: list[str] = Field(min_length=3, max_length=3)
    stronghold: str = Field(min_length=1, max_length=120)
    final_mission: Literal["Tidal Basin"] = "Tidal Basin"


class DescentTalentPoolRotation(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    offensive_talents: list[str] = Field(default_factory=list, max_length=20)
    defensive_talents: list[str] = Field(default_factory=list, max_length=20)
    utility_talents: list[str] = Field(default_factory=list, max_length=20)
    exotic_talents: list[str] = Field(default_factory=list, max_length=12)


class DarkZoneRotationAssignment(BaseModel):
    zone: Literal["Dark Zone East", "Dark Zone South", "Dark Zone West"]
    mode: str = Field(min_length=1, max_length=80)
    faction: str | None = Field(default=None, max_length=120)
    targeted_loot: str | None = Field(default=None, max_length=120)


class VendorStockEntry(BaseModel):
    vendor: Literal[
        "Cassie Mendoza",
        "Danny Weaver",
        "Countdown Requisition",
        "Clan Vendor",
        "Dark Zone East Vendor",
        "Dark Zone South Vendor",
        "Dark Zone West Vendor",
    ]
    category: Literal["gear", "weapon", "mod", "cache", "other"]
    name: str = Field(min_length=1, max_length=160)
    details: str | None = Field(default=None, max_length=500)


class RotationResearchItem(BaseModel):
    kind: Literal[
        "targeted_loot_dc",
        "targeted_loot_nyc",
        "targeted_loot_brooklyn",
        "invaded_missions",
        "legendary_project",
        "descent_pool",
        "classified_assignment",
        "dark_zone_mode",
        "vendor_stock",
        "other_rotation",
    ]
    title: str = Field(min_length=1, max_length=200)
    details: list[str] = Field(default_factory=list, max_length=24)
    targeted_loot: list[TargetedLootAssignment] = Field(default_factory=list, max_length=80)
    map_images: list[RotationMapImage] = Field(default_factory=list, max_length=4)
    invaded: InvadedMissionRotation | None = None
    descent: DescentTalentPoolRotation | None = None
    dark_zones: list[DarkZoneRotationAssignment] = Field(default_factory=list, max_length=3)
    vendor_stock: list[VendorStockEntry] = Field(default_factory=list, max_length=120)
    valid_from: date
    valid_until: date | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_class: Literal["official", "corroborated_community", "community_unverified"]
    source_urls: list[HttpUrl] = Field(min_length=1, max_length=8)


class RotationResearchReport(BaseModel):
    as_of: date
    summary: str = Field(min_length=1, max_length=1500)
    items: list[RotationResearchItem] = Field(default_factory=list, max_length=30)
    unavailable: list[str] = Field(default_factory=list, max_length=20)

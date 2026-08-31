from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select, update

from rwi_bot.db.models import (
    ApiUsage,
    CommunityClaim,
    CommunityClaimStatus,
    CommunityLoadout,
    ConversationSession,
    Feedback,
    UnansweredTicket,
    UserProfile,
)
from rwi_bot.db.session import Database
from rwi_bot.domain.schemas import AnswerAssumptions, AnswerTier
from rwi_bot.services.member_profiles import (
    MemberAnswerProfile,
    MemberProfileUpdate,
    detect_possible_personal_information,
)


@dataclass(frozen=True, slots=True)
class PrivacyResetResult:
    conversations_deleted: int
    feedback_deleted: int
    tickets_anonymized: int
    usage_records_anonymized: int
    community_loadouts_deleted: int
    pending_claims_deleted: int
    reviewed_claims_anonymized: int
    learning_opt_out_preserved: bool


@dataclass(frozen=True, slots=True)
class LearningPreferenceResult:
    community_loadouts_deleted: int = 0
    pending_claims_deleted: int = 0
    reviewed_claims_anonymized: int = 0


class ProfileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def learning_opted_out(self, user_id: int) -> bool:
        async with self.database.session() as session:
            value = await session.scalar(
                select(UserProfile.learning_opt_out).where(UserProfile.discord_user_id == user_id)
            )
            return bool(value)

    async def get_answer_profile(self, user_id: int) -> MemberAnswerProfile:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id)
        if profile is None:
            return MemberAnswerProfile(assumptions=AnswerAssumptions())
        return self._answer_profile(profile, persisted=True)

    async def update_answer_profile(
        self,
        user_id: int,
        profile_update: MemberProfileUpdate,
    ) -> MemberAnswerProfile:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id, with_for_update=True)
            if profile is None:
                profile = UserProfile(
                    discord_user_id=user_id,
                    detail_tier=AnswerTier.STANDARD.value,
                    shd_level=1000,
                    expertise_level=0,
                    platform_roles=[],
                    preferences={},
                    learning_opt_out=False,
                )
                session.add(profile)

            if profile_update.shd is not None:
                profile.shd_level = profile_update.shd
            if profile_update.expertise is not None:
                profile.expertise_level = profile_update.expertise
            if profile_update.detail_tier is not None:
                profile.detail_tier = profile_update.detail_tier.value
            if profile_update.platforms is not None:
                profile.platform_roles = list(profile_update.platforms)

            preferences = dict(profile.preferences or {})
            preference_updates = (
                ("level", profile_update.level),
                ("mode", profile_update.mode),
                ("gamertag", profile_update.gamertag),
                ("preferred_playstyle", profile_update.preferred_playstyle),
                ("maximum_item_rolls", profile_update.maximum_item_rolls),
                ("include_conditional_buffs", profile_update.include_conditional_buffs),
            )
            for key, value in preference_updates:
                if value is not None:
                    preferences[key] = value
            profile_notes = [
                " ".join(item.split())[:300]
                for item in preferences.get("profile_notes", [])
                if isinstance(item, str) and item.strip()
            ]
            if profile_update.profile_notes_remove:
                removal_terms = {
                    " ".join(item.split()).casefold()
                    for item in profile_update.profile_notes_remove
                    if item.strip()
                }
                profile_notes = [
                    note
                    for note in profile_notes
                    if not any(
                        term in note.casefold() or note.casefold() in term for term in removal_terms
                    )
                ]
            if profile_update.profile_notes_add:
                existing = {item.casefold() for item in profile_notes}
                for note in profile_update.profile_notes_add:
                    clean_note = " ".join(note.split())[:300]
                    if clean_note and clean_note.casefold() not in existing:
                        profile_notes.append(clean_note)
                        existing.add(clean_note.casefold())
            if profile_update.profile_notes_add is not None or profile_update.profile_notes_remove:
                preferences["profile_notes"] = profile_notes[-20:]
            if profile_update.fields:
                preferences["profile_customized"] = True
            profile.preferences = preferences
            return self._answer_profile(profile, persisted=True)

    async def scrub_sensitive_profile_data(self, user_id: int) -> int:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id, with_for_update=True)
            if profile is None:
                return 0
            preferences = dict(profile.preferences or {})
            notes = [
                item
                for item in preferences.get("profile_notes", [])
                if isinstance(item, str) and item.strip()
            ]
            retained_notes = [
                item for item in notes if not detect_possible_personal_information(item)
            ]
            removed = len(notes) - len(retained_notes)
            if retained_notes != notes:
                preferences["profile_notes"] = retained_notes
            for key in ("real_name", "birthday", "date_of_birth", "phone", "address", "email"):
                if key in preferences:
                    del preferences[key]
                    removed += 1
            profile.preferences = preferences
            return removed

    async def set_learning_opt_out(
        self, user_id: int, *, opted_out: bool
    ) -> LearningPreferenceResult:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id, with_for_update=True)
            if profile is None:
                profile = UserProfile(
                    discord_user_id=user_id,
                    learning_opt_out=opted_out,
                )
                session.add(profile)
            else:
                profile.learning_opt_out = opted_out
            if not opted_out:
                return LearningPreferenceResult()
            loadout_result = await session.execute(
                delete(CommunityLoadout).where(CommunityLoadout.author_user_id == user_id)
            )
            pending_claim_result = await session.execute(
                delete(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .where(CommunityClaim.status == CommunityClaimStatus.PENDING.value)
            )
            reviewed_claim_result = await session.execute(
                update(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .values(submitter_user_id=None, member_label="Former member")
            )
            return LearningPreferenceResult(
                community_loadouts_deleted=self._rowcount(loadout_result),
                pending_claims_deleted=self._rowcount(pending_claim_result),
                reviewed_claims_anonymized=self._rowcount(reviewed_claim_result),
            )

    async def export_data(self, user_id: int) -> dict[str, Any]:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id)
            conversations = list(
                await session.scalars(
                    select(ConversationSession)
                    .where(ConversationSession.discord_user_id == user_id)
                    .order_by(ConversationSession.created_at.asc())
                )
            )
            feedback = list(
                await session.scalars(
                    select(Feedback)
                    .where(Feedback.discord_user_id == user_id)
                    .order_by(Feedback.created_at.asc())
                )
            )
            community_loadouts = list(
                await session.scalars(
                    select(CommunityLoadout)
                    .where(CommunityLoadout.author_user_id == user_id)
                    .order_by(CommunityLoadout.submitted_at.asc())
                )
            )
            community_claims = list(
                await session.scalars(
                    select(CommunityClaim)
                    .where(CommunityClaim.submitter_user_id == user_id)
                    .order_by(CommunityClaim.created_at.asc())
                )
            )
        return {
            "profile": (
                None
                if profile is None
                else {
                    "detail_tier": profile.detail_tier,
                    "shd_level": profile.shd_level,
                    "expertise_level": profile.expertise_level,
                    "platform_roles": profile.platform_roles,
                    "preferences": profile.preferences,
                    "learning_opt_out": profile.learning_opt_out,
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat(),
                }
            ),
            "conversation_sessions": [
                {
                    "is_dm": item.is_dm,
                    "summary": item.summary,
                    "active_constraints": item.active_constraints,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                    "expires_at": item.expires_at.isoformat(),
                }
                for item in conversations
            ],
            "feedback": [
                {
                    "sentiment": item.sentiment,
                    "reason": item.reason,
                    "evidence_url": item.evidence_url,
                    "created_at": item.created_at.isoformat(),
                }
                for item in feedback
            ],
            "community_loadouts": [
                {
                    "title": item.title,
                    "content": item.content,
                    "tags": item.tags,
                    "source_url": item.source_url,
                    "game_version": item.game_version,
                    "verification_status": item.verification_status,
                    "submitted_at": item.submitted_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in community_loadouts
            ],
            "community_claims": [
                {
                    "source_question": item.source_question,
                    "claim_text": item.claim_text,
                    "source_url": item.source_url,
                    "game_version": item.game_version,
                    "status": item.status,
                    "risk_flag": item.risk_flag,
                    "review_note": item.review_note,
                    "reviewed_at": (
                        item.reviewed_at.isoformat() if item.reviewed_at is not None else None
                    ),
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in community_claims
            ],
            "retained_categories": [
                "security and moderation records",
                "immutable operational audit events",
                "anonymized cost accounting",
                "privacy-sanitized review tickets",
                "anonymized, human-reviewed community knowledge",
            ],
        }

    async def reset_private_state(self, user_id: int) -> PrivacyResetResult:
        async with self.database.session() as session:
            profile = await session.get(UserProfile, user_id, with_for_update=True)
            opted_out = bool(profile.learning_opt_out) if profile is not None else False

            conversation_result = await session.execute(
                delete(ConversationSession).where(ConversationSession.discord_user_id == user_id)
            )
            feedback_result = await session.execute(
                delete(Feedback).where(Feedback.discord_user_id == user_id)
            )
            ticket_result = await session.execute(
                update(UnansweredTicket)
                .where(UnansweredTicket.requester_user_id == user_id)
                .values(requester_user_id=None)
            )
            usage_result = await session.execute(
                update(ApiUsage)
                .where(ApiUsage.discord_user_id == user_id)
                .values(discord_user_id=None)
            )
            loadout_result = await session.execute(
                delete(CommunityLoadout).where(CommunityLoadout.author_user_id == user_id)
            )
            pending_claim_result = await session.execute(
                delete(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .where(CommunityClaim.status == CommunityClaimStatus.PENDING.value)
            )
            reviewed_claim_result = await session.execute(
                update(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .values(submitter_user_id=None, member_label="Former member")
            )

            if profile is not None:
                profile.detail_tier = "standard"
                profile.shd_level = 1000
                profile.expertise_level = 0
                profile.platform_roles = []
                profile.preferences = {}
                profile.learning_opt_out = opted_out

            return PrivacyResetResult(
                conversations_deleted=self._rowcount(conversation_result),
                feedback_deleted=self._rowcount(feedback_result),
                tickets_anonymized=self._rowcount(ticket_result),
                usage_records_anonymized=self._rowcount(usage_result),
                community_loadouts_deleted=self._rowcount(loadout_result),
                pending_claims_deleted=self._rowcount(pending_claim_result),
                reviewed_claims_anonymized=self._rowcount(reviewed_claim_result),
                learning_opt_out_preserved=opted_out,
            )

    @staticmethod
    def _rowcount(result: Any) -> int:
        return int(cast(Any, result).rowcount or 0)

    @staticmethod
    def _answer_profile(profile: UserProfile, *, persisted: bool) -> MemberAnswerProfile:
        preferences = profile.preferences if isinstance(profile.preferences, dict) else {}
        level = ProfileRepository._bounded_int(preferences.get("level"), 1, 40, 40)
        shd = ProfileRepository._bounded_int(profile.shd_level, 0, 1_000_000, 1000)
        expertise = ProfileRepository._bounded_int(profile.expertise_level, 0, 30, 0)
        mode = preferences.get("mode")
        if mode not in {"PvE", "PvP", "Both"}:
            mode = "PvE"
        platforms = [
            item
            for item in (getattr(profile, "platform_roles", None) or [])
            if isinstance(item, str) and item in {"Xbox", "PC", "PS"}
        ]
        playstyle = preferences.get("preferred_playstyle")
        if not isinstance(playstyle, str) or not playstyle.strip():
            playstyle = None
        else:
            playstyle = " ".join(playstyle.split())[:120]
        gamertag = preferences.get("gamertag")
        if not isinstance(gamertag, str) or not gamertag.strip():
            gamertag = None
        else:
            gamertag = " ".join(gamertag.split())[:32]
        profile_notes = [
            " ".join(item.split())[:300]
            for item in preferences.get("profile_notes", [])
            if isinstance(item, str) and item.strip()
        ][-20:]
        maximum_item_rolls = preferences.get("maximum_item_rolls")
        if not isinstance(maximum_item_rolls, bool):
            maximum_item_rolls = True
        include_conditional_buffs = preferences.get("include_conditional_buffs")
        if not isinstance(include_conditional_buffs, bool):
            include_conditional_buffs = False
        try:
            detail_tier = AnswerTier(profile.detail_tier)
        except (TypeError, ValueError):
            detail_tier = AnswerTier.STANDARD
        return MemberAnswerProfile(
            assumptions=AnswerAssumptions(
                level=level,
                shd=shd,
                expertise=expertise,
                mode=mode,
                platforms=platforms,
                preferred_playstyle=playstyle,
                profile_notes=profile_notes,
                maximum_item_rolls=maximum_item_rolls,
                include_conditional_buffs=include_conditional_buffs,
            ),
            detail_tier=detail_tier,
            persisted=(persisted and ProfileRepository._has_answer_customizations(profile)),
            gamertag=gamertag,
        )

    @staticmethod
    def _bounded_int(value: object, minimum: int, maximum: int, default: int) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum:
            return value
        return default

    @staticmethod
    def _has_answer_customizations(profile: UserProfile) -> bool:
        preferences = profile.preferences if isinstance(profile.preferences, dict) else {}
        if preferences.get("profile_customized") is True:
            return True
        if profile.shd_level != 1000 or profile.expertise_level != 0:
            return True
        if profile.detail_tier != AnswerTier.STANDARD.value or bool(
            getattr(profile, "platform_roles", None)
        ):
            return True
        return any(
            key in preferences
            for key in (
                "level",
                "mode",
                "gamertag",
                "preferred_playstyle",
                "profile_notes",
                "maximum_item_rolls",
                "include_conditional_buffs",
            )
        )

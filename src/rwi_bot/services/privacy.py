from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select, update

from rwi_bot.db.models import (
    ApiUsage,
    CommunityLoadout,
    ConversationSession,
    Feedback,
    UnansweredTicket,
    UserProfile,
)
from rwi_bot.db.session import Database


@dataclass(frozen=True, slots=True)
class PrivacyResetResult:
    conversations_deleted: int
    feedback_deleted: int
    tickets_anonymized: int
    usage_records_anonymized: int
    community_loadouts_deleted: int
    learning_opt_out_preserved: bool


class ProfileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def learning_opted_out(self, user_id: int) -> bool:
        async with self.database.session() as session:
            value = await session.scalar(
                select(UserProfile.learning_opt_out).where(UserProfile.discord_user_id == user_id)
            )
            return bool(value)

    async def set_learning_opt_out(self, user_id: int, *, opted_out: bool) -> int:
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
                return 0
            result = await session.execute(
                delete(CommunityLoadout).where(CommunityLoadout.author_user_id == user_id)
            )
            return self._rowcount(result)

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
            "retained_categories": [
                "security and moderation records",
                "immutable operational audit events",
                "anonymized cost accounting",
                "privacy-sanitized review tickets",
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
                learning_opt_out_preserved=opted_out,
            )

    @staticmethod
    def _rowcount(result: Any) -> int:
        return int(cast(Any, result).rowcount or 0)

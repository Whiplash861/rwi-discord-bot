from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from rwi_bot.db.models import MemberEndorsement, MemberExperience, MemberObservation, UserProfile
from rwi_bot.db.session import Database

_LABELS = {
    "Raid leader": r"raid leader",
    "Incursion leader": r"incursion leader",
    "PvP-focused": r"pvp[- ](?:focused|main|player)",
    "PvE-focused": r"pve[- ](?:focused|main|player)",
    "Healer main": r"healer main",
    "Tank main": r"tank main",
    "Sniper main": r"sniper main",
    "Experienced player": (
        r"(?:experienced|knowledgeable|veteran|expert)"
        r"(?: (?:division 2 )?player)?"
    ),
}


def endorsement_target(text: str) -> tuple[int, str] | None:
    # An attributable, affirmative statement about ONE exact member, never a question.
    if "?" in text or len(re.findall(r"<@!?\d+>", text)) != 1:
        return None
    for label, pattern in _LABELS.items():
        match = re.fullmatch(
            r"\s*<@!?(\d+)>\s+(?:is|has been)\s+"
            r"(?:(?:a|an|very|really|highly|great|good)\s+)*" + pattern + r"[.!\s]*",
            text,
            re.I,
        )
        if match:
            return int(match[1]), label
    return None


def is_experience_endorsement(text: str) -> bool:
    return endorsement_target(text) is not None


def self_reported_labels(text: str) -> tuple[str, ...]:
    if "?" in text:
        return ()
    # Narrow explicit self-reports. Mentioning a raid is not evidence of leadership.
    return tuple(
        label
        for label, pattern in _LABELS.items()
        if re.search(
            r"(?:^|[.!]\s*)i(?:'m| am)\s+(?:a |an )?" + pattern + r"(?=[.!]|$)",
            text.strip(),
            re.I,
        )
    )


def observation_fingerprint(claim: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", claim.casefold()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def demonstrates_experience(rows: list[MemberObservation], *, game_version: str) -> bool:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    valid = [
        r
        for r in rows
        if r.status == "corroborated"
        and r.provenance == "observed_advice"
        and r.game_version == game_version
        and r.created_at >= cutoff
    ]
    return (
        len({r.fingerprint for r in valid}) >= 5 and len({r.created_at.date() for r in valid}) >= 3
    )


class ExperienceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def endorse(
        self,
        *,
        guild_id: int,
        sponsor_id: int,
        target_id: int,
        note: str,
        message_id: int | None = None,
    ) -> None:
        if sponsor_id == target_id:
            raise ValueError("Self-endorsements are not independent recommendations.")
        now = datetime.now(UTC)
        async with self.database.session() as session:
            await session.execute(
                insert(MemberEndorsement)
                .values(
                    guild_id=guild_id,
                    sponsor_id=sponsor_id,
                    target_id=target_id,
                    note=note[:500],
                    source_message_id=message_id,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["guild_id", "sponsor_id", "target_id"],
                    set_={"note": note[:500], "updated_at": now, "source_message_id": message_id},
                )
            )

    async def verified(self, guild_id: int, target_id: int) -> bool:
        async with self.database.session() as session:
            return bool(
                await session.scalar(
                    select(MemberExperience.verified).where(
                        MemberExperience.guild_id == guild_id,
                        MemberExperience.target_id == target_id,
                    )
                )
            )

    async def experienced(self, guild_id: int, target_id: int, *, game_version: str) -> bool:
        async with self.database.session() as session:
            review = await session.scalar(
                select(MemberExperience).where(
                    MemberExperience.guild_id == guild_id, MemberExperience.target_id == target_id
                )
            )
        if review is not None:
            return review.verified  # Explicit revocation overrides automatic recognition.
        return demonstrates_experience(
            await self.observations(guild_id, target_id), game_version=game_version
        )

    async def observations(self, guild_id: int, target_id: int) -> list[MemberObservation]:
        async with self.database.session() as session:
            return list(
                await session.scalars(
                    select(MemberObservation)
                    .where(
                        MemberObservation.guild_id == guild_id,
                        MemberObservation.target_id == target_id,
                        MemberObservation.created_at >= datetime.now(UTC) - timedelta(days=90),
                    )
                    .order_by(MemberObservation.created_at.desc())
                    .limit(100)
                )
            )

    async def record(
        self,
        *,
        guild_id: int,
        target_id: int,
        message_id: int,
        label: str,
        provenance: str,
        game_version: str,
        claim: str = "",
    ) -> UUID | None:
        now = datetime.now(UTC)
        async with self.database.session() as session:
            if await session.scalar(
                select(UserProfile.learning_opt_out).where(UserProfile.discord_user_id == target_id)
            ):
                return None
            # Retain bounded gameplay-only observations, never a general-chat transcript.
            await session.execute(
                delete(MemberObservation).where(
                    MemberObservation.guild_id == guild_id,
                    MemberObservation.created_at < now - timedelta(days=90),
                )
            )
            if provenance == "observed_advice":
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                base = (
                    select(func.count())
                    .select_from(MemberObservation)
                    .where(
                        MemberObservation.guild_id == guild_id,
                        MemberObservation.provenance == provenance,
                        MemberObservation.created_at >= today,
                    )
                )
                if (await session.scalar(base) or 0) >= 6:
                    return None
                if (
                    await session.scalar(base.where(MemberObservation.target_id == target_id)) or 0
                ) >= 2:
                    return None
            return await session.scalar(
                insert(MemberObservation)
                .values(
                    guild_id=guild_id,
                    target_id=target_id,
                    source_message_id=message_id,
                    fingerprint=observation_fingerprint(claim or label),
                    label=label,
                    provenance=provenance,
                    status="pending" if claim else "self_reported",
                    game_version=game_version,
                    evidence={},
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(MemberObservation.id)
            )

    async def finish(
        self, observation_id: UUID, *, status: str, summary: str, source_urls: list[str]
    ) -> None:
        async with self.database.session() as session:
            await session.execute(
                update(MemberObservation)
                .where(
                    MemberObservation.id == observation_id, MemberObservation.status == "pending"
                )
                .values(
                    status=status,
                    evidence={"summary": summary[:500], "source_urls": source_urls[:6]},
                    updated_at=datetime.now(UTC),
                )
            )

    async def withdraw_message(self, guild_id: int, message_id: int) -> None:
        async with self.database.session() as session:
            await session.execute(
                delete(MemberEndorsement).where(
                    MemberEndorsement.guild_id == guild_id,
                    MemberEndorsement.source_message_id == message_id,
                )
            )
            await session.execute(
                delete(MemberObservation).where(
                    MemberObservation.guild_id == guild_id,
                    MemberObservation.source_message_id == message_id,
                )
            )

    async def review(
        self, *, guild_id: int, target_id: int, reviewer_id: int, verified: bool, note: str
    ) -> None:
        now = datetime.now(UTC)
        async with self.database.session() as session:
            await session.execute(
                insert(MemberExperience)
                .values(
                    guild_id=guild_id,
                    target_id=target_id,
                    reviewer_id=reviewer_id,
                    verified=verified,
                    note=note[:500],
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["guild_id", "target_id"],
                    set_={
                        "reviewer_id": reviewer_id,
                        "verified": verified,
                        "note": note[:500],
                        "updated_at": now,
                    },
                )
            )

    async def endorsements(self, guild_id: int, target_id: int) -> list[MemberEndorsement]:
        async with self.database.session() as session:
            return list(
                await session.scalars(
                    select(MemberEndorsement)
                    .where(
                        MemberEndorsement.guild_id == guild_id,
                        MemberEndorsement.target_id == target_id,
                    )
                    .limit(20)
                )
            )

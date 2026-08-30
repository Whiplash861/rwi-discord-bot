from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select

from rwi_bot.db.models import CommunityLoadout
from rwi_bot.db.session import Database
from rwi_bot.services.language import normalize_text

COMMUNITY_VERIFICATION_STATES = frozenset(
    {
        "community_submitted",
        "technician_verified",
        "rwi_tested",
        "mathematically_validated",
    }
)


@dataclass(frozen=True, slots=True)
class CommunityLoadoutHit:
    loadout: CommunityLoadout
    similarity: float


class CommunityLoadoutRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def upsert(
        self,
        *,
        guild_id: int,
        forum_channel_id: int,
        thread_id: int,
        starter_message_id: int,
        author_user_id: int,
        title: str,
        content: str,
        tags: list[str],
        source_url: str,
        game_version: str,
        submitted_at: datetime,
        verification_status: str = "community_submitted",
    ) -> UUID:
        clean_title = " ".join(title.split())[:300]
        clean_content = content.strip()[:2000]
        clean_tags = sorted({" ".join(tag.split())[:100] for tag in tags if tag.strip()})[:20]
        clean_version = " ".join(game_version.split())[:80]
        if not clean_title or not clean_content:
            raise ValueError("A community loadout needs a title and build description.")
        if verification_status not in COMMUNITY_VERIFICATION_STATES:
            raise ValueError("Unknown community loadout verification status.")
        if not clean_version:
            raise ValueError("A community loadout needs a game-version scope.")
        if not source_url.startswith("https://discord.com/channels/"):
            raise ValueError("Community loadout source_url must be a Discord channel link.")
        search_text = community_search_text(
            title=clean_title,
            content=clean_content,
            tags=clean_tags,
            game_version=clean_version,
        )
        now = datetime.now(UTC)
        async with self.database.session() as session:
            loadout = await session.scalar(
                select(CommunityLoadout)
                .where(CommunityLoadout.guild_id == guild_id)
                .where(CommunityLoadout.thread_id == thread_id)
                .with_for_update()
            )
            if loadout is None:
                loadout = CommunityLoadout(
                    guild_id=guild_id,
                    forum_channel_id=forum_channel_id,
                    thread_id=thread_id,
                    starter_message_id=starter_message_id,
                    author_user_id=author_user_id,
                    title=clean_title,
                    content=clean_content,
                    tags=clean_tags,
                    search_text=search_text,
                    source_url=source_url,
                    game_version=clean_version,
                    verification_status=verification_status,
                    active=True,
                    submitted_at=submitted_at,
                    created_at=now,
                    updated_at=now,
                )
                session.add(loadout)
            else:
                loadout.forum_channel_id = forum_channel_id
                loadout.starter_message_id = starter_message_id
                loadout.author_user_id = author_user_id
                loadout.title = clean_title
                loadout.content = clean_content
                loadout.tags = clean_tags
                loadout.search_text = search_text
                loadout.source_url = source_url
                loadout.game_version = clean_version
                loadout.verification_status = verification_status
                loadout.active = True
                loadout.submitted_at = submitted_at
                loadout.updated_at = now
            await session.flush()
            return loadout.id

    async def search(
        self,
        query: str,
        *,
        guild_id: int,
        game_version: str,
        limit: int = 3,
    ) -> list[CommunityLoadoutHit]:
        if not 1 <= limit <= 10:
            raise ValueError("Community loadout search limit must be between 1 and 10.")
        normalized = normalize_text(query)
        if not normalized:
            return []
        similarity = func.word_similarity(normalized, CommunityLoadout.search_text)
        statement = (
            select(CommunityLoadout, similarity.label("score"))
            .where(CommunityLoadout.guild_id == guild_id)
            .where(CommunityLoadout.game_version == game_version)
            .where(CommunityLoadout.active.is_(True))
            .where(similarity >= 0.24)
            .order_by(similarity.desc(), CommunityLoadout.updated_at.desc())
            .limit(limit)
        )
        async with self.database.session() as session:
            rows = (await session.execute(statement)).all()
        return [
            CommunityLoadoutHit(loadout=cast(CommunityLoadout, row[0]), similarity=float(row[1]))
            for row in rows
        ]

    async def by_author(self, user_id: int) -> list[CommunityLoadout]:
        async with self.database.session() as session:
            return list(
                await session.scalars(
                    select(CommunityLoadout)
                    .where(CommunityLoadout.author_user_id == user_id)
                    .order_by(CommunityLoadout.submitted_at.asc())
                )
            )

    async def remove_by_thread(self, *, guild_id: int, thread_id: int) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                delete(CommunityLoadout)
                .where(CommunityLoadout.guild_id == guild_id)
                .where(CommunityLoadout.thread_id == thread_id)
            )
            return int(cast(Any, result).rowcount or 0)

    async def remove_by_starter_message(self, *, guild_id: int, message_id: int) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                delete(CommunityLoadout)
                .where(CommunityLoadout.guild_id == guild_id)
                .where(CommunityLoadout.starter_message_id == message_id)
            )
            return int(cast(Any, result).rowcount or 0)

    async def remove_by_author(self, user_id: int) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                delete(CommunityLoadout).where(CommunityLoadout.author_user_id == user_id)
            )
            return int(cast(Any, result).rowcount or 0)


def community_search_text(*, title: str, content: str, tags: list[str], game_version: str) -> str:
    return normalize_text(" ".join((title, content, " ".join(tags), game_version)))

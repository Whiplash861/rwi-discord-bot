import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from rwi_bot.db.models import MemberObservation
from rwi_bot.db.session import Database
from rwi_bot.services.experience import ExperienceRepository
from rwi_bot.services.privacy import ProfileRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_private_observation_budget_review_and_privacy_are_persistent():
    if os.getenv("RWI_RUN_DB_INTEGRATION") != "1":
        pytest.skip("requires disposable PostgreSQL database")
    db = Database(os.environ["RWI_DATABASE_URL"])
    repo, privacy = ExperienceRepository(db), ProfileRepository(db)
    guild = uuid4().int % (2**60)
    user = guild + 1
    sponsor = guild + 2
    now = datetime.now(UTC)
    try:
        await repo.endorse(
            guild_id=guild,
            sponsor_id=sponsor,
            target_id=user,
            note="Peer recommendation",
            message_id=10,
        )
        assert not await repo.experienced(guild, user, game_version="current")
        for i in range(5):
            identifier = await repo.record(
                guild_id=guild,
                target_id=user,
                message_id=20 + i,
                label="Gameplay advice",
                provenance="observed_advice",
                game_version="current",
                claim=f"Distinct supported game claim {i}",
            )
            assert identifier is not None
            await repo.finish(
                identifier,
                status="corroborated",
                summary="Supported with conditions",
                source_urls=["https://example.test/source"],
            )
            async with db.session() as session:
                await session.execute(
                    update(MemberObservation)
                    .where(MemberObservation.id == identifier)
                    .values(created_at=now - timedelta(days=1 + i // 2))
                )
        assert await repo.experienced(guild, user, game_version="current")
        assert not await repo.experienced(guild, user, game_version="future")
        # Two budget reservations/day, even if a verifier crashes; duplicates don't add evidence.
        for i in range(3):
            identifier = await repo.record(
                guild_id=guild,
                target_id=user,
                message_id=30 + i,
                label="Gameplay advice",
                provenance="observed_advice",
                game_version="current",
                claim=f"Budget reservation {i}",
            )
            assert (identifier is not None) == (i < 2)
        await repo.review(
            guild_id=guild,
            target_id=user,
            reviewer_id=sponsor,
            verified=False,
            note="Revoke pending context review",
        )
        assert not await repo.experienced(guild, user, game_version="current")
        exported = await privacy.export_data(user)
        assert len(exported["private_gameplay_observations"]) == 7
        assert len(exported["private_experience_endorsements"]) == 1
        await privacy.set_learning_opt_out(user, opted_out=True)
        assert not await repo.observations(guild, user)
        assert not await repo.endorsements(guild, user)
        assert (
            await repo.record(
                guild_id=guild,
                target_id=user,
                message_id=42,
                label="Healer main",
                provenance="self_reported",
                game_version="current",
            )
            is None
        )
        await privacy.reset_private_state(user)
        assert await privacy.learning_opted_out(user)
        async with db.session() as session:
            assert not list(
                await session.scalars(
                    select(MemberObservation).where(MemberObservation.guild_id == guild)
                )
            )
    finally:
        await db.dispose()

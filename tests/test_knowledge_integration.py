from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from rwi_bot.db.models import AnswerCache, CacheState, KnowledgeEntry, KnowledgeStatus
from rwi_bot.db.session import Database
from rwi_bot.domain.schemas import AnswerTier
from rwi_bot.services.knowledge import CacheRepository, KnowledgeRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revision_invalidation_and_rollback_are_transactional() -> None:
    if os.getenv("RWI_RUN_DB_INTEGRATION") != "1":
        pytest.skip("set RWI_RUN_DB_INTEGRATION=1 against a disposable test database")
    database_url = os.environ["RWI_DATABASE_URL"]
    database = Database(database_url)
    knowledge = KnowledgeRepository(database)
    cache = CacheRepository(database)
    entry_id = None
    cache_id = None
    test_suffix = uuid4().hex
    try:
        entry_id = await knowledge.add_candidate(
            subject=f"integration-revision-test-{test_suffix}",
            entity_type="test",
            claim_key=f"transactional-cache-invalidation-{test_suffix}",
            content={"value": 1},
            context={"mode": "pve"},
            actor_id=None,
            reason="Integration fixture",
            game_version="1.0-test",
            confidence=0.8,
            status=KnowledgeStatus.ACTIVE,
        )
        entry = await knowledge.get(entry_id)
        assert entry is not None
        revision_one = next(item for item in entry.revisions if item.revision_number == 1)
        cache_id = await cache.create_candidate(
            signature=test_suffix,
            normalized_intent="integration revision",
            entities=[],
            constraints={},
            assumptions={},
            answer_text="test answer",
            tier=AnswerTier.STANDARD,
            dependency_revision_ids=[revision_one.id],
            citations=[],
            model_name=None,
            prompt_version="integration",
            ttl=timedelta(minutes=5),
        )
        await cache.mark_feedback(cache_id, helpful=True)
        assert await cache.get_valid(test_suffix, AnswerTier.STANDARD)

        await knowledge.revise(
            entry_id=entry_id,
            actor_id=1,
            content={"value": 2},
            context={"mode": "pvp"},
            status=KnowledgeStatus.ACTIVE,
            reason="Integration revision",
            game_version="2.0-test",
            confidence=0.9,
        )

        assert await cache.get_valid(test_suffix, AnswerTier.STANDARD) is None
        async with database.session() as session:
            cached = await session.get(AnswerCache, cache_id)
            assert cached is not None
            assert cached.state == CacheState.STALE.value
        with pytest.raises(ValueError, match="current revisions"):
            await cache.create_candidate(
                signature=f"{test_suffix}-stale",
                normalized_intent="stale dependency",
                entities=[],
                constraints={},
                assumptions={},
                answer_text="must not be saved",
                tier=AnswerTier.STANDARD,
                dependency_revision_ids=[revision_one.id],
                citations=[],
                model_name=None,
                prompt_version="integration",
            )

        await knowledge.rollback(
            entry_id=entry_id,
            target_revision_number=1,
            actor_id=2,
            reason="Integration rollback",
        )
        restored = await knowledge.get(entry_id)
        assert restored is not None
        assert restored.current_revision == 3
        assert restored.content == {"value": 1}
        assert restored.game_version == "1.0-test"
    finally:
        if cache_id is not None or entry_id is not None:
            async with database.session() as session:
                if cache_id is not None:
                    await session.execute(delete(AnswerCache).where(AnswerCache.id == cache_id))
                if entry_id is not None:
                    await session.execute(
                        delete(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
                    )
        await database.dispose()

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rwi_bot.data.red_horizon import (
    GAME_VERSION,
    OFFICIAL_SOURCE,
    RED_HORIZON_SEEDS,
)
from rwi_bot.services.knowledge import (
    KnowledgeIdentityConflictError,
    KnowledgeRepository,
)


@dataclass(frozen=True, slots=True)
class SeedPreview:
    total: int
    missing: int
    existing: int


@dataclass(frozen=True, slots=True)
class SeedResult:
    created_entry_ids: tuple[UUID, ...]
    skipped_existing: int


async def preview_red_horizon_seed(knowledge: KnowledgeRepository) -> SeedPreview:
    existing = 0
    for seed in RED_HORIZON_SEEDS:
        if await knowledge.identity_exists(
            subject=seed.subject,
            claim_key=seed.claim_key,
            context=seed.context,
        ):
            existing += 1
    return SeedPreview(
        total=len(RED_HORIZON_SEEDS),
        missing=len(RED_HORIZON_SEEDS) - existing,
        existing=existing,
    )


async def apply_red_horizon_seed(knowledge: KnowledgeRepository, *, actor_id: int) -> SeedResult:
    created: list[UUID] = []
    skipped = 0
    for seed in RED_HORIZON_SEEDS:
        try:
            entry_id = await knowledge.add_candidate(
                subject=seed.subject,
                entity_type=seed.entity_type,
                claim_key=seed.claim_key,
                content=seed.content,
                context=seed.context,
                actor_id=actor_id,
                reason="Official Red Horizon launch baseline import",
                game_version=GAME_VERSION,
                confidence=seed.confidence,
                status=seed.status,
                sources=(OFFICIAL_SOURCE,),
            )
        except KnowledgeIdentityConflictError:
            skipped += 1
        else:
            created.append(entry_id)
    return SeedResult(created_entry_ids=tuple(created), skipped_existing=skipped)

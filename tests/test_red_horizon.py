from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from rwi_bot.data.red_horizon import (
    GAME_VERSION,
    OFFICIAL_BRAND_BREAKDOWN_URL,
    OFFICIAL_SOURCE_URL,
    RED_HORIZON_BRAND_BONUSES,
    RED_HORIZON_SEEDS,
)
from rwi_bot.db.models import KnowledgeStatus
from rwi_bot.services.knowledge import KnowledgeIdentityConflictError
from rwi_bot.services.seeding import apply_red_horizon_seed, preview_red_horizon_seed


class FakeKnowledgeRepository:
    def __init__(self, existing_subjects: set[str] | None = None) -> None:
        self.existing_subjects = existing_subjects or set()
        self.created: list[dict[str, object]] = []

    async def identity_exists(
        self, *, subject: str, claim_key: str, context: dict[str, object]
    ) -> bool:
        return subject in self.existing_subjects

    async def add_candidate(self, **kwargs: object) -> UUID:
        subject = str(kwargs["subject"])
        if subject in self.existing_subjects:
            raise KnowledgeIdentityConflictError
        self.existing_subjects.add(subject)
        self.created.append(kwargs)
        return uuid4()


def seed(subject: str) -> object:
    return next(item for item in RED_HORIZON_SEEDS if item.subject == subject)


def test_red_horizon_seed_catalog_is_unique_and_current() -> None:
    identities = {
        (item.subject.casefold(), item.claim_key, repr(sorted(item.context.items())))
        for item in RED_HORIZON_SEEDS
    }

    assert len(RED_HORIZON_SEEDS) == 47
    assert len(identities) == len(RED_HORIZON_SEEDS)
    assert all(item.status == KnowledgeStatus.ACTIVE for item in RED_HORIZON_SEEDS)
    assert OFFICIAL_SOURCE_URL.startswith("https://www.ubisoft.com/")
    assert OFFICIAL_BRAND_BREAKDOWN_URL.startswith("https://canopy.ubisoft.com/AssetLink/")
    assert GAME_VERSION == "Y8S3 Red Horizon"


def test_red_horizon_launch_values_use_release_values() -> None:
    fafnir = seed("Fafnir")
    iron_will = seed("Iron Will")
    ember_engine = seed("Ember Engine")

    assert fafnir.content["burn_chance_per_shot"] == 0.40  # type: ignore[attr-defined]
    assert (
        fafnir.content["weapon_damage_amplification_from_status_effect_bonus"]  # type: ignore[attr-defined]
        == 0.50
    )
    assert iron_will.content["pve_cooldown_seconds"] == 2  # type: ignore[attr-defined]
    assert iron_will.content["pvp_cooldown_seconds"] == 3  # type: ignore[attr-defined]
    assert ember_engine.content["four_piece_burn_chance"] == 0.40  # type: ignore[attr-defined]
    assert ember_engine.content["chest_burn_chance"] == 0.60  # type: ignore[attr-defined]


def test_red_horizon_brand_catalog_uses_final_ubisoft_values() -> None:
    belstone = seed("Belstone Armory")
    golan = seed("Golan Gear Ltd")

    assert len(RED_HORIZON_BRAND_BONUSES) == 29
    assert belstone.content == {  # type: ignore[attr-defined]
        "one_piece": "+1% Armor Regeneration",
        "two_piece": "+100% Increased Threat (+100% PvP)",
        "three_piece": "+36% Protection from Elites (+20% PvP)",
    }
    assert golan.content["one_piece"] == "+20% Explosive Resistance (+20% PvP)"  # type: ignore[attr-defined]
    assert golan.content["two_piece"] == "+1.5% Armor Regeneration"  # type: ignore[attr-defined]
    assert golan.content["three_piece"] == "+150% Increased Threat (+150% PvP)"  # type: ignore[attr-defined]
    assert len(belstone.sources) == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_seed_preview_and_apply_are_create_only_and_idempotent() -> None:
    repository = FakeKnowledgeRepository({"Fafnir", "Iron Will"})

    preview = await preview_red_horizon_seed(repository)  # type: ignore[arg-type]
    result = await apply_red_horizon_seed(repository, actor_id=42)  # type: ignore[arg-type]
    second = await apply_red_horizon_seed(repository, actor_id=42)  # type: ignore[arg-type]

    assert preview.total == 47
    assert preview.existing == 2
    assert preview.missing == 45
    assert len(result.created_entry_ids) == 45
    assert result.skipped_existing == 2
    assert len(second.created_entry_ids) == 0
    assert second.skipped_existing == 47
    assert all(item["actor_id"] == 42 for item in repository.created)
    assert all(item["game_version"] == GAME_VERSION for item in repository.created)

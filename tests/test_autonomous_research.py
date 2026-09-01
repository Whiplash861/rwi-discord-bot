from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from rwi_bot.domain.schemas import (
    GameResearchFinding,
    GameResearchReport,
    SourceCitation,
)
from rwi_bot.services.autonomous_research import (
    AutonomousResearchService,
    AutonomyStateStore,
)


@pytest.mark.asyncio
async def test_autonomy_promotes_only_strict_official_evidence(tmp_path: Path) -> None:
    official_url = "https://www.ubisoft.com/game/the-division/news/patch"
    community_url = "https://www.reddit.com/r/thedivision/comments/report"
    report = GameResearchReport(
        change_detected=True,
        current_game_version="Y8S3 Red Horizon",
        season_name="Red Horizon",
        season_started_on=date(2026, 8, 27),
        summary="One official adjustment and one community report were found.",
        official_evidence_urls=[official_url],
        findings=[
            GameResearchFinding(
                subject="Official balance adjustment",
                entity_type="patch",
                claim_key="weapon_balance",
                summary="An official balance value changed.",
                content={"change": "official"},
                context={"published_on": "2026-08-30"},
                confidence=0.98,
                evidence_class="official",
                source_urls=[official_url],
                material_change=True,
            ),
            GameResearchFinding(
                subject="Reported player interaction",
                entity_type="bug",
                claim_key="reported_interaction",
                summary="Players report an interaction that still needs reproduction.",
                content={"change": "reported"},
                context={"published_on": "2026-08-30"},
                confidence=0.82,
                evidence_class="corroborated_community",
                source_urls=[community_url],
                material_change=True,
            ),
        ],
    )
    citations = [
        SourceCitation(
            title="Official patch",
            url=official_url,
            source_type="official_web",
            official=True,
        ),
        SourceCitation(
            title="Player report",
            url=community_url,
            source_type="community_forum",
            official=False,
        ),
    ]
    ai = SimpleNamespace(
        research_game_updates=AsyncMock(
            return_value=SimpleNamespace(report=report, citations=citations)
        )
    )
    knowledge = SimpleNamespace(add_candidate=AsyncMock())
    cache = SimpleNamespace(invalidate_all=AsyncMock(return_value=4))
    qa = SimpleNamespace(set_current_game_version=Mock())
    audit = SimpleNamespace(record=AsyncMock())
    service = AutonomousResearchService(
        ai=cast(Any, ai),
        knowledge=cast(Any, knowledge),
        cache=cast(Any, cache),
        qa=cast(Any, qa),
        audit=cast(Any, audit),
        state_store=AutonomyStateStore(
            tmp_path / "autonomy.json",
            initial_game_version="Y8S3 Red Horizon",
            initial_started_on=date(2026, 8, 27),
        ),
        owner_user_id=42,
        enabled=True,
        full_sweep_hours=24,
        maximum_findings=20,
        auto_promote_official=True,
    )
    await service.initialize()

    outcome = await service.run_once(force_full=True)

    assert outcome.promoted == 1
    assert outcome.staged == 1
    statuses = [call.kwargs["status"].value for call in knowledge.add_candidate.await_args_list]
    assert statuses == ["active", "candidate"]
    cache.invalidate_all.assert_not_awaited()
    saved = await service.status()
    assert saved.last_status == "completed"
    assert saved.last_full_sweep_at is not None


@pytest.mark.asyncio
async def test_new_season_requires_retrieved_official_evidence(tmp_path: Path) -> None:
    report = GameResearchReport(
        change_detected=True,
        current_game_version="Y9S1 Unconfirmed",
        season_name="Unconfirmed",
        season_started_on=date(2026, 10, 1),
        summary="A community post claims a new season.",
        official_evidence_urls=["https://example.invalid/claim"],
    )
    qa = SimpleNamespace(set_current_game_version=Mock())
    cache = SimpleNamespace(invalidate_all=AsyncMock(return_value=10))
    service = AutonomousResearchService(
        ai=cast(
            Any,
            SimpleNamespace(
                research_game_updates=AsyncMock(
                    return_value=SimpleNamespace(report=report, citations=[])
                )
            ),
        ),
        knowledge=cast(Any, SimpleNamespace(add_candidate=AsyncMock())),
        cache=cast(Any, cache),
        qa=cast(Any, qa),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        state_store=AutonomyStateStore(
            tmp_path / "autonomy.json",
            initial_game_version="Y8S3 Red Horizon",
            initial_started_on=date(2026, 8, 27),
        ),
        owner_user_id=42,
        enabled=True,
        full_sweep_hours=24,
        maximum_findings=20,
        auto_promote_official=True,
    )
    await service.initialize()
    qa.set_current_game_version.reset_mock()

    outcome = await service.run_once(force_full=True)

    assert outcome.season_changed is False
    assert (await service.status()).current_game_version == "Y8S3 Red Horizon"
    qa.set_current_game_version.assert_not_called()
    cache.invalidate_all.assert_not_awaited()

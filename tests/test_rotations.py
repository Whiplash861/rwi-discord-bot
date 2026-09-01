from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from rwi_bot.cogs.rotations import rotation_embeds
from rwi_bot.domain.schemas import (
    RotationResearchItem,
    RotationResearchReport,
    SourceCitation,
)
from rwi_bot.services.rotations import RotationService, RotationStateStore

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
ESCALATION_URL = "https://example.invalid/escalation.json"
CALENDAR_URL = "https://example.invalid/calendar.json"


def escalation_payload(day: str = "2026-09-01") -> dict[str, object]:
    return {
        "Escalation": [
            {
                "week": "2026-09-01",
                "missions": ["The Tombs", "Manning National Zoo"],
                "target_loot_by_day": [
                    {
                        "day": day,
                        "target_loot": ["Skill MOD", "Aegis"],
                        "prototype_gear_cache": "kneepads",
                        "prototype_weapon_cache": "mmr",
                    }
                ],
            }
        ]
    }


def calendar_payload() -> dict[str, object]:
    return {
        "calendar": {
            "events": [
                {
                    "name": "Descent Playlist Rotation",
                    "title": "Descent Playlist Rotation",
                    "category": "Descent",
                    "occurs": "Cyclic",
                    "durationSeconds": 259200,
                    "cycleSeed": "2026-08-25T00:00:00Z",
                    "cycleDuration": 259200,
                },
                {
                    "name": "Red Horizon",
                    "title": "Red Horizon",
                    "category": "Season",
                    "occurs": "Once",
                    "durationSeconds": 7862400,
                    "scheduledStart": "2026-08-27T08:00:00Z",
                    "scheduledActiveEnd": "2026-11-26T08:00:00Z",
                },
                {
                    "name": "SHD Exposed",
                    "title": "SHD Exposed",
                    "category": "Global Event",
                    "occurs": "Once",
                    "durationSeconds": 604800,
                    "scheduledStart": "2026-09-01T08:00:00Z",
                    "scheduledActiveEnd": "2026-09-08T08:00:00Z",
                },
            ]
        }
    }


def researched_item(
    kind: str,
    title: str,
    details: list[str],
    url: str,
    *,
    evidence_class: str = "corroborated_community",
    confidence: float = 0.91,
    **content: object,
) -> RotationResearchItem:
    return RotationResearchItem.model_validate(
        {
            "kind": kind,
            "title": title,
            "details": details,
            "valid_from": "2026-09-01",
            "valid_until": "2026-09-07",
            "confidence": confidence,
            "evidence_class": evidence_class,
            "source_urls": [url],
            **content,
        }
    )


def build_service(
    tmp_path: Path,
    *,
    ai: object,
    stale_escalation: bool = False,
) -> RotationService:
    async def fetch_json(url: str) -> object:
        if url == ESCALATION_URL:
            return escalation_payload("2026-09-02" if stale_escalation else "2026-09-01")
        if url == CALENDAR_URL:
            return calendar_payload()
        raise AssertionError(f"unexpected URL: {url}")

    return RotationService(
        ai=cast(Any, ai),
        state_store=RotationStateStore(tmp_path / "rotation-state.json"),
        owner_user_id=42,
        current_game_version=lambda: "Y8S3 Red Horizon",
        escalation_url=ESCALATION_URL,
        calendar_url=CALENDAR_URL,
        web_refresh_hours=6,
        enabled=True,
        fetch_json=fetch_json,
    )


@pytest.mark.asyncio
async def test_collect_builds_all_rotation_posts_from_dated_feeds_and_gated_web(
    tmp_path: Path,
) -> None:
    dc_url = "https://prototrack.gg/target-loot/current"
    invasion_url = "https://when.shd.support/rotation/invasion"
    weak_url = "https://www.reddit.com/r/thedivision/comments/unverified"
    report = RotationResearchReport(
        as_of=date(2026, 9, 1),
        summary="Current dated rotations researched.",
        items=[
            researched_item(
                "targeted_loot_dc",
                "Washington targeted loot",
                [],
                dc_url,
                targeted_loot=[
                    {
                        "category": "area",
                        "location": "Downtown East",
                        "loot": "Assault Rifles",
                        "map_order": 10,
                    },
                    {
                        "category": "raid",
                        "location": "Dark Hours",
                        "loot": "Gear System Mods",
                        "map_order": 20,
                    },
                ],
                map_images=[
                    {
                        "label": "Washington, D.C. Targeted Loot Map",
                        "url": "https://images.example.invalid/dc.png",
                    }
                ],
            ),
            researched_item(
                "invaded_missions",
                "Weekly invasion",
                [],
                invasion_url,
                invaded={
                    "main_missions": [
                        "Jefferson Trade Center",
                        "Lincoln Memorial",
                        "Space Administration HQ",
                    ],
                    "stronghold": "Capitol Building",
                    "final_mission": "Tidal Basin",
                },
            ),
            researched_item(
                "legendary_project",
                "Legendary project",
                ["District Union Arena"],
                weak_url,
                evidence_class="community_unverified",
                confidence=0.72,
            ),
        ],
    )
    citations = [
        SourceCitation(
            title="Current target loot",
            url=dc_url,
            source_type="community_reference",
        ),
        SourceCitation(
            title="Current invasion",
            url=invasion_url,
            source_type="community_reference",
        ),
        SourceCitation(
            title="Unverified post",
            url=weak_url,
            source_type="community_forum",
        ),
    ]
    ai = SimpleNamespace(
        research_current_rotations=AsyncMock(
            return_value=SimpleNamespace(report=report, citations=citations)
        )
    )
    service = build_service(tmp_path, ai=ai)

    snapshot = await service.collect(now=NOW)

    assert len(snapshot.publications) == 5
    by_key = {publication.key: publication for publication in snapshot.publications}
    daily_text = "\n".join(field.value for field in by_key["daily-targeted-loot"].fields)
    weekly_text = "\n".join(field.value for field in by_key["weekly-mission-rotations"].fields)
    descent_text = "\n".join(field.value for field in by_key["descent-rotation"].fields)
    seasonal_text = "\n".join(field.value for field in by_key["seasonal-rotations"].fields)
    assert "Downtown East:** Assault Rifles" in daily_text
    assert "The Tombs" in daily_text
    assert "Skill MOD" in daily_text
    assert "Capitol Building" in weekly_text
    assert "Tidal Basin" in weekly_text
    assert "District Union Arena" not in weekly_text
    assert "complete dated assignment" in weekly_text
    assert len(by_key["daily-targeted-loot"].images) == 1
    embeds = rotation_embeds(by_key["daily-targeted-loot"])
    assert len(embeds) == 2
    assert embeds[1].image.url == "https://images.example.invalid/dc.png"
    assert "<t:1788393600:F>" in descent_text  # 2026-09-03 00:00 UTC
    assert "SHD Exposed" in seasonal_text
    assert snapshot.warnings == ()


@pytest.mark.asyncio
async def test_collect_reuses_still_valid_web_cache_between_research_windows(
    tmp_path: Path,
) -> None:
    url = "https://prototrack.gg/current"
    report = RotationResearchReport(
        as_of=date(2026, 9, 1),
        summary="Current rotations.",
        items=[
            researched_item(
                "targeted_loot_brooklyn",
                "Brooklyn targeted loot",
                [],
                url,
                targeted_loot=[
                    {
                        "category": "area",
                        "location": "DUMBO",
                        "loot": "Marksman Rifles",
                    }
                ],
            )
        ],
    )
    ai = SimpleNamespace(
        research_current_rotations=AsyncMock(
            return_value=SimpleNamespace(
                report=report,
                citations=[
                    SourceCitation(
                        title="Current rotations",
                        url=url,
                        source_type="community_reference",
                    )
                ],
            )
        )
    )
    service = build_service(tmp_path, ai=ai)

    await service.collect(now=NOW)
    second = await service.collect(now=NOW.replace(hour=13))

    assert ai.research_current_rotations.await_count == 1
    assert second.web_researched is False
    assert second.used_cached_web is True
    assert "DUMBO:** Marksman Rifles" in "\n".join(
        field.value for field in second.publications[0].fields
    )


@pytest.mark.asyncio
async def test_collect_researches_again_immediately_after_daily_reset(tmp_path: Path) -> None:
    report = RotationResearchReport(
        as_of=date(2026, 9, 1),
        summary="No complete live assignments.",
        items=[],
    )
    ai = SimpleNamespace(
        research_current_rotations=AsyncMock(
            return_value=SimpleNamespace(report=report, citations=[])
        )
    )
    service = build_service(tmp_path, ai=ai)

    await service.collect(now=NOW.replace(hour=7))
    second = await service.collect(now=NOW.replace(hour=9))

    assert ai.research_current_rotations.await_count == 2
    assert second.web_researched is True


@pytest.mark.asyncio
async def test_future_escalation_data_is_not_published_as_today(
    tmp_path: Path,
) -> None:
    ai = SimpleNamespace(
        research_current_rotations=AsyncMock(
            return_value=SimpleNamespace(
                report=RotationResearchReport(
                    as_of=date(2026, 9, 1),
                    summary="Nothing corroborated.",
                    items=[],
                ),
                citations=[],
            )
        )
    )
    service = build_service(tmp_path, ai=ai, stale_escalation=True)

    snapshot = await service.collect(now=NOW)

    assert "structured Escalation feed was invalid or out of date" in snapshot.warnings[0]
    assert "temporarily unavailable" in snapshot.publications[0].fields[1].value


@pytest.mark.asyncio
async def test_partial_invasion_descent_and_dark_zone_reports_are_not_published(
    tmp_path: Path,
) -> None:
    source_url = "https://example.invalid/current-rotations"
    report = RotationResearchReport(
        as_of=date(2026, 9, 1),
        summary="Incomplete reports.",
        items=[
            researched_item(
                "invaded_missions",
                "Incomplete invasion",
                ["Jefferson Trade Center"],
                source_url,
            ),
            researched_item(
                "descent_pool",
                "Pool cadence only",
                ["Changes every three days"],
                source_url,
            ),
            researched_item(
                "dark_zone_mode",
                "One zone only",
                [],
                source_url,
                dark_zones=[{"zone": "Dark Zone East", "mode": "Blackout"}],
            ),
        ],
    )
    ai = SimpleNamespace(
        research_current_rotations=AsyncMock(
            return_value=SimpleNamespace(
                report=report,
                citations=[
                    SourceCitation(
                        title="Current rotations",
                        url=source_url,
                        source_type="community_reference",
                    )
                ],
            )
        )
    )
    service = build_service(tmp_path, ai=ai)

    snapshot = await service.collect(now=NOW)

    weekly = next(item for item in snapshot.publications if item.key == "weekly-mission-rotations")
    descent = next(item for item in snapshot.publications if item.key == "descent-rotation")
    seasonal = next(item for item in snapshot.publications if item.key == "seasonal-rotations")
    assert "Awaiting a complete dated set" in weekly.fields[1].value
    assert "current named pool has not been established" in descent.fields[0].value
    assert "complete current East / South / West" in seasonal.fields[2].value

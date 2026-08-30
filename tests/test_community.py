from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.bot.client import RwiBot
from rwi_bot.domain.schemas import AnswerRequest
from rwi_bot.services.community import CommunityLoadoutHit, community_search_text
from rwi_bot.services.qa import QuestionAnsweringService, render_community_loadouts


def loadout_fixture() -> SimpleNamespace:
    now = datetime(2026, 8, 30, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        title="Broken Rain Hazard Anchor",
        content="Six blue cores with hazard protection and armor regeneration.",
        tags=["Tank", "Broken Rain"],
        source_url="https://discord.com/channels/1/2/2",
        game_version="Y8S3 Red Horizon",
        verification_status="community_submitted",
        updated_at=now,
    )


def test_community_search_text_includes_description_tags_and_version() -> None:
    text = community_search_text(
        title="Hazard Anchor",
        content="Armor regeneration tank",
        tags=["Broken Rain", "PvE"],
        game_version="Y8S3 Red Horizon",
    )

    assert "hazard anchor" in text
    assert "armor regeneration tank" in text
    assert "broken rain pve" in text
    assert "y8s3 red horizon" in text


def test_community_answer_is_labeled_and_links_to_the_original_post() -> None:
    hit = CommunityLoadoutHit(loadout=cast(Any, loadout_fixture()), similarity=0.81)

    rendered = render_community_loadouts([hit], game_version="Y8S3 Red Horizon")

    assert "player-submitted builds" in rendered
    assert "Tags:" in rendered
    assert "https://discord.com/channels/1/2/2" in rendered
    assert "Match: 81%" in rendered


@pytest.mark.asyncio
async def test_matching_community_loadout_answers_without_provider_or_cache() -> None:
    hit = CommunityLoadoutHit(loadout=cast(Any, loadout_fixture()), similarity=0.81)
    community = SimpleNamespace(search=AsyncMock(return_value=[hit]))
    cache = SimpleNamespace(get_valid=AsyncMock(), create_candidate=AsyncMock())
    ai = SimpleNamespace(answer=AsyncMock())
    audit = SimpleNamespace(record=AsyncMock())
    service = QuestionAnsweringService(
        maintenance=cast(Any, SimpleNamespace(halted=False)),
        knowledge=cast(Any, SimpleNamespace(search=AsyncMock())),
        cache=cast(Any, cache),
        tickets=cast(Any, SimpleNamespace()),
        profiles=cast(Any, SimpleNamespace(learning_opted_out=AsyncMock(return_value=False))),
        community_loadouts=cast(Any, community),
        ai=cast(Any, ai),
        audit=cast(Any, audit),
        web_search_enabled=True,
        current_game_version="Y8S3 Red Horizon",
    )

    result = await service.answer(
        AnswerRequest(
            user_id=42,
            guild_id=1,
            channel_id=2,
            question="Can you suggest a Broken Rain hazpro tank build?",
        )
    )

    assert "Broken Rain Hazard Anchor" in result.text
    assert result.citations[0].source_type == "community_loadout"
    community.search.assert_awaited_once()
    cache.get_valid.assert_not_awaited()
    cache.create_candidate.assert_not_awaited()
    ai.answer.assert_not_awaited()
    event = audit.record.call_args.args[0]
    assert event.event_type == "answer.community_loadout_match"


@pytest.mark.asyncio
async def test_erin_server_identity_is_idempotent() -> None:
    member = SimpleNamespace(display_name="Old Bot Name", edit=AsyncMock())
    bot_like = SimpleNamespace(log=Mock())

    await RwiBot.ensure_server_identity(cast(Any, bot_like), cast(Any, SimpleNamespace(me=member)))

    member.edit.assert_awaited_once()
    assert member.edit.call_args.kwargs["nick"] == "ERIN"

    member.display_name = "ERIN"
    member.edit.reset_mock()
    await RwiBot.ensure_server_identity(cast(Any, bot_like), cast(Any, SimpleNamespace(me=member)))
    member.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_erin_global_identity_is_idempotent_for_dm_display() -> None:
    user = SimpleNamespace(name="RWI Bot Dev", edit=AsyncMock())
    bot_like = SimpleNamespace(user=user, log=Mock(), _global_identity_complete=False)

    await RwiBot.ensure_global_identity(cast(Any, bot_like))

    user.edit.assert_awaited_once_with(username="ERIN")
    assert bot_like._global_identity_complete is True

    user.edit.reset_mock()
    await RwiBot.ensure_global_identity(cast(Any, bot_like))
    user.edit.assert_not_awaited()

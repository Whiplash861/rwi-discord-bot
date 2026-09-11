from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from rwi_bot.bot import names
from rwi_bot.cogs.conversation import ConversationCog
from rwi_bot.cogs.moderation import ModerationCog
from rwi_bot.cogs.observation import KnowledgeObservationCog
from rwi_bot.cogs.operations import OperationsCog
from rwi_bot.services.experience import (
    demonstrates_experience,
    endorsement_target,
    observation_fingerprint,
    self_reported_labels,
)
from rwi_bot.services.observation import KnowledgeAssessment


@pytest.mark.parametrize(
    "text,expected",
    [
        ("<@123> is experienced", (123, "Experienced player")),
        ("<@!123> is a great raid leader.", (123, "Raid leader")),
        ("<@123> is PvP-focused", (123, "PvP-focused")),
        ("Is <@123> experienced?", None),
        ("<@123> is experienced?", None),
        ("<@123> is not experienced", None),
        ("<@123> is an experienced doctor", None),
        ("<@123> is experienced, <@456> isn't", None),
        ("Someone said <@123> is experienced", None),
    ],
)
def test_endorsements_require_affirmative_unambiguous_target(text, expected):
    assert endorsement_target(text) == expected


def test_labels_are_specific_self_reports_not_expertise_inferences():
    assert self_reported_labels("I'm a healer main. I am a raid leader.") == (
        "Raid leader",
        "Healer main",
    )
    assert self_reported_labels("I'm PvP-focused") == ("PvP-focused",)
    assert not self_reported_labels("I'm not a raid leader")
    assert not self_reported_labels("The raid leader opens the door with this mechanic.")
    assert not self_reported_labels("He says I am a raid leader.")
    assert not self_reported_labels("I am a raid leader if we need one")


def test_experience_needs_distinct_current_corroborated_advice_across_days():
    now = datetime.now(UTC)
    rows = [
        SimpleNamespace(
            status="corroborated",
            provenance="observed_advice",
            game_version="current",
            created_at=now - timedelta(days=i // 2),
            fingerprint=observation_fingerprint(f"distinct advice {i}"),
        )
        for i in range(5)
    ]
    assert demonstrates_experience(rows, game_version="current")
    assert not demonstrates_experience(rows[:4], game_version="current")
    assert not demonstrates_experience(rows, game_version="next-season")
    assert not demonstrates_experience([rows[0]] * 8, game_version="current")
    rows[-1].status = "unresolved"
    assert not demonstrates_experience(rows, game_version="current")
    rows[-1].status = "corroborated"
    rows[-1].created_at = now - timedelta(days=91)
    assert not demonstrates_experience(rows, game_version="current")


@pytest.mark.parametrize("name", ["general", "general-chat", "general-pvp", "general_chat"])
@pytest.mark.asyncio
async def test_general_chat_never_answers_schedules_or_moderates(name):
    channel = SimpleNamespace(name=name, send=AsyncMock(), parent=None)
    message = SimpleNamespace(
        channel=channel,
        author=SimpleNamespace(bot=False),
        content="ERIN schedule a raid and help me",
        attachments=[],
    )
    bot = SimpleNamespace(services=SimpleNamespace())
    # Instantiate only the message handlers: guards must run before other dependencies.
    conversation = object.__new__(ConversationCog)
    conversation.bot = bot
    await conversation.on_message(message)
    assert not await OperationsCog.maybe_handle_message(object.__new__(OperationsCog), message)
    assert not await ModerationCog.handle_message(object.__new__(ModerationCog), message)
    channel.send.assert_not_awaited()
    assert names.is_passive_general(SimpleNamespace(name="thread", parent=channel))
    assert not names.is_passive_general(SimpleNamespace(name="ask-rwi", parent=None))


@pytest.mark.asyncio
async def test_passive_advice_is_checked_stored_and_never_replied_to(tmp_path, monkeypatch):
    repository = SimpleNamespace(
        record=AsyncMock(return_value="observation-id"),
        finish=AsyncMock(),
        withdraw_message=AsyncMock(),
    )
    assessment = KnowledgeAssessment(
        verdict="corroborated", summary="Game-only conditions confirmed."
    )
    checker = SimpleNamespace(check=AsyncMock(return_value=assessment))
    monkeypatch.setattr("rwi_bot.cogs.observation.ExperienceRepository", lambda _: repository)
    monkeypatch.setattr("rwi_bot.cogs.observation.KnowledgeVerifier", lambda *_: checker)
    services = SimpleNamespace(
        database=None,
        ai=None,
        knowledge=None,
        profiles=SimpleNamespace(learning_opted_out=AsyncMock(return_value=False)),
        maintenance=SimpleNamespace(halted=False),
        settings=SimpleNamespace(runtime_dir=tmp_path, autonomous_research_enabled=True),
        qa=SimpleNamespace(
            current_game_version="Red Horizon",
            current_game_version_started_on=datetime.now(UTC).date(),
        ),
    )
    cog = KnowledgeObservationCog(SimpleNamespace(services=services))
    message = SimpleNamespace(
        content="You can use the linked laser to pulse targets with Technician.",
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=2),
        id=3,
        webhook_id=None,
        reference=None,
        reply=AsyncMock(),
        channel=SimpleNamespace(send=AsyncMock()),
    )
    await cog.observe_general(message)
    checker.check.assert_awaited_once()
    repository.finish.assert_awaited_once()
    message.reply.assert_not_awaited()
    message.channel.send.assert_not_awaited()
    services.profiles.learning_opted_out.return_value = True
    repository.record.reset_mock()
    await cog.observe_general(message)
    repository.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_daily_observation_budget_does_not_search_or_speak(tmp_path, monkeypatch):
    repository = SimpleNamespace(record=AsyncMock(return_value=None))
    verifier = Mock()
    monkeypatch.setattr("rwi_bot.cogs.observation.ExperienceRepository", lambda _: repository)
    monkeypatch.setattr("rwi_bot.cogs.observation.KnowledgeVerifier", verifier)
    services = SimpleNamespace(
        database=None,
        profiles=SimpleNamespace(learning_opted_out=AsyncMock(return_value=False)),
        maintenance=SimpleNamespace(halted=False),
        settings=SimpleNamespace(runtime_dir=tmp_path, autonomous_research_enabled=True),
        qa=SimpleNamespace(current_game_version="Red Horizon"),
    )
    cog = KnowledgeObservationCog(SimpleNamespace(services=services))
    message = SimpleNamespace(
        content="The linked laser allows you to pulse targets with Technician.",
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=2),
        id=3,
        webhook_id=None,
        reference=None,
        reply=AsyncMock(),
    )
    await cog.observe_general(message)
    verifier.assert_not_called()
    message.reply.assert_not_awaited()

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import discord
import pytest

from rwi_bot.bot import names
from rwi_bot.cogs.moderation import ModerationCog
from rwi_bot.services.moderation import SpamAction, SpamDetector, choose_spam_action


def moderation_bot(*, halted: bool = False) -> SimpleNamespace:
    settings = SimpleNamespace(
        discord_guild_id=1,
        owner_user_id=999,
        spam_detection_enabled=True,
        spam_repeated_messages=2,
        spam_burst_messages=4,
        spam_severe_messages=6,
        spam_window_seconds=10,
        spam_incident_cooldown_seconds=4,
        spam_history_hours=24,
        spam_timeout_minutes=10,
    )
    services = SimpleNamespace(
        settings=settings,
        maintenance=SimpleNamespace(halted=halted),
        discipline=SimpleNamespace(
            recent_count=AsyncMock(return_value=0),
            append=AsyncMock(return_value=uuid4()),
        ),
        audit=SimpleNamespace(record=AsyncMock(return_value=uuid4())),
    )
    return SimpleNamespace(services=services, user=SimpleNamespace(id=10))


def test_repeated_messages_trigger_without_retaining_content() -> None:
    detector = SpamDetector(
        repeated_messages=3,
        burst_messages=7,
        severe_messages=12,
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)

    assert not detector.inspect(guild_id=1, user_id=2, content="same", now=now).detected
    assert not detector.inspect(
        guild_id=1,
        user_id=2,
        content=" SAME ",
        now=now + timedelta(seconds=1),
    ).detected
    signal = detector.inspect(
        guild_id=1,
        user_id=2,
        content="same",
        now=now + timedelta(seconds=2),
    )

    assert signal.detected
    assert signal.reasons == ("repeated_message",)
    assert signal.repeated_messages == 3
    assert all(not hasattr(event, "content") for event in detector._events[(1, 2)])


def test_unique_message_burst_is_detected() -> None:
    detector = SpamDetector(
        repeated_messages=3,
        burst_messages=4,
        severe_messages=6,
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)

    signals = [
        detector.inspect(
            guild_id=1,
            user_id=2,
            content=f"message {index}",
            now=now + timedelta(milliseconds=index * 100),
        )
        for index in range(4)
    ]

    assert not any(signal.detected for signal in signals[:3])
    assert signals[3].detected
    assert signals[3].reasons == ("message_burst",)


def test_incident_cooldown_prevents_immediate_multi_step_escalation() -> None:
    detector = SpamDetector(
        repeated_messages=2,
        burst_messages=4,
        severe_messages=6,
        incident_cooldown=timedelta(seconds=5),
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)

    detector.inspect(guild_id=1, user_id=2, content="same", now=now)
    first = detector.inspect(
        guild_id=1,
        user_id=2,
        content="same",
        now=now + timedelta(seconds=1),
    )
    cooling_down = detector.inspect(
        guild_id=1,
        user_id=2,
        content="same",
        now=now + timedelta(seconds=2),
    )

    assert first.detected
    assert not cooling_down.detected


def test_spam_policy_never_selects_a_ban() -> None:
    assert choose_spam_action(0, severe=False) is SpamAction.WARNING
    assert choose_spam_action(1, severe=False) is SpamAction.TIMEOUT
    assert choose_spam_action(2, severe=False) is SpamAction.KICK
    assert choose_spam_action(0, severe=True) is SpamAction.TIMEOUT
    assert choose_spam_action(1, severe=True) is SpamAction.KICK
    assert "ban" not in {action.value for action in SpamAction}


@pytest.mark.asyncio
async def test_maintenance_halt_disables_moderation() -> None:
    bot = moderation_bot(halted=True)
    cog = ModerationCog(bot)  # type: ignore[arg-type]
    message = Mock(spec=discord.Message)

    assert not await cog.handle_message(message)
    bot.services.discipline.recent_count.assert_not_awaited()


@pytest.mark.asyncio
async def test_detected_spam_is_deleted_warned_and_safely_recorded() -> None:
    bot = moderation_bot()
    cog = ModerationCog(bot)  # type: ignore[arg-type]
    cog._is_protected = Mock(return_value=False)  # type: ignore[method-assign]
    guild = Mock(spec=discord.Guild)
    guild.id = 1
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.mention = "<@2>"
    channel = Mock(spec=discord.TextChannel)
    channel.id = 3
    channel.send = AsyncMock()

    def message(message_id: int) -> Mock:
        item = Mock(spec=discord.Message)
        item.id = message_id
        item.guild = guild
        item.author = member
        item.channel = channel
        item.content = "same private text"
        item.attachments = []
        item.webhook_id = None
        item.delete = AsyncMock()
        return item

    first = message(4)
    second = message(5)

    assert not await cog.handle_message(first)
    assert await cog.handle_message(second)
    second.delete.assert_awaited_once_with()
    channel.send.assert_awaited_once()
    append = bot.services.discipline.append.await_args.kwargs
    assert append["action"] == SpamAction.WARNING.value
    assert "same private text" not in repr(append["evidence"])
    assert "content" not in append["evidence"]


def test_owner_and_protected_roles_are_exempt_from_automation() -> None:
    bot = moderation_bot()
    cog = ModerationCog(bot)  # type: ignore[arg-type]
    guild = SimpleNamespace(owner_id=123, me=None)
    owner = SimpleNamespace(id=999, guild=guild, roles=[])
    technician = SimpleNamespace(
        id=5,
        guild=guild,
        roles=[SimpleNamespace(name=names.TECHNICIAN)],
    )

    assert cog._is_protected(owner)  # type: ignore[arg-type]
    assert cog._is_protected(technician)  # type: ignore[arg-type]

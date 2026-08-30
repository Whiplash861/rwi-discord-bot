from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from rwi_bot.bot import names
from rwi_bot.bot.views import PlatformButton, PlatformRoleView


def interaction_for(
    *,
    guild_id: int = 1,
    member_roles: list[discord.Role] | None = None,
) -> tuple[Mock, Mock, Mock]:
    guild = Mock(spec=discord.Guild)
    guild.id = guild_id
    guild.roles = []
    member = Mock(spec=discord.Member)
    member.id = 2
    member.roles = member_roles or []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    interaction = Mock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = member
    interaction.response = SimpleNamespace(send_message=AsyncMock())
    return interaction, guild, member


def platform_button(*, halted: bool = False) -> PlatformButton:
    return PlatformButton(
        names.XBOX,
        "🎮",
        discord.ButtonStyle.success,
        guild_id=1,
        halted=lambda: halted,
    )


@pytest.mark.asyncio
async def test_platform_button_adds_role_without_openai_or_public_reply() -> None:
    role = Mock(spec=discord.Role)
    role.name = names.XBOX
    interaction, guild, member = interaction_for()
    guild.roles = [role]

    await platform_button().callback(interaction)

    member.add_roles.assert_awaited_once_with(role, reason="Member platform-role toggle")
    member.remove_roles.assert_not_awaited()
    response = interaction.response.send_message.await_args
    assert response.kwargs["ephemeral"] is True
    assert "more than one platform" in response.args[0]


@pytest.mark.asyncio
async def test_platform_button_removes_only_the_selected_role() -> None:
    xbox = Mock(spec=discord.Role)
    xbox.name = names.XBOX
    pc = Mock(spec=discord.Role)
    pc.name = names.PC
    interaction, guild, member = interaction_for(member_roles=[xbox, pc])
    guild.roles = [xbox, pc]

    await platform_button().callback(interaction)

    member.remove_roles.assert_awaited_once_with(xbox, reason="Member platform-role toggle")
    assert pc in member.roles


@pytest.mark.asyncio
async def test_platform_button_stops_during_maintenance() -> None:
    interaction, _, member = interaction_for()

    await platform_button(halted=True).callback(interaction)

    member.add_roles.assert_not_awaited()
    assert "maintenance mode" in interaction.response.send_message.await_args.args[0]
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_rogue_agent_cannot_change_platform_roles() -> None:
    rogue = Mock(spec=discord.Role)
    rogue.name = names.ROGUE_AGENT
    interaction, _, member = interaction_for(member_roles=[rogue])

    await platform_button().callback(interaction)

    member.add_roles.assert_not_awaited()
    assert "Rogue Agent" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_platform_selector_rejects_another_guild() -> None:
    interaction, _, member = interaction_for(guild_id=99)

    await platform_button().callback(interaction)

    member.add_roles.assert_not_awaited()
    assert "belongs to" in interaction.response.send_message.await_args.args[0]


def test_persistent_platform_view_has_stable_independent_buttons() -> None:
    view = PlatformRoleView(guild_id=1, halted=lambda: False)

    custom_ids = {item.custom_id for item in view.children}
    assert custom_ids == {
        "rwi:platform:xbox",
        "rwi:platform:pc",
        "rwi:platform:ps",
    }

from __future__ import annotations

import discord
from discord import app_commands

from rwi_bot.bot.names import DIVISION_COMMANDER, TECHNICIAN


def has_role(member: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in member.roles)


def is_owner_or_technician(member: discord.Member, owner_user_id: int) -> bool:
    return member.id == owner_user_id or has_role(member, TECHNICIAN)


def is_commander(member: discord.Member, owner_user_id: int) -> bool:
    return (
        member.id == owner_user_id
        or has_role(member, DIVISION_COMMANDER)
        or member.guild_permissions.administrator
    )


def owner_or_technician_check(owner_user_id: int) -> app_commands.Check:
    async def predicate(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_owner_or_technician(
            interaction.user, owner_user_id
        )

    return app_commands.check(predicate)


def commander_check(owner_user_id: int) -> app_commands.Check:
    async def predicate(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_commander(
            interaction.user, owner_user_id
        )

    return app_commands.check(predicate)

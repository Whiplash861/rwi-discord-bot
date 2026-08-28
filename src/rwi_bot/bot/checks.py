from __future__ import annotations

import discord

from rwi_bot.bot.names import DIVISION_COMMANDER, TECHNICIAN


def has_role(member: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in member.roles)


def is_maintenance_operator(member: discord.Member, owner_user_id: int) -> bool:
    return (
        member.id == owner_user_id
        or has_role(member, DIVISION_COMMANDER)
        or has_role(member, TECHNICIAN)
    )


def is_commander(member: discord.Member, owner_user_id: int) -> bool:
    return member.id == owner_user_id or has_role(member, DIVISION_COMMANDER)

from __future__ import annotations

import discord

from rwi_bot.bot.server_blueprint import ROLE_SPECS, ServerReconciler


def role_permissions(name: str) -> discord.Permissions:
    return next(spec.permissions for spec in ROLE_SPECS if spec.name == name)


def test_commander_administrator_permission_requires_manual_owner_action() -> None:
    bot_permissions = discord.Permissions(
        manage_roles=True,
        manage_channels=True,
        manage_messages=True,
        manage_threads=True,
        moderate_members=True,
        kick_members=True,
    )

    grantable, missing = ServerReconciler._grantable_permissions(
        role_permissions("Division Commander"),
        bot_permissions,
    )

    assert grantable == discord.Permissions.none()
    assert missing == ("administrator",)


def test_coordinator_receives_only_permissions_the_bot_can_grant() -> None:
    bot_permissions = discord.Permissions(
        kick_members=True,
        moderate_members=True,
        manage_messages=True,
        manage_threads=True,
    )

    grantable, missing = ServerReconciler._grantable_permissions(
        role_permissions("Division Coordinator"),
        bot_permissions,
    )

    assert grantable.kick_members
    assert grantable.moderate_members
    assert grantable.manage_messages
    assert grantable.manage_threads
    assert not grantable.manage_nicknames
    assert not grantable.view_audit_log
    assert missing == ("manage_nicknames", "view_audit_log")

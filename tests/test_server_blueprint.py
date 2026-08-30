from __future__ import annotations

from unittest.mock import Mock

import discord

from rwi_bot.bot.server_blueprint import ROLE_SPECS, ChannelKind, ChannelSpec, ServerReconciler


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


def test_new_private_category_keeps_bot_bootstrap_access() -> None:
    default_role = Mock(spec=discord.Role)
    bot_member = Mock(spec=discord.Member)
    guild = Mock(spec=discord.Guild)
    guild.default_role = default_role

    overwrites = ServerReconciler(guild)._new_category_overwrites(bot_member)

    assert overwrites[default_role].view_channel is False
    assert overwrites[bot_member].view_channel is True
    assert overwrites[bot_member].manage_channels is True


def test_bot_inaccessible_channel_is_not_editable() -> None:
    channel = Mock(spec=discord.TextChannel)
    bot_member = Mock(spec=discord.Member)
    channel.permissions_for.return_value = discord.Permissions.none()

    assert not ServerReconciler._channel_is_editable(channel, bot_member)


def test_unchanged_text_channel_does_not_need_update() -> None:
    role = Mock(spec=discord.Role)
    role.id = 1
    overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=False)
    channel = Mock(spec=discord.TextChannel)
    channel.overwrites = {role: overwrite}
    channel.topic = "Canonical topic"
    channel.nsfw = False
    spec = ChannelSpec("canonical", ChannelKind.TEXT, "Canonical topic")

    assert not ServerReconciler._channel_needs_update(channel, spec, {role: overwrite})

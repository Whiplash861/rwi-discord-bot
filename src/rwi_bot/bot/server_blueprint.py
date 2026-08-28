from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

import discord
import structlog

from rwi_bot.bot import names


class ChannelKind(StrEnum):
    TEXT = "text"
    FORUM = "forum"
    VOICE = "voice"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    name: str
    permissions: discord.Permissions = field(default_factory=discord.Permissions.none)
    colour: discord.Colour = field(default_factory=discord.Colour.default)
    hoist: bool = False
    mentionable: bool = False


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    name: str
    kind: ChannelKind
    topic: str | None = None
    nsfw: bool = False
    access_roles: tuple[str, ...] = ()
    bot_access: bool = False


ROLE_SPECS = (
    RoleSpec(
        names.DIVISION_COMMANDER,
        discord.Permissions(administrator=True),
        discord.Colour.from_rgb(214, 92, 26),
        hoist=True,
    ),
    RoleSpec(
        names.DIVISION_COORDINATOR,
        discord.Permissions(
            view_audit_log=True,
            kick_members=True,
            moderate_members=True,
            manage_messages=True,
            manage_threads=True,
            manage_nicknames=True,
        ),
        discord.Colour.from_rgb(232, 139, 45),
        hoist=True,
    ),
    RoleSpec(
        names.TECHNICIAN,
        colour=discord.Colour.from_rgb(245, 184, 64),
        hoist=True,
    ),
    RoleSpec(names.AGENT, colour=discord.Colour.from_rgb(192, 192, 192)),
    RoleSpec(names.XBOX, colour=discord.Colour.from_rgb(16, 124, 16)),
    RoleSpec(names.PC, colour=discord.Colour.from_rgb(92, 107, 130)),
    RoleSpec(names.PS, colour=discord.Colour.from_rgb(0, 112, 209)),
    RoleSpec(names.ROGUE_AGENT, colour=discord.Colour.from_rgb(145, 24, 24)),
)


CATEGORY_CHANNELS: dict[str, tuple[ChannelSpec, ...]] = {
    names.START_HERE: (
        ChannelSpec(
            names.WELCOME,
            ChannelKind.TEXT,
            "Welcome to The Redwing Initiative. Choose your platform roles here.",
            bot_access=True,
        ),
    ),
    names.ALLIANCE_HUB: (
        ChannelSpec(
            names.GENERAL_CHAT,
            ChannelKind.TEXT,
            "Alliance conversation. Images, links, video, and files are welcome.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.ASK_RWI,
            ChannelKind.TEXT,
            "Ask RWI anything about The Division 2. The bot answers here and in member DMs.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.COMMUNITY_BUILDS,
            ChannelKind.FORUM,
            "Submit, discuss, validate, and improve community builds.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.GALLERY,
            ChannelKind.FORUM,
            "Share general-audience screenshots, artwork, and clips.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.NSFW_CHAT,
            ChannelKind.TEXT,
            "Age-restricted member conversation. RWI does not learn from this channel.",
            nsfw=True,
            access_roles=(names.AGENT,),
        ),
    ),
    names.MATCHMAKING: (
        ChannelSpec(
            names.XBOX_MATCHMAKING,
            ChannelKind.FORUM,
            "Xbox looking-for-group posts until crossplay is live.",
            access_roles=(names.AGENT, names.XBOX, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.PC_MATCHMAKING,
            ChannelKind.FORUM,
            "PC looking-for-group posts until crossplay is live.",
            access_roles=(names.AGENT, names.PC, names.ROGUE_AGENT),
            bot_access=True,
        ),
        ChannelSpec(
            names.PS_MATCHMAKING,
            ChannelKind.FORUM,
            "PlayStation looking-for-group posts until crossplay is live.",
            access_roles=(names.AGENT, names.PS, names.ROGUE_AGENT),
            bot_access=True,
        ),
    ),
    names.ADMINISTRATION: (
        ChannelSpec(
            names.COUNCIL,
            ChannelKind.TEXT,
            "Private Division Commander and Division Coordinator meeting space.",
            access_roles=(names.DIVISION_COMMANDER, names.DIVISION_COORDINATOR),
        ),
        ChannelSpec(
            names.COUNCIL_VOICE,
            ChannelKind.VOICE,
            access_roles=(names.DIVISION_COMMANDER, names.DIVISION_COORDINATOR),
        ),
        ChannelSpec(
            names.ANNOTATIONS,
            ChannelKind.FORUM,
            "Private versioned server and member notes.",
            access_roles=(names.DIVISION_COMMANDER, names.DIVISION_COORDINATOR),
        ),
        ChannelSpec(
            names.DISCIPLINARY_LOG,
            ChannelKind.FORUM,
            "Private disciplinary records about members; never a public punishment board.",
            access_roles=(names.DIVISION_COMMANDER, names.DIVISION_COORDINATOR),
            bot_access=True,
        ),
        ChannelSpec(
            names.WORKSHOP,
            ChannelKind.TEXT,
            "Technician conversation and coordination, separate from production debugging.",
            access_roles=(names.DIVISION_COMMANDER, names.TECHNICIAN),
        ),
        ChannelSpec(
            names.TECHNICIAN_LAB,
            ChannelKind.TEXT,
            "RWI production, debugging, tests, knowledge changes, and unresolved tickets.",
            access_roles=(names.DIVISION_COMMANDER, names.TECHNICIAN),
            bot_access=True,
        ),
        ChannelSpec(
            names.BOT_OPS,
            ChannelKind.TEXT,
            "Commander and bot-only security, cost, failure, halt, and kick records.",
            access_roles=(names.DIVISION_COMMANDER,),
            bot_access=True,
        ),
    ),
}


@dataclass(slots=True)
class ReconcileReport:
    created_roles: list[str] = field(default_factory=list)
    created_categories: list[str] = field(default_factory=list)
    created_channels: list[str] = field(default_factory=list)
    updated_channels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ServerReconciler:
    """Idempotently creates only the canonical RWI roles and spaces."""

    def __init__(self, guild: discord.Guild) -> None:
        self.guild = guild
        self.log = structlog.get_logger("server_blueprint")

    async def reconcile(self) -> ReconcileReport:
        report = ReconcileReport()
        roles = await self._ensure_roles(report)
        bot_member = self.guild.me
        if bot_member is None:
            raise RuntimeError("The bot member is not available in the target guild.")

        for category_name, channel_specs in CATEGORY_CHANNELS.items():
            category = discord.utils.get(self.guild.categories, name=category_name)
            if category is None:
                category = await self.guild.create_category(
                    category_name,
                    overwrites={
                        self.guild.default_role: discord.PermissionOverwrite(view_channel=False)
                    },
                    reason="RWI canonical server bootstrap",
                )
                report.created_categories.append(category_name)

            for spec in channel_specs:
                overwrites = self._channel_overwrites(spec, roles, bot_member)
                channel: discord.abc.GuildChannel | None = discord.utils.get(
                    category.channels, name=spec.name
                )
                if channel is None:
                    channel = await self._create_channel(category, spec, overwrites)
                    report.created_channels.append(f"{category_name}/{spec.name}")
                elif isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    await channel.edit(
                        overwrites=overwrites,
                        topic=spec.topic or "",
                        nsfw=spec.nsfw,
                        reason="Reconcile canonical RWI permissions",
                    )
                    report.updated_channels.append(f"{category_name}/{spec.name}")
                elif isinstance(channel, discord.VoiceChannel):
                    await channel.edit(
                        overwrites=overwrites,
                        reason="Reconcile canonical RWI permissions",
                    )
                    report.updated_channels.append(f"{category_name}/{spec.name}")
                else:
                    report.warnings.append(
                        f"{category_name}/{spec.name} exists with an incompatible channel type."
                    )

        rogue = roles[names.ROGUE_AGENT]
        custom_roles = [role for role in self.guild.roles if not role.is_default()]
        if custom_roles and rogue.position != min(role.position for role in custom_roles):
            report.warnings.append(
                "Move Rogue Agent to the lowest custom-role position; Discord's @everyone "
                "role always remains beneath it."
            )
        if roles[names.TECHNICIAN].position < bot_member.top_role.position:
            report.warnings.append(
                "Move Division Commander, Division Coordinator, and Technician above the "
                "RWI Bot role after bootstrap. Discord does not allow a bot to move roles "
                "above its own managed role."
            )
        return report

    async def _ensure_roles(self, report: ReconcileReport) -> dict[str, discord.Role]:
        roles: dict[str, discord.Role] = {}
        for spec in ROLE_SPECS:
            role = discord.utils.get(self.guild.roles, name=spec.name)
            if role is None:
                role = await self.guild.create_role(
                    name=spec.name,
                    permissions=spec.permissions,
                    colour=spec.colour,
                    hoist=spec.hoist,
                    mentionable=spec.mentionable,
                    reason="RWI canonical server bootstrap",
                )
                report.created_roles.append(spec.name)
            else:
                await role.edit(
                    permissions=spec.permissions,
                    colour=spec.colour,
                    hoist=spec.hoist,
                    mentionable=spec.mentionable,
                    reason="Reconcile canonical RWI role configuration",
                )
            roles[spec.name] = role
        return roles

    def _channel_overwrites(
        self,
        spec: ChannelSpec,
        roles: dict[str, discord.Role],
        bot_member: discord.Member,
    ) -> Mapping[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]:
        overwrites: dict[
            discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite
        ] = {self.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        if spec.name == names.WELCOME:
            overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
            )
        for role_name in spec.access_roles:
            role = roles[role_name]
            overwrite = discord.PermissionOverwrite(view_channel=True, read_message_history=True)
            if role_name == names.ROGUE_AGENT:
                overwrite.update(
                    send_messages=False,
                    add_reactions=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    send_messages_in_threads=False,
                    speak=False,
                    stream=False,
                    use_application_commands=False,
                )
            overwrites[role] = overwrite
        if spec.bot_access:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_threads=True,
                create_public_threads=True,
                send_messages_in_threads=True,
            )
        return overwrites

    async def _create_channel(
        self,
        category: discord.CategoryChannel,
        spec: ChannelSpec,
        overwrites: Mapping[
            discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite
        ],
    ) -> discord.abc.GuildChannel:
        reason = "RWI canonical server bootstrap"
        if spec.kind == ChannelKind.TEXT:
            return await category.create_text_channel(
                spec.name,
                topic=spec.topic or "",
                nsfw=spec.nsfw,
                overwrites=overwrites,
                reason=reason,
            )
        if spec.kind == ChannelKind.VOICE:
            return await category.create_voice_channel(
                spec.name,
                overwrites=overwrites,
                reason=reason,
            )
        try:
            return await category.create_forum(
                spec.name,
                topic=spec.topic or "",
                nsfw=spec.nsfw,
                overwrites=overwrites,
                reason=reason,
            )
        except discord.HTTPException:
            self.log.warning("forum_fallback_to_text", channel=spec.name)
            return await category.create_text_channel(
                spec.name,
                topic=f"[Forum fallback] {spec.topic or ''}".strip(),
                nsfw=spec.nsfw,
                overwrites=overwrites,
                reason=reason,
            )

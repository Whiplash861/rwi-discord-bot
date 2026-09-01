from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

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
    read_only: bool = False


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
    RoleSpec(
        names.RAID_INCURSION_MATCHMAKING,
        colour=discord.Colour.from_rgb(229, 111, 35),
        mentionable=True,
    ),
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
            names.ERIN_PATCH_NOTES,
            ChannelKind.TEXT,
            "Read-only release history for ERIN features, fixes, safety changes, and operations.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
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
            "Ask ERIN anything about The Division 2. The bot answers here and in member DMs.",
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
            names.SCHEDULED_OPERATIONS,
            ChannelKind.TEXT,
            "Read-only Raid and Incursion schedule, RSVP roster, and attendance reminders.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
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
    names.ROTATIONS: (
        ChannelSpec(
            names.DAILY_TARGETED_LOOT,
            ChannelKind.TEXT,
            "Read-only daily DC, New York, Brooklyn, and Escalation targeted-loot updates.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
        ChannelSpec(
            names.WEEKLY_MISSION_ROTATIONS,
            ChannelKind.TEXT,
            "Read-only Escalation, Invasion, Legendary project, and Classified rotations.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
        ChannelSpec(
            names.DESCENT_ROTATION,
            ChannelKind.TEXT,
            "Read-only current Descent talent pool and three-day reset timing.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
        ChannelSpec(
            names.SEASONAL_ROTATIONS,
            ChannelKind.TEXT,
            "Read-only active and upcoming seasonal, Manhunt, event, and Dark Zone rotations.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
        ),
        ChannelSpec(
            names.RESET_TIMERS,
            ChannelKind.TEXT,
            "Read-only local-time reset index for daily, weekly, vendor, Raid, and Descent cycles.",
            access_roles=(names.AGENT, names.ROGUE_AGENT),
            bot_access=True,
            read_only=True,
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
        bot_member = self.guild.me
        if bot_member is None:
            raise RuntimeError("The bot member is not available in the target guild.")
        roles = await self._ensure_roles(report, bot_member)
        known_channels = [
            cast(discord.abc.GuildChannel, channel) for channel in await self.guild.fetch_channels()
        ]

        for category_name, channel_specs in CATEGORY_CHANNELS.items():
            category = next(
                (
                    channel
                    for channel in known_channels
                    if isinstance(channel, discord.CategoryChannel)
                    and channel.name == category_name
                ),
                None,
            )
            if category is None:
                category = await self.guild.create_category(
                    category_name,
                    overwrites=self._new_category_overwrites(bot_member),
                    reason="RWI canonical server bootstrap",
                )
                known_channels.append(category)
                report.created_categories.append(category_name)
            else:
                await self._ensure_category_overwrites(category, bot_member)

            for spec in channel_specs:
                overwrites = self._channel_overwrites(spec, roles, bot_member)
                channel: discord.abc.GuildChannel | None = next(
                    (
                        candidate
                        for candidate in known_channels
                        if getattr(candidate, "category_id", None) == category.id
                        and candidate.name == spec.name
                    ),
                    None,
                )
                if channel is None:
                    channel = await self._create_channel(category, spec, overwrites)
                    known_channels.append(channel)
                    report.created_channels.append(f"{category_name}/{spec.name}")
                elif not self._channel_is_editable(channel, bot_member):
                    if spec.bot_access:
                        report.warnings.append(
                            f"{category_name}/{spec.name} should be bot-managed, but RWI Bot "
                            "cannot currently view and manage it."
                        )
                elif not self._channel_needs_update(channel, spec, overwrites):
                    continue
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

    async def ensure_channel(
        self,
        category_name: str,
        spec: ChannelSpec,
    ) -> discord.abc.GuildChannel:
        """Reconcile one explicitly requested channel without touching roles or peers."""

        bot_member = self.guild.me
        if bot_member is None:
            raise RuntimeError("The bot member is not available in the target guild.")
        category = discord.utils.get(self.guild.categories, name=category_name)
        if category is None:
            fetched = await self.guild.fetch_channels()
            category = next(
                (
                    channel
                    for channel in fetched
                    if isinstance(channel, discord.CategoryChannel)
                    and channel.name == category_name
                ),
                None,
            )
        if category is None:
            if category_name not in CATEGORY_CHANNELS:
                raise RuntimeError(f"The {category_name} category does not exist.")
            category = await self.guild.create_category(
                category_name,
                overwrites=self._new_category_overwrites(bot_member),
                reason="Reconcile an explicitly requested RWI category",
            )
        else:
            await self._ensure_category_overwrites(category, bot_member)
        roles: dict[str, discord.Role] = {}
        for role_name in spec.access_roles:
            role = discord.utils.get(self.guild.roles, name=role_name)
            if role is None:
                raise RuntimeError(f"The {role_name} role does not exist.")
            roles[role_name] = role

        overwrites = self._channel_overwrites(spec, roles, bot_member)
        channel = discord.utils.get(category.channels, name=spec.name)
        if channel is None:
            return await self._create_channel(category, spec, overwrites)
        if spec.kind == ChannelKind.TEXT and not isinstance(channel, discord.TextChannel):
            raise RuntimeError(f"{category_name}/{spec.name} is not a text channel.")
        if not self._channel_is_editable(channel, bot_member):
            raise PermissionError(f"ERIN cannot manage {category_name}/{spec.name}.")
        if self._channel_needs_update(channel, spec, overwrites):
            if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                raise RuntimeError(f"{category_name}/{spec.name} has an incompatible type.")
            await channel.edit(
                overwrites=overwrites,
                topic=spec.topic or "",
                nsfw=spec.nsfw,
                reason="Reconcile an explicitly requested ERIN-managed channel",
            )
        return channel

    async def ensure_role(self, role_name: str) -> discord.Role:
        """Reconcile one canonical role without touching other server structure."""

        spec = next((item for item in ROLE_SPECS if item.name == role_name), None)
        if spec is None:
            raise ValueError(f"{role_name} is not a canonical RWI role.")
        bot_member = self.guild.me
        if bot_member is None:
            raise RuntimeError("The bot member is not available in the target guild.")
        role = discord.utils.get(self.guild.roles, name=spec.name)
        if role is not None and role.position >= bot_member.top_role.position:
            return role
        permissions, _ = self._grantable_permissions(
            spec.permissions,
            bot_member.guild_permissions,
        )
        if role is None:
            return await self.guild.create_role(
                name=spec.name,
                permissions=permissions,
                colour=spec.colour,
                hoist=spec.hoist,
                mentionable=spec.mentionable,
                reason="Reconcile an explicitly requested RWI role",
            )
        await role.edit(
            permissions=permissions,
            colour=spec.colour,
            hoist=spec.hoist,
            mentionable=spec.mentionable,
            reason="Reconcile an explicitly requested RWI role",
        )
        return role

    async def _ensure_roles(
        self,
        report: ReconcileReport,
        bot_member: discord.Member,
    ) -> dict[str, discord.Role]:
        roles: dict[str, discord.Role] = {}
        for spec in ROLE_SPECS:
            role = discord.utils.get(self.guild.roles, name=spec.name)
            if role is not None and role.position >= bot_member.top_role.position:
                report.warnings.append(
                    f"{spec.name} is at or above the RWI Bot role, so its protected "
                    "permissions and display settings were left unchanged."
                )
                roles[spec.name] = role
                continue

            permissions, missing_permissions = self._grantable_permissions(
                spec.permissions,
                bot_member.guild_permissions,
            )
            if missing_permissions:
                readable = ", ".join(
                    permission.replace("_", " ").title() for permission in missing_permissions
                )
                report.warnings.append(
                    f"Enable {readable} manually on {spec.name} after moving that role "
                    "above RWI Bot. The bot intentionally cannot grant permissions it "
                    "does not possess."
                )

            if role is None:
                role = await self.guild.create_role(
                    name=spec.name,
                    permissions=permissions,
                    colour=spec.colour,
                    hoist=spec.hoist,
                    mentionable=spec.mentionable,
                    reason="RWI canonical server bootstrap",
                )
                report.created_roles.append(spec.name)
            else:
                await role.edit(
                    permissions=permissions,
                    colour=spec.colour,
                    hoist=spec.hoist,
                    mentionable=spec.mentionable,
                    reason="Reconcile canonical RWI role configuration",
                )
            roles[spec.name] = role
        return roles

    def _new_category_overwrites(
        self,
        bot_member: discord.Member,
    ) -> dict[
        discord.Role | discord.Member | discord.Object,
        discord.PermissionOverwrite,
    ]:
        return {
            self.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            bot_member: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
        }

    async def _ensure_category_overwrites(
        self,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
    ) -> None:
        default_overwrite = category.overwrites_for(self.guild.default_role)
        if default_overwrite.view_channel is not False:
            default_overwrite.update(view_channel=False)
            await category.set_permissions(
                self.guild.default_role,
                overwrite=default_overwrite,
                reason="Reconcile canonical RWI category privacy",
            )

        bot_overwrite = category.overwrites_for(bot_member)
        if bot_overwrite.view_channel is not True or bot_overwrite.manage_channels is not True:
            bot_overwrite.update(view_channel=True, manage_channels=True)
            await category.set_permissions(
                bot_member,
                overwrite=bot_overwrite,
                reason="Retain RWI bootstrap access to its managed category",
            )

    @staticmethod
    def _channel_is_editable(
        channel: discord.abc.GuildChannel,
        bot_member: discord.Member,
    ) -> bool:
        permissions = channel.permissions_for(bot_member)
        return permissions.view_channel and permissions.manage_channels

    @classmethod
    def _channel_needs_update(
        cls,
        channel: discord.abc.GuildChannel,
        spec: ChannelSpec,
        overwrites: Mapping[
            discord.Role | discord.Member | discord.Object,
            discord.PermissionOverwrite,
        ],
    ) -> bool:
        if cls._overwrite_signature(channel.overwrites) != cls._overwrite_signature(overwrites):
            return True
        if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            return channel.topic != (spec.topic or "") or channel.nsfw != spec.nsfw
        return False

    @staticmethod
    def _overwrite_signature(
        overwrites: Mapping[
            discord.Role | discord.Member | discord.Object,
            discord.PermissionOverwrite,
        ],
    ) -> dict[int, tuple[int, int]]:
        signature: dict[int, tuple[int, int]] = {}
        for target, overwrite in overwrites.items():
            allow, deny = overwrite.pair()
            signature[target.id] = (allow.value, deny.value)
        return signature

    @staticmethod
    def _grantable_permissions(
        desired: discord.Permissions,
        bot_permissions: discord.Permissions,
    ) -> tuple[discord.Permissions, tuple[str, ...]]:
        """Return the desired permissions the bot can safely grant to a role."""

        grantable = discord.Permissions.none()
        missing: list[str] = []
        for name, enabled in desired:
            if not enabled:
                continue
            if getattr(bot_permissions, name):
                setattr(grantable, name, True)
            else:
                missing.append(name)
        return grantable, tuple(sorted(missing))

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
            if spec.read_only or role_name == names.ROGUE_AGENT:
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

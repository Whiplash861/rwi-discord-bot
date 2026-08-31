from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import UUID

import discord
import structlog
from discord.ext import commands, tasks

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import CATEGORY_CHANNELS, ChannelSpec, ServerReconciler
from rwi_bot.db.models import OperationRsvp, OperationRsvpStatus, ScheduledOperation
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.operations import (
    OPERATION_ROLES,
    ParsedOperationRequest,
    is_operation_schedule_request,
    parse_operation_activity,
    parse_operation_request,
    parse_operation_role,
    parse_operation_start,
)

SCHEDULE_PANEL_MARKER = "RWI_OPERATION_ALERT_PANEL_V1"
_DRAFT_LIFETIME = timedelta(minutes=20)
_MINIMUM_NOTICE = timedelta(minutes=5)
_MAXIMUM_NOTICE = timedelta(days=180)


@dataclass(slots=True)
class OperationDraft:
    requester_user_id: int
    source_channel_id: int
    activity: str | None
    activity_type: str | None
    capacity: int | None
    target_date: date | None
    start_at: datetime | None
    organizer_role: str | None
    created_at: datetime

    @classmethod
    def from_request(
        cls,
        request: ParsedOperationRequest,
        *,
        requester_user_id: int,
        source_channel_id: int,
        now: datetime,
    ) -> OperationDraft:
        return cls(
            requester_user_id=requester_user_id,
            source_channel_id=source_channel_id,
            activity=request.activity,
            activity_type=request.activity_type,
            capacity=request.capacity,
            target_date=request.target_date,
            start_at=request.start_at,
            organizer_role=None,
            created_at=now,
        )


class OperationAlertRoleButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, bot: RwiBot) -> None:
        super().__init__(
            label="Toggle Raid & Incursion Alerts",
            emoji="📡",
            style=discord.ButtonStyle.primary,
            custom_id="rwi:operation-alerts:toggle",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "ERIN is in maintenance mode. Alert roles will be available after resume.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        if (
            guild is None
            or guild.id != self.bot.services.settings.discord_guild_id
            or not isinstance(member, discord.Member)
        ):
            await interaction.followup.send(
                "This alert selector works only inside The Redwing Initiative server.",
                ephemeral=True,
            )
            return
        role = discord.utils.get(guild.roles, name=names.RAID_INCURSION_MATCHMAKING)
        if role is None:
            await interaction.followup.send(
                "The matchmaking alert role is not configured yet.", ephemeral=True
            )
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Member operation-alert opt-out")
                reply = "Raid and Incursion scheduling alerts are now **off**."
            else:
                await member.add_roles(role, reason="Member operation-alert opt-in")
                reply = "Raid and Incursion scheduling alerts are now **on**."
        except (discord.Forbidden, discord.HTTPException):
            reply = "I cannot manage that role. A Commander needs to check ERIN's role order."
        await interaction.followup.send(reply, ephemeral=True)


class OperationAlertRoleView(discord.ui.View):
    def __init__(self, bot: RwiBot) -> None:
        super().__init__(timeout=None)
        self.add_item(OperationAlertRoleButton(bot))


class OperationRoleSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, operation_id: UUID) -> None:
        self.operation_id = operation_id
        super().__init__(
            placeholder="RSVP Going and choose your role",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=role, value=role) for role in OPERATION_ROLES],
            custom_id=f"rwi:operation:{operation_id.hex}:role",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = cast(RwiBot, interaction.client).get_cog("OperationsCog")
        if not isinstance(cog, OperationsCog):
            await interaction.response.send_message(
                "The operation scheduler is not ready.", ephemeral=True
            )
            return
        await cog.record_rsvp(
            interaction,
            self.operation_id,
            status=OperationRsvpStatus.GOING,
            selected_role=self.values[0],
        )


class OperationActionButton(discord.ui.Button[discord.ui.View]):
    def __init__(
        self,
        operation_id: UUID,
        *,
        status: OperationRsvpStatus,
        label: str,
        style: discord.ButtonStyle,
    ) -> None:
        self.operation_id = operation_id
        self.rsvp_status = status
        super().__init__(
            label=label,
            style=style,
            custom_id=f"rwi:operation:{operation_id.hex}:{status.value}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = cast(RwiBot, interaction.client).get_cog("OperationsCog")
        if not isinstance(cog, OperationsCog):
            await interaction.response.send_message(
                "The operation scheduler is not ready.", ephemeral=True
            )
            return
        await cog.record_rsvp(interaction, self.operation_id, status=self.rsvp_status)


class OperationRsvpView(discord.ui.View):
    def __init__(self, operation_id: UUID) -> None:
        super().__init__(timeout=None)
        self.add_item(OperationRoleSelect(operation_id))
        self.add_item(
            OperationActionButton(
                operation_id,
                status=OperationRsvpStatus.GOING,
                label="Going (Undecided)",
                style=discord.ButtonStyle.success,
            )
        )
        self.add_item(
            OperationActionButton(
                operation_id,
                status=OperationRsvpStatus.MAYBE,
                label="Maybe",
                style=discord.ButtonStyle.secondary,
            )
        )
        self.add_item(
            OperationActionButton(
                operation_id,
                status=OperationRsvpStatus.WITHDRAWN,
                label="Withdraw",
                style=discord.ButtonStyle.danger,
            )
        )


class ConfirmationActionButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, operation_id: UUID, *, confirming: bool) -> None:
        self.operation_id = operation_id
        self.confirming = confirming
        super().__init__(
            label="Confirm attendance" if confirming else "Withdraw",
            style=(discord.ButtonStyle.success if confirming else discord.ButtonStyle.danger),
            custom_id=(
                f"rwi:operation:{operation_id.hex}:confirm"
                if confirming
                else f"rwi:operation:{operation_id.hex}:reminder-withdraw"
            ),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = cast(RwiBot, interaction.client).get_cog("OperationsCog")
        if not isinstance(cog, OperationsCog):
            await interaction.response.send_message(
                "The operation scheduler is not ready.", ephemeral=True
            )
            return
        if self.confirming:
            await cog.confirm_attendance(interaction, self.operation_id)
        else:
            await cog.record_rsvp(
                interaction,
                self.operation_id,
                status=OperationRsvpStatus.WITHDRAWN,
            )


class OperationConfirmationView(discord.ui.View):
    def __init__(self, operation_id: UUID) -> None:
        super().__init__(timeout=None)
        self.add_item(ConfirmationActionButton(operation_id, confirming=True))
        self.add_item(ConfirmationActionButton(operation_id, confirming=False))


class OperationsCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("operations")
        self._drafts: dict[int, OperationDraft] = {}
        self._draft_locks: dict[int, asyncio.Lock] = {}
        self._views_restored = False
        self._panel_message_id: int | None = None

    async def cog_unload(self) -> None:
        self.dispatch_reminders.cancel()

    def schedule_start(self) -> None:
        if self.bot.services.maintenance.halted or self.dispatch_reminders.is_running():
            return
        self.dispatch_reminders.start()

    async def restore_persistent_views(self) -> None:
        if self._views_restored:
            return
        for operation in await self.bot.services.operations.active():
            if operation.announcement_message_id is not None:
                self.bot.add_view(
                    OperationRsvpView(operation.id),
                    message_id=operation.announcement_message_id,
                )
            if operation.reminder_message_id is not None:
                self.bot.add_view(
                    OperationConfirmationView(operation.id),
                    message_id=operation.reminder_message_id,
                )
        self._views_restored = True

    async def ensure_schedule_space(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return None
        try:
            reconciler = ServerReconciler(guild)
            await reconciler.ensure_role(names.RAID_INCURSION_MATCHMAKING)
            channel = await reconciler.ensure_channel(
                names.MATCHMAKING,
                _schedule_channel_spec(),
            )
        except (discord.Forbidden, discord.HTTPException, PermissionError, RuntimeError):
            self.log.exception("scheduled_operations_channel_unavailable")
            return None
        if not isinstance(channel, discord.TextChannel):
            return None
        await self._ensure_alert_panel(channel)
        self.log.info(
            "operation_space_ready",
            channel=names.SCHEDULED_OPERATIONS,
            alert_role=names.RAID_INCURSION_MATCHMAKING,
        )
        return channel

    async def _ensure_alert_panel(self, channel: discord.TextChannel) -> None:
        if self._panel_message_id is not None:
            try:
                await channel.fetch_message(self._panel_message_id)
                return
            except discord.NotFound:
                self._panel_message_id = None
        try:
            pinned = await channel.pins()
        except (discord.Forbidden, discord.HTTPException):
            pinned = []
        for message in pinned:
            if message.author == self.bot.user and message.embeds:
                if message.embeds[0].footer.text == SCHEDULE_PANEL_MARKER:
                    self._panel_message_id = message.id
                    return
        embed = discord.Embed(
            title="Raid & Incursion Operation Alerts",
            description=(
                "Use the button below to opt in or out of new scheduled-operation pings. "
                "Event posts remain visible here whether alerts are enabled or not."
            ),
            colour=discord.Colour.orange(),
        )
        embed.set_footer(text=SCHEDULE_PANEL_MARKER)
        panel = await channel.send(embed=embed, view=OperationAlertRoleView(self.bot))
        self._panel_message_id = panel.id
        try:
            await panel.pin(reason="Persistent ERIN operation-alert selector")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
            message.author.bot
            or not message.content.strip()
            or message.guild is None
            or message.guild.id != self.bot.services.settings.discord_guild_id
            or _is_ask_rwi_space(message.channel)
        ):
            return
        await self.maybe_handle_message(message)

    async def maybe_handle_message(self, message: discord.Message) -> bool:
        text = message.content.strip()
        user_id = message.author.id
        draft = self._drafts.get(user_id)
        is_new_request = is_operation_schedule_request(text)
        if draft is None and not is_new_request:
            return False
        if self.bot.services.maintenance.halted:
            await message.channel.send(
                "ERIN's scheduler is paused during maintenance. Please try again after resume."
            )
            return True

        lock = self._draft_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            draft = self._drafts.get(user_id)
            now = datetime.now(UTC)
            if draft is not None and now - draft.created_at > _DRAFT_LIFETIME:
                self._drafts.pop(user_id, None)
                await message.channel.send(
                    "That scheduling interview expired after 20 minutes. Start again when "
                    "you're ready."
                )
                return True
            if draft is not None and text.casefold() in {
                "cancel",
                "cancel event",
                "cancel schedule",
                "stop",
            }:
                self._drafts.pop(user_id, None)
                await message.channel.send("Scheduling cancelled. No event was posted.")
                return True
            if draft is None:
                parsed = parse_operation_request(text, now=now)
                if parsed is None:
                    return False
                draft = OperationDraft.from_request(
                    parsed,
                    requester_user_id=user_id,
                    source_channel_id=message.channel.id,
                    now=now,
                )
                self._drafts[user_id] = draft
                await message.channel.send(_next_draft_question(draft))
                return True

            await self._apply_draft_reply(draft, text, now=now)
            question = _next_draft_question(draft)
            if question:
                await message.channel.send(question)
                return True
            await self._finalize_draft(message, draft, now=now)
            return True

    async def _apply_draft_reply(
        self,
        draft: OperationDraft,
        text: str,
        *,
        now: datetime,
    ) -> None:
        if draft.organizer_role is None:
            draft.organizer_role = parse_operation_role(text)
        if draft.activity is None:
            parsed_activity = parse_operation_activity(text)
            if parsed_activity is not None:
                draft.activity, draft.activity_type, draft.capacity = parsed_activity
        if draft.start_at is None:
            start_at = parse_operation_start(text, target_date=draft.target_date, now=now)
            if start_at is not None:
                draft.start_at = start_at
            request = parse_operation_request(f"schedule event {text}", now=now)
            if draft.target_date is None and request is not None:
                draft.target_date = request.target_date

    async def _finalize_draft(
        self,
        message: discord.Message,
        draft: OperationDraft,
        *,
        now: datetime,
    ) -> None:
        assert draft.activity is not None
        assert draft.activity_type is not None
        assert draft.capacity is not None
        assert draft.organizer_role is not None
        assert draft.start_at is not None
        notice = draft.start_at - now
        if notice < _MINIMUM_NOTICE:
            draft.start_at = None
            draft.target_date = None
            await message.channel.send(
                "That time is less than five minutes away or already passed. Give me a new "
                "date, time, and timezone—for example, `September 3 at 8 PM ET`."
            )
            return
        if notice > _MAXIMUM_NOTICE:
            draft.start_at = None
            draft.target_date = None
            await message.channel.send(
                "I can schedule operations up to 180 days ahead. Give me a nearer date, "
                "time, and timezone."
            )
            return

        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        schedule_channel = await self.ensure_schedule_space()
        matchmaking_role = (
            discord.utils.get(guild.roles, name=names.RAID_INCURSION_MATCHMAKING)
            if guild is not None
            else None
        )
        if guild is None or schedule_channel is None or matchmaking_role is None:
            await message.channel.send(
                "I couldn't reach the scheduled-operations space or alert role. Nothing was "
                "posted; a Commander should check ERIN's server permissions."
            )
            return
        operation = await self.bot.services.operations.create(
            guild_id=guild.id,
            organizer_user_id=message.author.id,
            activity=draft.activity,
            activity_type=draft.activity_type,
            organizer_role=draft.organizer_role,
            start_at=draft.start_at,
            capacity=draft.capacity,
            source_channel_id=draft.source_channel_id,
            matchmaking_role_id=matchmaking_role.id,
        )
        await self.bot.services.operations.upsert_rsvp(
            operation.id,
            user_id=message.author.id,
            status=OperationRsvpStatus.GOING,
            selected_role=draft.organizer_role,
        )
        rsvps = await self.bot.services.operations.rsvps(operation.id)
        announcement = await schedule_channel.send(
            content=(
                f"{matchmaking_role.mention} New {operation.activity_type} operation scheduled."
            ),
            embed=render_operation_embed(operation, rsvps),
            view=OperationRsvpView(operation.id),
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=[matchmaking_role],
                users=False,
                replied_user=False,
            ),
        )
        await self.bot.services.operations.attach_announcement(
            operation.id,
            channel_id=schedule_channel.id,
            message_id=announcement.id,
        )
        self._drafts.pop(message.author.id, None)
        await message.channel.send(
            f"Scheduled **{operation.activity}** for <t:{int(operation.start_at.timestamp())}:F>. "
            f"Your role is **{operation.organizer_role}**. The RSVP post is in "
            f"{schedule_channel.mention}."
        )
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="operation.scheduled",
                actor_id=message.author.id,
                target_type="scheduled_operation",
                target_id=str(operation.id),
                reason=f"Scheduled {operation.activity}",
                details={
                    "activity_type": operation.activity_type,
                    "start_at": operation.start_at.isoformat(),
                    "capacity": operation.capacity,
                    "organizer_role": operation.organizer_role,
                },
            )
        )

    async def record_rsvp(
        self,
        interaction: discord.Interaction,
        operation_id: UUID,
        *,
        status: OperationRsvpStatus,
        selected_role: str | None = None,
    ) -> None:
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "ERIN's scheduler is paused during maintenance.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        operation = await self.bot.services.operations.get(operation_id)
        if operation is None or operation.status != "scheduled":
            await interaction.followup.send("That operation is no longer active.", ephemeral=True)
            return
        existing = await self.bot.services.operations.rsvps(operation_id)
        current = next(
            (entry for entry in existing if entry.discord_user_id == interaction.user.id), None
        )
        if status == OperationRsvpStatus.GOING:
            going_ids = {
                entry.discord_user_id
                for entry in existing
                if entry.status == OperationRsvpStatus.GOING
            }
            if interaction.user.id not in going_ids and len(going_ids) >= operation.capacity:
                await interaction.followup.send(
                    "The confirmed roster is full. Choose **Maybe** to join the standby list.",
                    ephemeral=True,
                )
                return
        chosen_role = selected_role or (current.selected_role if current else "Undecided")
        await self.bot.services.operations.upsert_rsvp(
            operation_id,
            user_id=interaction.user.id,
            status=status,
            selected_role=chosen_role,
        )
        await self.refresh_announcement(operation_id)
        if status == OperationRsvpStatus.WITHDRAWN:
            reply = "You have withdrawn from this operation."
        elif status == OperationRsvpStatus.MAYBE:
            reply = "You are on the **Maybe/standby** list."
        else:
            reply = f"You're marked **Going** as **{chosen_role}**."
        await interaction.followup.send(reply, ephemeral=True)

    async def confirm_attendance(
        self,
        interaction: discord.Interaction,
        operation_id: UUID,
    ) -> None:
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "ERIN's scheduler is paused during maintenance.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        confirmed = await self.bot.services.operations.confirm(
            operation_id,
            user_id=interaction.user.id,
            now=datetime.now(UTC),
        )
        if not confirmed:
            await interaction.followup.send(
                "You do not have an active RSVP for this operation.", ephemeral=True
            )
            return
        await self.refresh_announcement(operation_id)
        await interaction.followup.send(
            "Attendance confirmed. See you there, Agent.", ephemeral=True
        )

    async def refresh_announcement(self, operation_id: UUID) -> None:
        operation = await self.bot.services.operations.get(operation_id)
        if (
            operation is None
            or operation.announcement_channel_id is None
            or operation.announcement_message_id is None
        ):
            return
        channel = self.bot.get_channel(operation.announcement_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(operation.announcement_message_id)
            rsvps = await self.bot.services.operations.rsvps(operation_id)
            await message.edit(
                embed=render_operation_embed(operation, rsvps),
                view=OperationRsvpView(operation_id),
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            self.log.warning("operation_announcement_refresh_failed")

    @tasks.loop(seconds=30, reconnect=True)
    async def dispatch_reminders(self) -> None:
        if self.bot.services.maintenance.halted:
            return
        now = datetime.now(UTC)
        for operation in await self.bot.services.operations.due_reminders(now=now):
            try:
                await self._send_reminder(operation, now=now)
            except Exception:
                self.log.exception("operation_reminder_failed", activity=operation.activity)
        await self.bot.services.operations.complete_past(before=now - timedelta(hours=6))

    @dispatch_reminders.before_loop
    async def before_dispatch_reminders(self) -> None:
        await self.bot.wait_until_ready()

    async def _send_reminder(self, operation: ScheduledOperation, *, now: datetime) -> None:
        if operation.announcement_channel_id is None:
            return
        channel = self.bot.get_channel(operation.announcement_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        rsvps = [
            entry
            for entry in await self.bot.services.operations.rsvps(operation.id)
            if entry.status != OperationRsvpStatus.WITHDRAWN
        ]
        mentions = " ".join(f"<@{entry.discord_user_id}>" for entry in rsvps)
        message = await channel.send(
            content=(
                f"{mentions}\n**Attendance check — {operation.activity} starts "
                f"<t:{int(operation.start_at.timestamp())}:R>.** Confirm below or withdraw "
                "so the organizer has an accurate roster."
            ).strip(),
            view=OperationConfirmationView(operation.id),
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=[discord.Object(id=entry.discord_user_id) for entry in rsvps],
                replied_user=False,
            ),
        )
        await self.bot.services.operations.mark_reminder_sent(
            operation.id,
            message_id=message.id,
            sent_at=now,
        )


def render_operation_embed(
    operation: ScheduledOperation,
    rsvps: list[OperationRsvp],
) -> discord.Embed:
    start_timestamp = int(operation.start_at.timestamp())
    going = [entry for entry in rsvps if entry.status == OperationRsvpStatus.GOING]
    maybe = [entry for entry in rsvps if entry.status == OperationRsvpStatus.MAYBE]
    embed = discord.Embed(
        title=operation.activity,
        description=(
            f"**{operation.activity_type.title()}** coordinated by "
            f"<@{operation.organizer_user_id}> as **{operation.organizer_role}**."
        ),
        colour=discord.Colour.orange(),
        timestamp=operation.start_at,
    )
    embed.add_field(
        name="Start",
        value=f"<t:{start_timestamp}:F>\n<t:{start_timestamp}:R>",
        inline=False,
    )
    embed.add_field(
        name=f"Going — {len(going)}/{operation.capacity}",
        value=_render_roster(going),
        inline=False,
    )
    embed.add_field(
        name=f"Maybe / Standby — {len(maybe)}",
        value=_render_roster(maybe),
        inline=False,
    )
    embed.add_field(
        name="RSVP",
        value=(
            "Choose a role from the menu to join as Going, or use the buttons for "
            "Undecided, Maybe, or Withdraw."
        ),
        inline=False,
    )
    embed.set_footer(text=f"RWI_OPERATION_{operation.id.hex}")
    return embed


def _render_roster(rsvps: list[OperationRsvp]) -> str:
    if not rsvps:
        return "No agents yet."
    return "\n".join(
        f"<@{entry.discord_user_id}> — {entry.selected_role}"
        + (" ✅ confirmed" if entry.confirmed_at is not None else "")
        for entry in rsvps
    )[:1024]


def _next_draft_question(draft: OperationDraft) -> str:
    if draft.organizer_role is None:
        return (
            "What role are you running? Reply with **Tank, Healer, DPS, Support, "
            "Mechanics,** or **Undecided**. You can say `cancel` at any point."
        )
    if draft.activity is None:
        return (
            "Which operation should I schedule: **Broken Rain, Paradise Lost, Operation "
            "Dark Hours,** or **Operation Iron Horse**?"
        )
    if draft.start_at is None:
        if draft.target_date is not None:
            return (
                f"What start time and timezone should I use on "
                f"**{draft.target_date.strftime('%B %d, %Y')}**? For example: `8 PM ET`."
            )
        return (
            "What date, start time, and timezone should I use? For example: "
            "`September 3 at 8 PM ET` or `tomorrow at 7:30 PM PT`."
        )
    return ""


def _schedule_channel_spec() -> ChannelSpec:
    return next(
        spec
        for spec in CATEGORY_CHANNELS[names.MATCHMAKING]
        if spec.name == names.SCHEDULED_OPERATIONS
    )


def _is_ask_rwi_space(channel: discord.abc.Messageable) -> bool:
    if isinstance(channel, discord.TextChannel):
        return channel.name == names.ASK_RWI
    if isinstance(channel, discord.Thread):
        return channel.parent is not None and channel.parent.name == names.ASK_RWI
    return False

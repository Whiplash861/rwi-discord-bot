from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import discord
import structlog
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.moderation import SpamAction, SpamDetector, SpamSignal, choose_spam_action


class ModerationCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        settings = bot.services.settings
        self.detector = SpamDetector(
            burst_messages=settings.spam_burst_messages,
            repeated_messages=settings.spam_repeated_messages,
            severe_messages=settings.spam_severe_messages,
            window=timedelta(seconds=settings.spam_window_seconds),
            incident_cooldown=timedelta(seconds=settings.spam_incident_cooldown_seconds),
        )
        self.log = structlog.get_logger("moderation")
        self._locks: defaultdict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self._is_ask_rwi_space(message.channel):
            return
        await self.handle_message(message)

    async def handle_message(self, message: discord.Message) -> bool:
        settings = self.bot.services.settings
        if (
            not settings.spam_detection_enabled
            or self.bot.services.maintenance.halted
            or message.guild is None
            or message.guild.id != settings.discord_guild_id
            or message.author.bot
            or message.webhook_id is not None
            or (not message.content.strip() and not message.attachments)
            or not isinstance(message.author, discord.Member)
        ):
            return False

        member = message.author
        if self._is_protected(member):
            return False

        signal = self.detector.inspect(
            guild_id=message.guild.id,
            user_id=member.id,
            content=message.content,
            attachment_count=len(message.attachments),
        )
        if not signal.detected:
            return False

        async with self._locks[(message.guild.id, member.id)]:
            if self.bot.services.maintenance.halted:
                return False
            now = datetime.now(UTC)
            try:
                previous_incidents = await self.bot.services.discipline.recent_count(
                    member.id,
                    since=now - timedelta(hours=settings.spam_history_hours),
                )
            except Exception:
                self.log.exception("moderation_history_unavailable", target_id=member.id)
                previous_incidents = 0
            if self.bot.services.maintenance.halted:
                return False
            action = choose_spam_action(previous_incidents, severe=signal.severe)
            await self._apply_action(message, member, action, signal, now)
        return True

    def _is_protected(self, member: discord.Member) -> bool:
        settings = self.bot.services.settings
        if member.id == settings.owner_user_id or member.guild.owner_id == member.id:
            return True
        if any(role.name in names.PROTECTED_ROLES for role in member.roles):
            return True
        bot_member = member.guild.me
        return bot_member is None or member.top_role >= bot_member.top_role

    async def _apply_action(
        self,
        message: discord.Message,
        member: discord.Member,
        action: SpamAction,
        signal: SpamSignal,
        now: datetime,
    ) -> None:
        deleted = False
        action_succeeded = False
        execution_errors: list[str] = []
        expires_at: datetime | None = None
        reason = "RWI automated spam protection: " + ", ".join(signal.reasons)

        try:
            await message.delete()
            deleted = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            execution_errors.append(f"delete:{type(exc).__name__}")

        try:
            if action is SpamAction.WARNING:
                await message.channel.send(
                    f"{member.mention}, please slow down. Continued spam may result in a "
                    "temporary timeout or removal from the server.",
                    allowed_mentions=discord.AllowedMentions(users=True),
                    delete_after=15,
                )
                action_succeeded = True
            elif action is SpamAction.TIMEOUT:
                expires_at = now + timedelta(
                    minutes=self.bot.services.settings.spam_timeout_minutes
                )
                await member.timeout(expires_at, reason=reason)
                action_succeeded = True
            else:
                await member.kick(reason=reason)
                action_succeeded = True
        except (discord.Forbidden, discord.HTTPException) as exc:
            execution_errors.append(f"action:{type(exc).__name__}")

        if action_succeeded and action is not SpamAction.WARNING:
            notice = (
                f"{member.mention} was temporarily timed out for continued or severe spam."
                if action is SpamAction.TIMEOUT
                else "A member was removed for continued or severe spam. RWI never "
                "automatically bans members."
            )
            try:
                await message.channel.send(
                    notice,
                    allowed_mentions=discord.AllowedMentions(users=True),
                    delete_after=15,
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                execution_errors.append(f"notice:{type(exc).__name__}")

        stored_action = action.value if action_succeeded else f"{action.value}_failed"
        evidence: dict[str, object] = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "detectors": list(signal.reasons),
            "observed_messages": signal.observed_messages,
            "repeated_messages": signal.repeated_messages,
            "severe": signal.severe,
            "message_deleted": deleted,
        }
        if execution_errors:
            evidence["execution_errors"] = execution_errors

        try:
            action_id = await self.bot.services.discipline.append(
                user_id=member.id,
                actor_id=self.bot.user.id if self.bot.user else None,
                action=stored_action,
                reason=reason,
                evidence=evidence,
                expires_at=expires_at,
                active=action is SpamAction.TIMEOUT and action_succeeded,
            )
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type=f"moderation.{stored_action}",
                    actor_id=self.bot.user.id if self.bot.user else None,
                    target_type="member",
                    target_id=str(member.id),
                    reason=reason,
                    details={"discipline_action_id": str(action_id), **evidence},
                )
            )
        except Exception:
            self.log.exception(
                "moderation_audit_failed",
                action=stored_action,
                target_id=member.id,
            )

    @staticmethod
    def _is_ask_rwi_space(channel: discord.abc.Messageable) -> bool:
        if isinstance(channel, discord.TextChannel):
            return channel.name == names.ASK_RWI
        return (
            isinstance(channel, discord.Thread)
            and channel.parent is not None
            and channel.parent.name == names.ASK_RWI
        )

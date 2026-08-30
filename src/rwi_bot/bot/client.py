from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import discord
import structlog
from discord.ext import commands
from sqlalchemy import text

from rwi_bot.application import AppServices
from rwi_bot.bot import names
from rwi_bot.bot.server_blueprint import ServerReconciler
from rwi_bot.bot.views import PlatformRoleView
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.maintenance import ResumeCheck


class RwiBot(commands.Bot):
    def __init__(self, services: AppServices) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        intents.moderation = True
        intents.messages = True
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            application_id=services.settings.discord_application_id,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=False, users=True, replied_user=False
            ),
        )
        self.services = services
        self.log = structlog.get_logger("discord")
        self._auto_bootstrap_complete = False

    async def setup_hook(self) -> None:
        from rwi_bot.cogs.admin import AdminCog
        from rwi_bot.cogs.community import CommunityLoadoutsCog
        from rwi_bot.cogs.community_learning import (
            CommunityClaimReviewView,
            CommunityLearningCog,
        )
        from rwi_bot.cogs.conversation import ConversationCog
        from rwi_bot.cogs.moderation import ModerationCog
        from rwi_bot.cogs.onboarding import OnboardingCog
        from rwi_bot.cogs.privacy import PrivacyCog
        from rwi_bot.cogs.releases import ReleaseNotesCog

        self.add_view(
            PlatformRoleView(
                guild_id=self.services.settings.discord_guild_id,
                halted=lambda: self.services.maintenance.halted,
            )
        )
        self.add_view(CommunityClaimReviewView(self))
        await self.add_cog(AdminCog(self))
        await self.add_cog(OnboardingCog(self))
        await self.add_cog(ModerationCog(self))
        await self.add_cog(CommunityLoadoutsCog(self))
        await self.add_cog(CommunityLearningCog(self))
        await self.add_cog(ConversationCog(self))
        await self.add_cog(PrivacyCog(self))
        await self.add_cog(ReleaseNotesCog(self))

        if self.services.settings.sync_commands:
            guild = discord.Object(id=self.services.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        guild = self.get_guild(self.services.settings.discord_guild_id)
        if guild is None:
            self.log.error("target_guild_missing", guild_id=self.services.settings.discord_guild_id)
            return
        await self.ensure_server_identity(guild)
        await self.set_operating_presence()
        if self.services.settings.auto_bootstrap_server and not self._auto_bootstrap_complete:
            try:
                report = await ServerReconciler(guild).reconcile()
            except Exception:
                self.log.exception("automatic_server_bootstrap_failed")
            else:
                self._auto_bootstrap_complete = True
                commander = discord.utils.get(guild.roles, name=names.DIVISION_COMMANDER)
                owner = guild.get_member(self.services.settings.owner_user_id)
                if (
                    commander is not None
                    and owner is not None
                    and guild.me is not None
                    and commander.position < guild.me.top_role.position
                    and commander not in owner.roles
                ):
                    try:
                        await owner.add_roles(commander, reason="RWI owner bootstrap")
                    except discord.Forbidden:
                        report.warnings.append(
                            "The bot could not assign Division Commander to the owner; "
                            "assign it manually after role ordering."
                        )
                self.log.info(
                    "automatic_server_bootstrap_complete",
                    created_roles=len(report.created_roles),
                    created_categories=len(report.created_categories),
                    created_channels=len(report.created_channels),
                    updated_channels=len(report.updated_channels),
                    warnings=report.warnings,
                )
        self.log.info(
            "bot_ready",
            user_id=self.user.id if self.user else None,
            guild_id=guild.id,
            halted=self.services.maintenance.halted,
        )
        onboarding = self.get_cog("OnboardingCog")
        if onboarding is not None:
            await onboarding.ensure_platform_panel()  # type: ignore[attr-defined]
        community = self.get_cog("CommunityLoadoutsCog")
        if community is not None:
            community.schedule_sync()  # type: ignore[attr-defined]
        releases = self.get_cog("ReleaseNotesCog")
        if releases is not None:
            releases.schedule_publish()  # type: ignore[attr-defined]

    async def ensure_server_identity(self, guild: discord.Guild) -> None:
        member = guild.me
        if member is None or member.display_name == names.BOT_DISPLAY_NAME:
            return
        try:
            await member.edit(
                nick=names.BOT_DISPLAY_NAME,
                reason=f"Use the canonical {names.BOT_EXPANDED_NAME} server identity",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            self.log.warning("server_identity_update_failed", error_type=type(exc).__name__)
        else:
            self.log.info("server_identity_updated", display_name=names.BOT_DISPLAY_NAME)

    async def set_operating_presence(self) -> None:
        if self.services.maintenance.halted:
            await self.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name="ERIN Maintenance Mode"),
            )
        else:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="The Division 2 intelligence",
                ),
            )

    async def run_resume_checks(self) -> list[ResumeCheck]:
        results: list[ResumeCheck] = []
        try:
            async with self.services.database.session() as session:
                await session.execute(text("SELECT 1"))
            results.append(
                ResumeCheck(name="database", passed=True, detail="PostgreSQL responded.")
            )
        except Exception as exc:
            results.append(
                ResumeCheck(
                    name="database",
                    passed=False,
                    detail=f"PostgreSQL check failed: {type(exc).__name__}",
                )
            )

        guild = self.get_guild(self.services.settings.discord_guild_id)
        results.append(
            ResumeCheck(
                name="discord_guild",
                passed=guild is not None,
                detail="Target guild is connected." if guild else "Target guild is unavailable.",
            )
        )
        if guild and guild.me:
            permissions = guild.me.guild_permissions
            required = {
                "manage_roles": permissions.manage_roles,
                "manage_channels": permissions.manage_channels,
                "manage_messages": permissions.manage_messages,
                "moderate_members": permissions.moderate_members,
                "kick_members": permissions.kick_members,
            }
            missing = sorted(name for name, enabled in required.items() if not enabled)
            results.append(
                ResumeCheck(
                    name="discord_permissions",
                    passed=not missing,
                    detail=(
                        "Required permissions are present."
                        if not missing
                        else f"Missing permissions: {', '.join(missing)}"
                    ),
                )
            )

        spent, limit = await self.services.budget.utilization()
        results.append(
            ResumeCheck(
                name="budget",
                passed=spent < limit,
                detail=f"Estimated spend ${spent:.2f} of ${limit:.2f} hard limit.",
            )
        )
        key_present = bool(self.services.settings.openai_api_key.get_secret_value().strip())
        results.append(
            ResumeCheck(
                name="openai_key",
                passed=key_present,
                detail="OpenAI key is present." if key_present else "OpenAI key is missing.",
            )
        )
        breaker = await self.services.ai.breaker.snapshot()
        results.append(
            ResumeCheck(
                name="openai_breaker",
                passed=breaker.state.value != "open",
                detail=(
                    f"OpenAI breaker is {breaker.state.value} with "
                    f"{breaker.recent_failures} recent failure(s)."
                ),
            )
        )
        return results

    async def send_audit_summary(self, record: AuditRecord, event_id: UUID) -> None:
        if record.event_type.startswith("answer.") or record.event_type == "release.published":
            return
        guild = self.get_guild(self.services.settings.discord_guild_id)
        if guild is None:
            return
        target_name = (
            names.TECHNICIAN_LAB
            if record.event_type.startswith("knowledge.unanswered")
            else names.BOT_OPS
        )
        channel = discord.utils.get(guild.text_channels, name=target_name)
        if channel is None:
            return
        embed = build_audit_summary_embed(record, event_id)
        await channel.send(embed=embed)

    async def close(self) -> None:
        await self.services.database.dispose()
        await super().close()


def build_audit_summary_embed(record: AuditRecord, event_id: UUID) -> discord.Embed:
    if record.event_type == "knowledge.unanswered_ticket":
        details = record.details
        question = str(details.get("question") or "Original question was not recorded.")[:1024]
        failure = str(
            details.get("failure_summary")
            or record.reason
            or "ERIN could not establish a current, corroborated answer."
        )[:1024]
        requested_action = str(
            details.get("requested_action")
            or "Research the current answer and update ERIN's verified knowledge."
        )[:1024]
        web_status = (
            "attempted, but it did not produce sufficient current evidence"
            if details.get("used_web_search")
            else "not completed or not available for this attempt"
        )
        embed = discord.Embed(
            title="ERIN needs help with an unanswered question",
            description=(
                "The member could not supply the missing information, so this question now "
                "needs Technician research."
            ),
            colour=discord.Colour.orange(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(name="Original question", value=question, inline=False)
        embed.add_field(name="What went wrong", value=failure, inline=False)
        embed.add_field(
            name="Checks already attempted",
            value=f"ERIN knowledge: checked\nCurrent web search: {web_status}",
            inline=False,
        )
        embed.add_field(
            name="What the Technician should verify", value=requested_action, inline=False
        )
        if record.actor_id:
            embed.add_field(name="Requested by", value=f"<@{record.actor_id}>")
        if record.target_id:
            embed.add_field(name="Ticket ID", value=f"`{record.target_id}`", inline=False)
        return embed

    embed = discord.Embed(
        title=record.event_type,
        description=(record.reason or "No reason supplied.")[:1500],
        colour=discord.Colour.orange(),
        timestamp=datetime.now(UTC),
    )
    embed.add_field(name="Event ID", value=f"`{event_id}`", inline=False)
    if record.actor_id:
        embed.add_field(name="Actor", value=f"<@{record.actor_id}> (`{record.actor_id}`)")
    if record.target_id:
        embed.add_field(name="Target", value=f"`{record.target_id}`", inline=False)
    return embed

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
        from rwi_bot.cogs.conversation import ConversationCog
        from rwi_bot.cogs.moderation import ModerationCog
        from rwi_bot.cogs.onboarding import OnboardingCog

        self.add_view(
            PlatformRoleView(
                guild_id=self.services.settings.discord_guild_id,
                halted=lambda: self.services.maintenance.halted,
            )
        )
        await self.add_cog(AdminCog(self))
        await self.add_cog(OnboardingCog(self))
        await self.add_cog(ModerationCog(self))
        await self.add_cog(ConversationCog(self))

        if self.services.settings.sync_commands:
            guild = discord.Object(id=self.services.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        guild = self.get_guild(self.services.settings.discord_guild_id)
        if guild is None:
            self.log.error("target_guild_missing", guild_id=self.services.settings.discord_guild_id)
            return
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

    async def set_operating_presence(self) -> None:
        if self.services.maintenance.halted:
            await self.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name="RWI Maintenance Mode"),
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
        return results

    async def send_audit_summary(self, record: AuditRecord, event_id: UUID) -> None:
        if record.event_type.startswith("answer."):
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
        await channel.send(embed=embed)

    async def close(self) -> None:
        await self.services.database.dispose()
        await super().close()

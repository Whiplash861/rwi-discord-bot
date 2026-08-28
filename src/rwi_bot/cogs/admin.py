from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from rwi_bot.bot.checks import is_commander, is_maintenance_operator
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import ServerReconciler
from rwi_bot.bot.views import ConfirmationView
from rwi_bot.domain.schemas import AuditRecord


class AdminCog(commands.Cog):
    rwi = app_commands.Group(name="rwi", description="RWI operations and emergency controls")

    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot

    @rwi.command(name="halt", description="Enter durable emergency maintenance mode")
    @app_commands.describe(reason="Why RWI must stop answering and running checks")
    async def halt(self, interaction: discord.Interaction, reason: str) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            "Confirm emergency halt. This immediately blocks new answers, OpenAI calls, web "
            "searches, background checks, cache learning, onboarding, and bot moderation.",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(content="Emergency halt cancelled.", view=None)
            return
        state = await self.bot.services.maintenance.halt(
            actor_id=interaction.user.id,
            reason=reason,
        )
        await self.bot.set_operating_presence()
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="system.emergency_halt",
                actor_id=interaction.user.id,
                target_type="bot",
                target_id=str(self.bot.user.id if self.bot.user else "unknown"),
                reason=reason,
                details={"state_revision": state.revision},
            )
        )
        await interaction.edit_original_response(
            content="RWI is halted and displaying **Do Not Disturb — RWI Maintenance Mode**.",
            view=None,
        )

    @rwi.command(name="status", description="Show maintenance, health, and budget state")
    async def status(self, interaction: discord.Interaction) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        state = self.bot.services.maintenance.state
        spent, limit = await self.bot.services.budget.utilization()
        status = "HALTED (Do Not Disturb)" if state.halted else "ONLINE"
        await interaction.response.send_message(
            f"**RWI status:** {status}\n"
            f"**Reason:** {state.reason or 'None'}\n"
            f"**Changed:** {discord.utils.format_dt(state.changed_at, style='R')}\n"
            f"**State revision:** `{state.revision}`\n"
            f"**Estimated API spend:** `${spent:.2f}` / `${limit:.2f}`",
            ephemeral=True,
        )

    @rwi.command(name="resume", description="Run health checks and leave maintenance mode")
    @app_commands.describe(force="Owner-only override when a critical health check fails")
    async def resume(self, interaction: discord.Interaction, force: bool = False) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        if force and interaction.user.id != self.bot.services.settings.owner_user_id:
            await interaction.response.send_message(
                "Force-resume is restricted to the Discord server owner.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        state, checks = await self.bot.services.maintenance.resume(
            actor_id=interaction.user.id,
            checks=self.bot.run_resume_checks,
            force=force,
        )
        lines = [
            f"{'✅' if check.passed else '❌'} **{check.name}:** {check.detail}" for check in checks
        ]
        if state.halted:
            heading = "RWI remains halted because one or more critical checks failed."
        else:
            heading = "RWI resumed successfully. Old queued requests were not replayed."
            await self.bot.set_operating_presence()
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="system.resume",
                    actor_id=interaction.user.id,
                    target_type="bot",
                    target_id=str(self.bot.user.id if self.bot.user else "unknown"),
                    reason="Force resume" if force else "Health checks passed",
                    details={"force": force, "state_revision": state.revision},
                )
            )
        await interaction.followup.send(f"{heading}\n\n" + "\n".join(lines), ephemeral=True)

    @rwi.command(
        name="bootstrap", description="Create or reconcile the canonical RWI server layout"
    )
    async def bootstrap(self, interaction: discord.Interaction) -> None:
        if not self._commander(interaction) or interaction.guild is None:
            await self._deny(interaction)
            return
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            "Confirm reconciliation of the roles, categories, channels, and permission "
            "overwrites in this server. Existing channels outside the RWI blueprint are untouched.",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Server bootstrap cancelled.", view=None
            )
            return
        await interaction.edit_original_response(content="Reconciling the RWI server…", view=None)
        report = await ServerReconciler(interaction.guild).reconcile()
        commander = discord.utils.get(interaction.guild.roles, name="Division Commander")
        if commander and isinstance(interaction.user, discord.Member):
            try:
                await interaction.user.add_roles(commander, reason="RWI owner bootstrap")
            except discord.Forbidden:
                report.warnings.append(
                    "The bot could not assign Division Commander; assign it manually after "
                    "role ordering."
                )
        onboarding = self.bot.get_cog("OnboardingCog")
        if onboarding is not None:
            await onboarding.ensure_platform_panel()  # type: ignore[attr-defined]
        summary = (
            f"Created {len(report.created_roles)} roles, "
            f"{len(report.created_categories)} categories, and "
            f"{len(report.created_channels)} channels. "
            f"Reconciled {len(report.updated_channels)} existing channels."
        )
        if report.warnings:
            summary += "\n\n**Manual checks:**\n- " + "\n- ".join(report.warnings)
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="server.bootstrap",
                actor_id=interaction.user.id,
                target_type="guild",
                target_id=str(interaction.guild.id),
                reason="Canonical RWI structure reconciliation",
                details={
                    "created_roles": report.created_roles,
                    "created_channels": report.created_channels,
                    "warnings": report.warnings,
                },
            )
        )
        await interaction.edit_original_response(content=summary)

    def _maintenance_operator(self, interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_maintenance_operator(
            interaction.user, self.bot.services.settings.owner_user_id
        )

    def _commander(self, interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_commander(
            interaction.user, self.bot.services.settings.owner_user_id
        )

    @staticmethod
    async def _deny(interaction: discord.Interaction) -> None:
        message = "That operation is restricted to the authorized RWI staff role."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

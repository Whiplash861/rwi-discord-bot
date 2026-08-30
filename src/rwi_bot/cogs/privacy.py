from __future__ import annotations

import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.views import ConfirmationView
from rwi_bot.domain.schemas import AuditRecord


class PrivacyCog(commands.Cog):
    privacy = app_commands.Group(
        name="privacy",
        description="Inspect and control your private RWI member data",
    )

    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot

    @privacy.command(name="status", description="Show your RWI learning preference")
    async def status(self, interaction: discord.Interaction) -> None:
        if not await self._allowed(interaction):
            return
        opted_out = await self.bot.services.profiles.learning_opted_out(interaction.user.id)
        await interaction.response.send_message(
            "**RWI privacy status**\n"
            f"Shared answer learning: **{'disabled' if opted_out else 'enabled'}**\n\n"
            "Learning opt-out prevents your new answers and feedback from becoming shared "
            "cache material and removes your requester attribution from new review tickets. "
            "It does not prevent a question you ask from being processed to answer you.",
            ephemeral=True,
        )

    @privacy.command(
        name="learning",
        description="Enable or disable use of your interactions for shared answer learning",
    )
    @app_commands.describe(enabled="Whether your future interactions may improve shared answers")
    async def learning(self, interaction: discord.Interaction, enabled: bool) -> None:
        if not await self._allowed(interaction):
            return
        await self.bot.services.profiles.set_learning_opt_out(
            interaction.user.id,
            opted_out=not enabled,
        )
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="privacy.learning_preference_changed",
                actor_id=interaction.user.id,
                target_type="user_profile",
                target_id="self",
                reason="Member privacy preference",
                details={"learning_enabled": enabled},
            )
        )
        await interaction.response.send_message(
            f"Shared answer learning is now **{'enabled' if enabled else 'disabled'}** for "
            "your future interactions.",
            ephemeral=True,
        )

    @privacy.command(name="export", description="Download a private export of your RWI data")
    async def export(self, interaction: discord.Interaction) -> None:
        if not await self._allowed(interaction):
            return
        data = await self.bot.services.profiles.export_data(interaction.user.id)
        payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        attachment = discord.File(io.BytesIO(payload), filename="rwi-private-data.json")
        await interaction.response.send_message(
            "Here is your private RWI data export. It intentionally excludes security, "
            "moderation, and immutable operational audit records.",
            file=attachment,
            ephemeral=True,
        )

    @privacy.command(
        name="reset",
        description="Reset your profile and remove private conversation and feedback state",
    )
    async def reset(self, interaction: discord.Interaction) -> None:
        if not await self._allowed(interaction):
            return
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            "Confirm private-state reset. This clears your saved profile preferences, "
            "persisted conversation summaries, and feedback; anonymizes your requester ID on "
            "review tickets and cost records; and clears this process's conversation memory. "
            "Your current learning opt-out choice is preserved. Security, moderation, and "
            "immutable audit records are retained.",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Private-state reset cancelled or confirmation expired.", view=None
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="RWI entered maintenance mode; no private state was changed.",
                view=None,
            )
            return
        result = await self.bot.services.profiles.reset_private_state(interaction.user.id)
        cleared_memory = 0
        conversation = self.bot.get_cog("ConversationCog")
        if conversation is not None:
            cleared_memory = conversation.clear_user_memory(interaction.user.id)  # type: ignore[attr-defined]
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="privacy.private_state_reset",
                actor_id=interaction.user.id,
                target_type="user_profile",
                target_id="self",
                reason="Member-requested private-state reset",
                details={
                    "conversation_sessions_deleted": result.conversations_deleted,
                    "feedback_deleted": result.feedback_deleted,
                    "review_tickets_anonymized": result.tickets_anonymized,
                    "usage_records_anonymized": result.usage_records_anonymized,
                    "in_memory_sessions_cleared": cleared_memory,
                    "learning_opt_out_preserved": result.learning_opt_out_preserved,
                },
            )
        )
        await interaction.edit_original_response(
            content="Your private RWI profile, conversation, and feedback state was reset.",
            view=None,
        )

    async def _allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.bot.services.settings.discord_guild_id:
            await interaction.response.send_message(
                "RWI privacy controls are available inside The Redwing Initiative server.",
                ephemeral=True,
            )
            return False
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "RWI privacy controls are temporarily unavailable during maintenance mode.",
                ephemeral=True,
            )
            return False
        return True

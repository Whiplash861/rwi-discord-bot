from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from rwi_bot.bot import names


class ConfirmationView(discord.ui.View):
    def __init__(self, authorized_user_id: int, *, timeout: float = 45.0) -> None:
        super().__init__(timeout=timeout)
        self.authorized_user_id = authorized_user_id
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message(
                "Only the person who initiated this action can confirm it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, _: discord.ui.Button[ConfirmationView]
    ) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, _: discord.ui.Button[ConfirmationView]
    ) -> None:
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


class PlatformButton(discord.ui.Button[discord.ui.View]):
    def __init__(
        self,
        role_name: str,
        emoji: str,
        style: discord.ButtonStyle,
        *,
        guild_id: int,
        halted: Callable[[], bool],
    ) -> None:
        super().__init__(
            label=role_name,
            emoji=emoji,
            style=style,
            custom_id=f"rwi:platform:{role_name.casefold()}",
        )
        self.role_name = role_name
        self.guild_id = guild_id
        self._halted = halted

    async def callback(self, interaction: discord.Interaction) -> None:
        if self._halted():
            await interaction.response.send_message(
                "RWI is in maintenance mode. Platform roles will be available after resume.",
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message(
                "Platform roles can only be changed inside the RWI server.", ephemeral=True
            )
            return
        if interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This platform selector belongs to The Redwing Initiative server.",
                ephemeral=True,
            )
            return
        member = interaction.user
        rogue = discord.utils.get(member.roles, name=names.ROGUE_AGENT)
        if rogue is not None:
            await interaction.response.send_message(
                "Platform roles cannot be changed while Rogue Agent restrictions are active.",
                ephemeral=True,
            )
            return
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if role is None:
            await interaction.response.send_message(
                "That platform role is not configured. A Division Commander has been notified.",
                ephemeral=True,
            )
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Member platform-role toggle")
                message = f"Removed **{role.name}**."
            else:
                await member.add_roles(role, reason="Member platform-role toggle")
                message = f"Added **{role.name}**. You may select more than one platform."
        except (discord.Forbidden, discord.HTTPException):
            message = (
                "I cannot manage that role. Please ask a Division Commander to check role order."
            )
        await interaction.response.send_message(message, ephemeral=True)


class PlatformRoleView(discord.ui.View):
    def __init__(self, *, guild_id: int, halted: Callable[[], bool]) -> None:
        super().__init__(timeout=None)
        self.add_item(
            PlatformButton(
                names.XBOX,
                "🎮",
                discord.ButtonStyle.success,
                guild_id=guild_id,
                halted=halted,
            )
        )
        self.add_item(
            PlatformButton(
                names.PC,
                "🖥️",
                discord.ButtonStyle.secondary,
                guild_id=guild_id,
                halted=halted,
            )
        )
        self.add_item(
            PlatformButton(
                names.PS,
                "🎮",
                discord.ButtonStyle.primary,
                guild_id=guild_id,
                halted=halted,
            )
        )


class FeedbackView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        helpful: Callable[[], Awaitable[None]],
        incorrect: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(timeout=60 * 60 * 24)
        self.user_id = user_id
        self._helpful = helpful
        self._incorrect = incorrect

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the member who asked this question can rate this answer.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Helpful", emoji="✅", style=discord.ButtonStyle.success)
    async def helpful_button(
        self, interaction: discord.Interaction, button: discord.ui.Button[FeedbackView]
    ) -> None:
        await self._helpful()
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Incorrect / Outdated", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def incorrect_button(
        self, interaction: discord.Interaction, button: discord.ui.Button[FeedbackView]
    ) -> None:
        await self._incorrect()
        button.disabled = True
        await interaction.response.edit_message(view=self)

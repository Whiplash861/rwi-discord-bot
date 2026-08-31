from __future__ import annotations

import discord
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.views import PlatformRoleView
from rwi_bot.domain.schemas import AuditRecord

PLATFORM_PANEL_MARKER = "RWI_PLATFORM_PANEL_V1"


def render_erin_introduction() -> str:
    return (
        "Welcome to The Redwing Initiative, Agent. I'm **ERIN**—Enhanced "
        "Reconnaissance, Intelligence, and Navigation—RWI's intelligence agent. I can "
        "help with current Division 2 builds, encounter mechanics, progression, and "
        "recommendations.\n\n"
        "If you'd like personalized answers, reply with any profile details you want me "
        "to remember, such as:\n"
        "- platform(s): Xbox, PC, or PlayStation\n"
        "- focus: PvE, PvP, or both\n"
        "- SHD and Expertise levels\n"
        "- gamertag\n"
        "- preferred playstyle or team role\n"
        "- any other game-relevant notes you want me to use\n\n"
        "**Sharing any of this is optional.** It is used only to personalize the builds, "
        "advice, and recommendations I give you. I won't create or change those profile "
        "details unless you provide them, and you can update them naturally at any time. "
        "Use `/privacy export` to review your saved data or `/privacy reset` to clear it.\n\n"
        "Helpful optional notes might be `I'm a day-one player and a Healer main` or `I "
        "like sniper rifles and dislike Tank builds.` You can also write `Add to my profile: "
        "...` for another game-relevant preference.\n\n"
        "You can reply in one message—for example: `Platform: PC. I play both. SHD 2500, "
        "Expertise 20. Gamertag: AgentName. Playstyle: support and skill builds.` If "
        "something appears to be real-world personal information, I will withhold it and "
        "ask you to clarify instead of adding it to your profile."
    )


class OnboardingCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self._panel_message_id: int | None = None

    async def ensure_platform_panel(self) -> discord.Message | None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return None
        channel = discord.utils.get(guild.text_channels, name=names.WELCOME)
        if channel is None:
            return None
        if self._panel_message_id:
            try:
                return await channel.fetch_message(self._panel_message_id)
            except discord.NotFound:
                self._panel_message_id = None
        for message in await channel.pins():
            if message.author == self.bot.user and message.embeds:
                footer = message.embeds[0].footer.text or ""
                if PLATFORM_PANEL_MARKER in footer:
                    self._panel_message_id = message.id
                    return message
        embed = discord.Embed(
            title="Choose Your Platforms",
            description=(
                "Select every platform you use. Click a selected platform again to remove it. "
                "These roles control platform-specific matchmaking access and remain useful "
                "after crossplay launches."
            ),
            colour=discord.Colour.orange(),
        )
        embed.set_footer(text=PLATFORM_PANEL_MARKER)
        panel = await channel.send(
            embed=embed,
            view=PlatformRoleView(
                guild_id=self.bot.services.settings.discord_guild_id,
                halted=lambda: self.bot.services.maintenance.halted,
            ),
        )
        try:
            await panel.pin(reason="Persistent RWI platform-role selector")
        except discord.Forbidden:
            pass
        self._panel_message_id = panel.id
        return panel

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot or member.guild.id != self.bot.services.settings.discord_guild_id:
            return
        if self.bot.services.maintenance.halted or member.pending:
            return
        await self._onboard(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if (
            before.pending
            and not after.pending
            and not after.bot
            and after.guild.id == self.bot.services.settings.discord_guild_id
            and not self.bot.services.maintenance.halted
        ):
            await self._onboard(after)

    async def _onboard(self, member: discord.Member) -> None:
        agent = discord.utils.get(member.guild.roles, name=names.AGENT)
        role_ready = agent is not None
        if agent is not None and agent not in member.roles:
            try:
                await member.add_roles(agent, reason="RWI automatic member onboarding")
            except discord.Forbidden:
                role_ready = False
        panel = await self.ensure_platform_panel()
        channel = discord.utils.get(member.guild.text_channels, name=names.WELCOME)
        if channel is not None:
            destination = panel.jump_url if panel else "the pinned platform selector"
            await channel.send(
                f"Welcome to The Redwing Initiative, {member.mention}! You are now an "
                f"**Agent**. Choose your platforms here: {destination}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        if role_ready:
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="member.agent_assigned",
                    actor_id=self.bot.user.id if self.bot.user else None,
                    target_type="member",
                    target_id=str(member.id),
                    reason="Automatic onboarding after membership screening",
                )
            )
        await self._introduce_erin(member)

    async def _introduce_erin(self, member: discord.Member) -> None:
        target_id = str(member.id)
        audit = self.bot.services.audit
        if await audit.has_event(event_type="member.erin_introduction_sent", target_id=target_id):
            return
        if await audit.has_event(
            event_type="member.erin_introduction_unavailable", target_id=target_id
        ):
            return
        try:
            await member.send(render_erin_introduction())
        except (discord.Forbidden, discord.HTTPException) as exc:
            await audit.record(
                AuditRecord(
                    event_type="member.erin_introduction_unavailable",
                    actor_id=self.bot.user.id if self.bot.user else None,
                    target_type="member",
                    target_id=target_id,
                    reason="Member DMs were unavailable during optional ERIN introduction",
                    details={"error_type": type(exc).__name__},
                )
            )
            return
        await audit.record(
            AuditRecord(
                event_type="member.erin_introduction_sent",
                actor_id=self.bot.user.id if self.bot.user else None,
                target_type="member",
                target_id=target_id,
                reason="Consent-forward optional profile introduction after joining RWI",
                details={"profile_collection": "optional_explicit_self_report"},
            )
        )

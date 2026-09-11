from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import discord
import structlog
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.checks import is_maintenance_operator
from rwi_bot.bot.client import RwiBot
from rwi_bot.db.models import CommunityClaim, CommunityClaimStatus
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.community_learning import (
    ClaimStateConflictError,
    CommunityClaimProposal,
    claim_id_from_footer,
    infer_claim_review_reply,
)
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.member_profiles import (
    MemberProfileUpdate,
    detect_possible_personal_information,
)
from rwi_bot.services.observation import KnowledgeVerifier


class ClaimReviewModal(discord.ui.Modal):
    explanation: discord.ui.TextInput[ClaimReviewModal] = discord.ui.TextInput(
        label="Correction, limitation, or reason",
        placeholder="Explain the accurate behavior and any safe legitimate alternative.",
        style=discord.TextStyle.paragraph,
        min_length=8,
        max_length=1800,
        required=True,
    )

    def __init__(
        self,
        cog: CommunityLearningCog,
        review_message: discord.Message,
        status: CommunityClaimStatus,
    ) -> None:
        title = {
            CommunityClaimStatus.QUALIFIED: "Qualify community claim",
            CommunityClaimStatus.INCORRECT: "Reject community claim",
            CommunityClaimStatus.BUG: "Exclude bug interaction",
            CommunityClaimStatus.EXPLOIT: "Exclude exploit method",
        }[status]
        super().__init__(title=title, timeout=300)
        self.cog = cog
        self.review_message = review_message
        self.status = status

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        result = await self.cog.resolve_claim(
            self.review_message,
            reviewer=interaction.user,
            status=self.status,
            note=str(self.explanation),
        )
        await interaction.followup.send(result, ephemeral=True)


class CommunityClaimReviewView(discord.ui.View):
    def __init__(self, bot: RwiBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def _dispatch(
        self,
        interaction: discord.Interaction,
        status: CommunityClaimStatus,
    ) -> None:
        cog = cast(CommunityLearningCog | None, self.bot.get_cog("CommunityLearningCog"))
        if cog is None or not await cog.authorize_review(interaction):
            return
        if interaction.message is None:
            await interaction.response.send_message(
                "The review message is unavailable.", ephemeral=True
            )
            return
        if status is CommunityClaimStatus.VERIFIED:
            await interaction.response.defer(ephemeral=True)
            result = await cog.resolve_claim(
                interaction.message,
                reviewer=interaction.user,
                status=status,
                note=None,
            )
            await interaction.followup.send(result, ephemeral=True)
            return
        await interaction.response.send_modal(ClaimReviewModal(cog, interaction.message, status))

    @discord.ui.button(
        label="Accurate",
        style=discord.ButtonStyle.success,
        custom_id="rwi:community-claim:verified",
    )
    async def accurate(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button[CommunityClaimReviewView],
    ) -> None:
        await self._dispatch(interaction, CommunityClaimStatus.VERIFIED)

    @discord.ui.button(
        label="Qualify",
        style=discord.ButtonStyle.primary,
        custom_id="rwi:community-claim:qualified",
    )
    async def qualify(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button[CommunityClaimReviewView],
    ) -> None:
        await self._dispatch(interaction, CommunityClaimStatus.QUALIFIED)

    @discord.ui.button(
        label="Incorrect",
        style=discord.ButtonStyle.secondary,
        custom_id="rwi:community-claim:incorrect",
    )
    async def incorrect(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button[CommunityClaimReviewView],
    ) -> None:
        await self._dispatch(interaction, CommunityClaimStatus.INCORRECT)

    @discord.ui.button(
        label="Bug",
        style=discord.ButtonStyle.danger,
        custom_id="rwi:community-claim:bug",
    )
    async def bug(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button[CommunityClaimReviewView],
    ) -> None:
        await self._dispatch(interaction, CommunityClaimStatus.BUG)

    @discord.ui.button(
        label="Exploit",
        style=discord.ButtonStyle.danger,
        custom_id="rwi:community-claim:exploit",
    )
    async def exploit(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button[CommunityClaimReviewView],
    ) -> None:
        await self._dispatch(interaction, CommunityClaimStatus.EXPLOIT)


class CommunityLearningCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("community_learning")

    async def submit_candidate(
        self,
        message: discord.Message,
        *,
        proposal: CommunityClaimProposal,
        member_label: str,
        source_question: str,
        prior_answer_excerpt: str,
        quiet: bool = False,
    ) -> CommunityClaim | None:
        if (
            message.guild is None
            or self.bot.services.maintenance.halted
            or message.guild.id != self.bot.services.settings.discord_guild_id
        ):
            return None
        if detect_possible_personal_information(proposal.claim_text):
            await message.reply(
                "Please resend only the game-related claim, without personal details.",
                mention_author=False,
            )
            return None
        proposal = CommunityClaimProposal(
            sanitize_for_technicians(proposal.claim_text), proposal.risk_flag
        )
        try:
            if await self.bot.services.profiles.learning_opted_out(message.author.id):
                return None
            claim = await self.bot.services.community_claims.create_pending(
                guild_id=message.guild.id,
                source_channel_id=message.channel.id,
                source_message_id=message.id,
                submitter_user_id=message.author.id,
                member_label=member_label,
                source_question=source_question,
                prior_answer_excerpt=prior_answer_excerpt,
                proposal=proposal,
                source_url=message.jump_url,
                game_version=self.bot.services.qa.current_game_version,
            )
        except Exception:
            self.log.exception("community_claim_capture_failed")
            return None
        if claim is None:
            return None

        # New claims never become facts merely because the submitter has a trusted role.
        verifier = KnowledgeVerifier(self.bot.services.ai, self.bot.services.knowledge)
        assessment = await verifier.check(
            proposal.claim_text,
            context=f"{source_question}\nEarlier answer (may be wrong): {prior_answer_excerpt}",
            game_version=self.bot.services.qa.current_game_version,
            since=self.bot.services.qa.current_game_version_started_on.isoformat(),
            actor_id=message.author.id,
        )
        if await self.bot.services.profiles.learning_opted_out(message.author.id):
            await self.bot.services.community_claims.remove_or_anonymize_by_submitter(
                message.author.id
            )
            return None
        evidence_note = (
            assessment.summary
            + "\n"
            + "\n".join(f"{e.url} ({e.published_on}): {e.explanation}" for e in assessment.evidence)
        )
        if assessment.verdict == "corroborated" and not proposal.risk_flag:
            claim = await self.bot.services.community_claims.review(
                claim.id,
                status=CommunityClaimStatus.VERIFIED,
                reviewer_user_id=self.bot.user.id
                if self.bot.user
                else self.bot.services.settings.owner_user_id,
                note=evidence_note[:2000],
            )
            await self._note_contribution(claim)
            await self.bot.services.cache.invalidate_all()
            return claim
        if quiet:
            if assessment.verdict == "contradicted":
                explanation = (
                    f"The evidence I found conflicts with this claim: {assessment.summary}\n"
                    + "\n".join(f"- {e.explanation} ({e.url})" for e in assessment.evidence[:2])
                    + "\nI may be missing context. Reply with your mode, test conditions "
                    "and findings to appeal."
                )
            else:
                explanation = (
                    "I couldn't verify the whole claim yet. Could you clarify the game mode, "
                    "conditions, exceptions and a current source or reproducible test? "
                    "I've queued it for review; it isn't being used as fact."
                )
            await message.reply(
                explanation[:1950],
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        try:
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="answer.community_claim_submitted",
                    actor_id=message.author.id,
                    target_type="community_claim",
                    target_id=str(claim.id),
                    reason="Substantial factual follow-up queued for experienced-member review",
                    details={
                        "game_version": claim.game_version,
                        "risk_flag": claim.risk_flag,
                    },
                )
            )
        except Exception:
            self.log.exception("community_claim_submission_audit_failed", claim_id=str(claim.id))
        channel = discord.utils.get(message.guild.text_channels, name=names.TECHNICIAN_LAB)
        if channel is None:
            self.log.warning("community_claim_review_channel_missing", claim_id=str(claim.id))
            return claim
        try:
            review_message = await channel.send(
                embed=self._pending_embed(claim),
                view=CommunityClaimReviewView(self.bot),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await self.bot.services.community_claims.set_review_message(claim.id, review_message.id)
        except Exception:
            self.log.exception("community_claim_review_post_failed", claim_id=str(claim.id))
        return claim

    async def _note_contribution(self, claim: CommunityClaim) -> None:
        if claim.submitter_user_id is None:
            return
        if await self.bot.services.profiles.learning_opted_out(claim.submitter_user_id):
            return
        await self.bot.services.profiles.update_answer_profile(
            claim.submitter_user_id,
            MemberProfileUpdate(
                profile_notes_add=(
                    "Experience: contributed independently reviewed Division 2 knowledge. "
                    "This is not a blanket expertise rating or review permission.",
                )
            ),
        )

    async def authorize_review(self, interaction: discord.Interaction) -> bool:
        if (
            interaction.guild_id != self.bot.services.settings.discord_guild_id
            or not isinstance(interaction.user, discord.Member)
            or not is_maintenance_operator(
                interaction.user, self.bot.services.settings.owner_user_id
            )
        ):
            await interaction.response.send_message(
                "Only Technicians, Division Commanders, and the configured owner can "
                "review community claims.",
                ephemeral=True,
            )
            return False
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "ERIN is in maintenance mode; the claim was not changed.", ephemeral=True
            )
            return False
        return True

    async def resolve_claim(
        self,
        review_message: discord.Message,
        *,
        reviewer: discord.abc.User,
        status: CommunityClaimStatus,
        note: str | None,
    ) -> str:
        claim_id = self._claim_id(review_message)
        if claim_id is None:
            return "That message is not an ERIN community-claim review."
        try:
            claim = await self.bot.services.community_claims.review(
                claim_id,
                status=status,
                reviewer_user_id=reviewer.id,
                note=note,
            )
        except KeyError:
            return "That community claim no longer exists."
        except (ClaimStateConflictError, ValueError) as exc:
            return str(exc)

        if status in {CommunityClaimStatus.VERIFIED, CommunityClaimStatus.QUALIFIED}:
            await self._note_contribution(claim)
        await self.bot.services.cache.invalidate_all()

        try:
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="knowledge.community_claim_reviewed",
                    actor_id=reviewer.id,
                    target_type="community_claim",
                    target_id=str(claim.id),
                    reason=note or "Experienced reviewer confirmed the claim without qualification",
                    details={
                        "status": status.value,
                        "game_version": claim.game_version,
                        "reusable": status.value in {"verified", "qualified"},
                    },
                )
            )
        except Exception:
            self.log.exception("community_claim_review_audit_failed", claim_id=str(claim.id))
        try:
            await review_message.edit(
                embed=self._resolved_embed(claim, reviewer),
                view=None,
            )
        except (discord.Forbidden, discord.HTTPException):
            self.log.exception(
                "community_claim_review_message_update_failed", claim_id=str(claim.id)
            )
        return self._resolution_reply(status)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.services.settings.discord_guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.name != names.TECHNICIAN_LAB
            or message.reference is None
            or not isinstance(message.author, discord.Member)
            or not is_maintenance_operator(message.author, self.bot.services.settings.owner_user_id)
        ):
            return
        referenced = message.reference.resolved
        if not isinstance(referenced, discord.Message) and message.reference.message_id:
            try:
                referenced = await message.channel.fetch_message(message.reference.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if not isinstance(referenced, discord.Message) or self._claim_id(referenced) is None:
            return
        if self.bot.services.maintenance.halted:
            await message.reply(
                "ERIN is in maintenance mode; the claim was not changed.",
                mention_author=False,
            )
            return
        decision = infer_claim_review_reply(message.content)
        if decision is None:
            await message.reply(
                "Reply `Yes`, `Yes, but …`, or `No, …`. Incorrect, bug, and exploit "
                "decisions require an explanation.",
                mention_author=False,
            )
            return
        result = await self.resolve_claim(
            referenced,
            reviewer=message.author,
            status=decision.status,
            note=decision.note,
        )
        await message.reply(result, mention_author=False)

    @staticmethod
    def _claim_id(message: discord.Message) -> UUID | None:
        if not message.embeds or message.embeds[0].footer is None:
            return None
        return claim_id_from_footer(message.embeds[0].footer.text)

    @staticmethod
    def _pending_embed(claim: CommunityClaim) -> discord.Embed:
        risk_note = (
            "\n\n⚠️ This submission mentions a possible bug, glitch, or exploit. "
            "Do not approve it unless the legitimate behavior is clearly qualified."
            if claim.risk_flag
            else ""
        )
        embed = discord.Embed(
            title="Community claim awaiting verification",
            description=(
                f"**{claim.member_label} says:**\n{claim.claim_text}\n\n"
                f"Is this accurate for **{claim.game_version}**?{risk_note}"
            )[:4000],
            colour=discord.Colour.orange(),
            timestamp=datetime.now(UTC),
            url=claim.source_url,
        )
        embed.add_field(name="Original question", value=claim.source_question[:1024], inline=False)
        embed.add_field(
            name="ERIN's prior answer (excerpt)",
            value=claim.prior_answer_excerpt[:1024],
            inline=False,
        )
        embed.set_footer(text=f"Community claim {claim.id}")
        return embed

    @staticmethod
    def _resolved_embed(claim: CommunityClaim, reviewer: discord.abc.User) -> discord.Embed:
        status = CommunityClaimStatus(claim.status)
        title, colour = {
            CommunityClaimStatus.VERIFIED: (
                "Community claim verified — added to ERIN memory",
                discord.Colour.green(),
            ),
            CommunityClaimStatus.QUALIFIED: (
                "Community claim verified with qualification",
                discord.Colour.green(),
            ),
            CommunityClaimStatus.INCORRECT: (
                "Community claim rejected",
                discord.Colour.light_grey(),
            ),
            CommunityClaimStatus.BUG: (
                "Community claim excluded — bug or unintended behavior",
                discord.Colour.red(),
            ),
            CommunityClaimStatus.EXPLOIT: (
                "Community claim excluded — exploit",
                discord.Colour.dark_red(),
            ),
        }[status]
        embed = discord.Embed(
            title=title,
            description=f"**Submitted claim:**\n{claim.claim_text}"[:4000],
            colour=colour,
            timestamp=claim.reviewed_at,
            url=claim.source_url,
        )
        result = claim.review_note or "Confirmed as accurate without qualification."
        embed.add_field(name="Review result", value=result[:1024], inline=False)
        reviewer_label = " ".join(reviewer.display_name.split())[:80]
        embed.add_field(name="Reviewed by", value=reviewer_label, inline=False)
        embed.set_footer(text=f"Community claim {claim.id}")
        return embed

    @staticmethod
    def _resolution_reply(status: CommunityClaimStatus) -> str:
        if status is CommunityClaimStatus.VERIFIED:
            return "Claim verified and added to ERIN's reusable Red Horizon memory."
        if status is CommunityClaimStatus.QUALIFIED:
            return "Qualified claim saved; ERIN will apply the reviewer limitation."
        if status is CommunityClaimStatus.BUG:
            return (
                "Claim marked as a bug or unintended interaction and excluded from recommendations."
            )
        if status is CommunityClaimStatus.EXPLOIT:
            return "Claim marked as an exploit and excluded from recommendations."
        return "Claim rejected and excluded from ERIN's reusable memory."

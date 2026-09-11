from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import discord
import structlog
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select

from rwi_bot.bot import names
from rwi_bot.bot.checks import is_maintenance_operator
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import CATEGORY_CHANNELS, ServerReconciler
from rwi_bot.cogs.community_learning import CommunityLearningCog
from rwi_bot.db.models import CommunityClaim, CommunityLoadout, KnowledgeEntry
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.community_learning import CommunityClaimProposal, infer_community_claim
from rwi_bot.services.experience import (
    ExperienceRepository,
    endorsement_target,
    self_reported_labels,
)
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.member_profiles import detect_possible_personal_information
from rwi_bot.services.observation import KnowledgeVerifier


class KnowledgeObservationCog(commands.Cog):
    """Private opt-in knowledge intake and bounded, creator-only knowledge audits."""

    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("knowledge_observation")
        self._lock = asyncio.Lock()
        self._intake_lock = asyncio.Lock()
        self._passive_lock = asyncio.Lock()
        self.path = bot.services.settings.runtime_dir / "knowledge-awareness.json"

    async def is_experienced(self, user_id: int) -> bool:
        if await self.bot.services.profiles.learning_opted_out(user_id):
            return False
        return await ExperienceRepository(self.bot.services.database).experienced(
            self.bot.services.settings.discord_guild_id,
            user_id,
            game_version=self.bot.services.qa.current_game_version,
        )

    async def maybe_record_endorsement(self, message: discord.Message) -> bool:
        endorsement = endorsement_target(message.content)
        if endorsement is None:
            return False
        if self.bot.services.maintenance.halted or detect_possible_personal_information(
            message.content
        ):
            return True
        if await self.bot.services.profiles.learning_opted_out(message.author.id):
            return True
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return True
        for target in message.mentions:
            if target.bot or target.id == message.author.id or target.id != endorsement[0]:
                continue
            try:
                await guild.fetch_member(target.id)
            except discord.HTTPException:
                continue
            if await self.bot.services.profiles.learning_opted_out(target.id):
                continue
            await ExperienceRepository(self.bot.services.database).endorse(
                guild_id=guild.id,
                sponsor_id=message.author.id,
                target_id=target.id,
                note=f"Peer endorsement (not independently verified): {endorsement[1]}",
                message_id=message.id,
            )
        return True

    @app_commands.command(
        name="experience-review",
        description="Privately inspect or verify a member's experience endorsements",
    )
    @app_commands.guild_only()
    async def experience_review(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        verified: bool | None = None,
        reason: str | None = None,
    ) -> None:
        if (
            interaction.guild_id != self.bot.services.settings.discord_guild_id
            or not isinstance(interaction.user, discord.Member)
            or not is_maintenance_operator(
                interaction.user, self.bot.services.settings.owner_user_id
            )
        ):
            await interaction.response.send_message(
                "Only the owner and authorized reviewers can inspect or verify "
                "experience endorsements.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        if (
            self.bot.services.maintenance.halted
            or await self.bot.services.profiles.learning_opted_out(member.id)
        ):
            await interaction.followup.send(
                "Experience review is unavailable for this member or while ERIN is halted.",
                ephemeral=True,
            )
            return
        repository = ExperienceRepository(self.bot.services.database)
        guild_id = self.bot.services.settings.discord_guild_id
        if verified is not None:
            if member.id == interaction.user.id or not reason or len(reason.strip()) < 8:
                await interaction.followup.send(
                    "Use an independent reviewer and provide a substantive reason.", ephemeral=True
                )
                return
            if detect_possible_personal_information(reason):
                await interaction.followup.send(
                    "Keep the review reason game-related; remove personal information.",
                    ephemeral=True,
                )
                return
            await repository.review(
                guild_id=guild_id,
                target_id=member.id,
                reviewer_id=interaction.user.id,
                verified=verified,
                note=sanitize_for_technicians(reason),
            )
            await interaction.followup.send(
                "Private experience review saved. This does not grant permissions or "
                "bypass evidence checks.",
                ephemeral=True,
            )
            return
        endorsements = await repository.endorsements(guild_id, member.id)
        lines = [f"Verified experience: {await repository.verified(guild_id, member.id)}"]
        experienced = await repository.experienced(
            guild_id, member.id, game_version=self.bot.services.qa.current_game_version
        )
        lines.append(f"Recognized experience (reviewed or demonstrated): {experienced}")
        observations = await repository.observations(guild_id, member.id)
        lines += [f"{o.label} ({o.provenance}; {o.status})" for o in observations[:10]]
        lines += [f"Sponsor {e.sponsor_id}: {e.note}" for e in endorsements[:3]]
        await interaction.followup.send(
            "\n".join(lines)[:1900], ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    async def ensure_space(self) -> None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return
        spec = next(
            spec
            for spec in CATEGORY_CHANNELS[names.ADMINISTRATION]
            if spec.name == names.ERIN_KNOWLEDGE
        )
        await ServerReconciler(guild).ensure_channel(names.ADMINISTRATION, spec)
        # Defense in depth: no bot messages/reactions/deletions in general channels.
        if guild.me is not None:
            for channel in guild.text_channels:
                if not names.is_passive_general(channel):
                    continue
                overwrite = channel.overwrites_for(guild.me)
                expected = discord.PermissionOverwrite.from_pair(*overwrite.pair())
                expected.update(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    add_reactions=False,
                    manage_messages=False,
                    manage_threads=False,
                )
                if expected != overwrite:
                    await channel.set_permissions(
                        guild.me,
                        overwrite=expected,
                        reason="ERIN observes general chat without responding or moderating",
                    )

    def schedule_start(self) -> None:
        if (
            self.bot.services.settings.autonomous_research_enabled
            and not self.scan_knowledge.is_running()
        ):
            self.scan_knowledge.start()

    async def cog_unload(self) -> None:
        self.scan_knowledge.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
            not message.author.bot
            and message.guild is not None
            and message.guild.id == self.bot.services.settings.discord_guild_id
            and not getattr(message.channel, "nsfw", False)
            and not (
                isinstance(message.channel, discord.Thread)
                and getattr(message.channel.parent, "nsfw", False)
            )
        ):
            if await self.maybe_record_endorsement(message):
                return
            if names.is_passive_general(message.channel):
                try:
                    await self.observe_general(message)
                except Exception:
                    self.log.exception("passive_observation_failed")
                return  # Never reply, ticket, DM, moderate or run commands in general chat.
        if (
            message.author.bot
            or self.bot.services.maintenance.halted
            or message.guild is None
            or message.guild.id != self.bot.services.settings.discord_guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.name != names.ERIN_KNOWLEDGE
            or not isinstance(message.author, discord.Member)
            or not is_maintenance_operator(message.author, self.bot.services.settings.owner_user_id)
        ):
            return
        if not message.content.strip():
            await message.reply(
                "Please include the gameplay claim in text with its conditions and source.",
                mention_author=False,
            )
            return
        if len(message.content.strip()) < 24:
            await message.reply(
                "Please include the complete claim or appeal, including the condition you tested.",
                mention_author=False,
            )
            return
        context = "Unprompted Division 2 knowledge submission."
        if message.reference and message.reference.message_id:
            try:
                original = await message.channel.fetch_message(message.reference.message_id)
                context = (
                    "Appeal/additional context; earlier statement may be wrong: "
                    + sanitize_for_technicians(original.content)[:1000]
                )
            except discord.HTTPException:
                pass
        learning = cast(CommunityLearningCog | None, self.bot.get_cog("CommunityLearningCog"))
        if learning is None:
            return
        async with self._intake_lock:
            await learning.submit_candidate(
                message,
                proposal=CommunityClaimProposal(
                    message.content,
                    "possible_bug_or_exploit"
                    if any(
                        word in message.content.casefold() for word in ("exploit", "glitch", "bug")
                    )
                    else None,
                ),
                member_label=message.author.display_name,
                source_question=context,
                prior_answer_excerpt=(
                    "No earlier ERIN answer; independently assess this submission."
                ),
                quiet=True,
            )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if (
            before.content == after.content
            or after.guild is None
            or after.guild.id != self.bot.services.settings.discord_guild_id
        ):
            return
        await ExperienceRepository(self.bot.services.database).withdraw_message(
            after.guild.id, after.id
        )
        changed = await self.bot.services.community_claims.withdraw_source(after.guild.id, after.id)
        if changed:
            await self.bot.services.cache.invalidate_all()
            if names.is_passive_general(after.channel):
                return
            await after.reply(
                "The source was edited, so its earlier knowledge contribution is no longer "
                "active. Please repost the complete revised claim for a fresh check.",
                mention_author=False,
            )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id != self.bot.services.settings.discord_guild_id:
            return
        await ExperienceRepository(self.bot.services.database).withdraw_message(
            payload.guild_id, payload.message_id
        )
        if await self.bot.services.community_claims.withdraw_source(
            payload.guild_id, payload.message_id
        ):
            await self.bot.services.cache.invalidate_all()

    async def observe_general(self, message: discord.Message) -> None:
        """Quiet, bounded assessment of advice; no raw message history or public labels."""
        if (
            self.bot.services.maintenance.halted
            or message.guild is None
            or message.webhook_id is not None
            or not self.bot.services.settings.autonomous_research_enabled
            or not 12 <= len(message.content) <= 2000
            or self._passive_lock.locked()
            or detect_possible_personal_information(message.content)
            or await self.bot.services.profiles.learning_opted_out(message.author.id)
        ):
            return
        repository = ExperienceRepository(self.bot.services.database)
        version = self.bot.services.qa.current_game_version
        async with self._passive_lock:
            for label in self_reported_labels(message.content):
                await repository.record(
                    guild_id=message.guild.id,
                    target_id=message.author.id,
                    message_id=message.id,
                    label=label,
                    provenance="self_reported",
                    game_version=version,
                )
            proposal = infer_community_claim(message.content, prompted=True)
            if proposal is None or proposal.risk_flag:
                return
            clean = sanitize_for_technicians(proposal.claim_text)
            context = (
                "Division 2 general-chat advice. Validate all material claims and "
                "practical conditions. Non-gameplay chatter is unresolved, not advice."
            )
            if message.reference and message.reference.message_id:
                try:
                    question = await message.channel.fetch_message(message.reference.message_id)
                    if (
                        not question.author.bot
                        and not detect_possible_personal_information(question.content)
                        and not await self.bot.services.profiles.learning_opted_out(
                            question.author.id
                        )
                    ):
                        context += (
                            " Question being answered (untrusted): "
                            + sanitize_for_technicians(question.content)[:750]
                        )
                except discord.HTTPException:
                    pass
            identifier = await repository.record(
                guild_id=message.guild.id,
                target_id=message.author.id,
                message_id=message.id,
                label="Helpful gameplay advice",
                provenance="observed_advice",
                game_version=version,
                claim=clean,
            )
            if identifier is None:
                return  # Persistent six/day global, two/day per person; duplicate claims excluded.
            assessment = await KnowledgeVerifier(
                self.bot.services.ai, self.bot.services.knowledge
            ).check(
                clean,
                context=context,
                game_version=version,
                since=self.bot.services.qa.current_game_version_started_on.isoformat(),
                actor_id=message.author.id,
            )
            if await self.bot.services.profiles.learning_opted_out(
                message.author.id
            ) or detect_possible_personal_information(assessment.summary):
                await repository.withdraw_message(message.guild.id, message.id)
                return
            await repository.finish(
                identifier,
                status=assessment.verdict,
                summary=assessment.summary,
                source_urls=[str(e.url) for e in assessment.evidence],
            )

    async def route_sensitive(self, message: discord.Message) -> str:
        owner_id = self.bot.services.settings.owner_user_id
        if message.author.id == owner_id:
            return (
                "You are my creator and sole programmer. For sensitive code or knowledge changes, "
                "please use your private development workspace; I won't expose internals in chat."
            )
        # Do not forward a member's DM contents, personal data or pasted secrets.
        try:
            owner = await self.bot.fetch_user(owner_id)
            await owner.send(
                f"A member (<@{message.author.id}>) asked about ERIN's private programming "
                f"or knowledge internals. "
                "Please contact them directly. Their message content was not forwarded.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            return (
                "Whiplash861 is my creator and sole programmer. Please DM them about sensitive "
                "code or knowledge questions; I couldn't deliver the private notification."
            )
        return (
            "Whiplash861 is my creator and sole programmer. I sent them a private contact "
            "request without forwarding your message contents. Please discuss sensitive "
            "details with them in DMs."
        )

    @tasks.loop(hours=6, reconnect=True)
    async def scan_knowledge(self) -> None:
        if self.bot.services.maintenance.halted:
            return
        try:
            await self.scan_once()
        except Exception:
            self.log.exception("awareness_scan_failed")

    @scan_knowledge.before_loop
    async def before_scan(self) -> None:
        await self.bot.wait_until_ready()

    async def scan_once(self) -> int:
        async with self._lock:
            state: dict[str, Any] = {}
            if self.path.exists():
                try:
                    state = json.loads(
                        await asyncio.to_thread(self.path.read_text, encoding="utf-8")
                    )
                except (ValueError, OSError):
                    self.log.warning("awareness_state_unreadable")
                    return 0  # No notification flood when a state file is damaged.
            now = datetime.now(UTC)
            if state.get("last_run") and now - datetime.fromisoformat(
                state["last_run"]
            ) < timedelta(hours=6):
                return 0
            qa = self.bot.services.qa
            async with self.bot.services.database.session() as session:
                entries = list(
                    await session.scalars(
                        select(KnowledgeEntry).where(KnowledgeEntry.status == "active")
                    )
                )
                claims = list(
                    await session.scalars(
                        select(CommunityClaim).where(
                            CommunityClaim.status.in_(["verified", "qualified"])
                        )
                    )
                )
                loadouts = list(
                    await session.scalars(
                        select(CommunityLoadout).where(CommunityLoadout.active.is_(True))
                    )
                )
            candidates = []
            for entry in entries:
                candidates.append(
                    (
                        f"entry:{entry.id}",
                        entry.subject,
                        json.dumps(entry.content, default=str),
                        entry.game_version or "unknown",
                    )
                )
            for claim in claims:
                candidates.append(
                    (
                        f"claim:{claim.id}",
                        claim.source_question,
                        claim.claim_text + "\n" + (claim.review_note or ""),
                        claim.game_version,
                    )
                )
            for loadout in loadouts:
                candidates.append(
                    (f"loadout:{loadout.id}", loadout.title, loadout.content, loadout.game_version)
                )
            checked = state.setdefault("checked", {})
            flags = state.setdefault("flags", {})
            # Oldest/never checked first, not only frequently retrieved entries.
            candidates.sort(key=lambda item: checked.get(item[0], ""))
            verifier = KnowledgeVerifier(self.bot.services.ai, self.bot.services.knowledge)
            count = 0
            for key, subject, content, version in candidates:
                if count >= 8 or self.bot.services.maintenance.halted:
                    break
                if checked.get(key) and now - datetime.fromisoformat(checked[key]) < timedelta(
                    days=7
                ):
                    continue
                clean = sanitize_for_technicians(content)[:2000]
                if detect_possible_personal_information(clean):
                    checked[key] = now.isoformat()
                    continue
                assessment = await verifier.check(
                    clean,
                    context=f"Audit existing knowledge: {subject}; stored version {version}",
                    game_version=qa.current_game_version,
                    since=qa.current_game_version_started_on.isoformat(),
                    actor_id=self.bot.services.settings.owner_user_id,
                )
                if assessment.check_failed:
                    break  # An unavailable/budget-blocked check is not a factual disagreement.
                count += 1
                fingerprint = hashlib.sha256(f"{version}:{content}".encode()).hexdigest()
                if assessment.verdict != "corroborated" and flags.get(key) != fingerprint:
                    embed = discord.Embed(
                        title="ERIN knowledge check — your review requested",
                        color=discord.Color.orange(),
                    )
                    embed.description = (
                        f"**Topic:** {subject[:180]}\n**Stored claim:** {clean[:750]}\n\n"
                        f"**Why flagged:** {assessment.summary[:600]}\n"
                        "Is this still valid, or does it need updating? Reply with mode, "
                        "conditions and evidence. "
                        "I may be missing context; this flag alone has not rewritten the knowledge."
                    )
                    if assessment.evidence:
                        embed.add_field(
                            name="Evidence checked",
                            value="\n".join(str(e.url) for e in assessment.evidence[:3])[:1000],
                            inline=False,
                        )
                    embed.set_footer(text=f"ERIN_AWARENESS:{key}")
                    owner = await self.bot.fetch_user(self.bot.services.settings.owner_user_id)
                    await owner.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    flags[key] = fingerprint
                    # Persist each delivery so later failures cannot resend earlier flags.
                checked[key] = now.isoformat()
                await self._save(state)
            state["last_run"] = now.isoformat()
            await self._save(state)
            self.log.info("awareness_scan_complete", examined=count, inventory=len(candidates))
            return count

    async def _save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        await asyncio.to_thread(
            temporary.write_text, json.dumps(state, sort_keys=True), encoding="utf-8"
        )
        await asyncio.to_thread(temporary.replace, self.path)

    async def handle_owner_review(self, message: discord.Message) -> bool:
        if message.author.id != self.bot.services.settings.owner_user_id or not message.reference:
            return False
        if not message.reference.message_id or self.bot.user is None:
            return False
        try:
            original = await message.channel.fetch_message(message.reference.message_id)
        except (discord.HTTPException, AttributeError):
            return False
        if original.author.id != self.bot.user.id or not original.embeds:
            return False
        marker = original.embeds[0].footer.text or ""
        if not marker.startswith("ERIN_AWARENESS:"):
            return False
        if detect_possible_personal_information(message.content):
            await message.reply(
                "Please resend only the game-related correction; I did not save the "
                "flagged details."
            )
            return True
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="knowledge.creator_review",
                actor_id=message.author.id,
                target_type="knowledge_awareness",
                target_id=marker.removeprefix("ERIN_AWARENESS:"),
                reason="Creator supplied context for a flagged knowledge item.",
                details={"game_context": sanitize_for_technicians(message.content)[:1800]},
            )
        )
        await message.reply(
            "I've recorded your clarification privately for this flagged item. It has not "
            "automatically overwritten the knowledge; a reviewed update is still needed if "
            "the stored claim should change."
        )
        return True

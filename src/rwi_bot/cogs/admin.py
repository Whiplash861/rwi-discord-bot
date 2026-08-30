from __future__ import annotations

from uuid import UUID

import discord
from discord import app_commands
from discord.ext import commands

from rwi_bot.bot.checks import is_commander, is_maintenance_operator
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import ServerReconciler
from rwi_bot.bot.views import ConfirmationView
from rwi_bot.data.red_horizon import (
    GAME_VERSION,
    OFFICIAL_SOURCE_URL,
    RED_HORIZON_SEEDS,
)
from rwi_bot.db.models import CacheState, KnowledgeStatus, TicketStatus
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.knowledge import (
    CacheStateConflictError,
    KnowledgeIdentityConflictError,
    KnowledgeRevisionConflictError,
    SourceMetadataConflictError,
    TicketStateConflictError,
    sanitize_for_technicians,
)
from rwi_bot.services.seeding import apply_red_horizon_seed, preview_red_horizon_seed
from rwi_bot.services.technician import (
    KnowledgeAction,
    KnowledgeChangeProposal,
    KnowledgeCreateProposal,
    parse_json_object,
    parse_source_evidence,
    propose_create,
    propose_revision,
    propose_rollback,
    render_create_proposal,
    render_proposal,
)


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
            content="ERIN is halted and displaying **Do Not Disturb — ERIN Maintenance Mode**.",
            view=None,
        )

    @rwi.command(name="status", description="Show maintenance, health, and budget state")
    async def status(self, interaction: discord.Interaction) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        state = self.bot.services.maintenance.state
        spent, limit = await self.bot.services.budget.utilization()
        breaker = await self.bot.services.ai.breaker.snapshot()
        status = "HALTED (Do Not Disturb)" if state.halted else "ONLINE"
        await interaction.response.send_message(
            f"**ERIN status:** {status}\n"
            f"**Reason:** {state.reason or 'None'}\n"
            f"**Changed:** {discord.utils.format_dt(state.changed_at, style='R')}\n"
            f"**State revision:** `{state.revision}`\n"
            f"**OpenAI breaker:** `{breaker.state.value}` "
            f"({breaker.recent_failures} recent failure(s))\n"
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
            heading = "ERIN remains halted because one or more critical checks failed."
        else:
            heading = "ERIN resumed successfully. Old queued requests were not replayed."
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
            releases = self.bot.get_cog("ReleaseNotesCog")
            if releases is not None:
                releases.schedule_publish()  # type: ignore[attr-defined]
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
        releases = self.bot.get_cog("ReleaseNotesCog")
        if releases is not None:
            releases.schedule_publish()  # type: ignore[attr-defined]
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

    @rwi.command(
        name="knowledge-history",
        description="Inspect the immutable revision history for a knowledge entry",
    )
    @app_commands.describe(entry_id="Knowledge entry UUID")
    async def knowledge_history(self, interaction: discord.Interaction, entry_id: str) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        parsed_entry_id = await self._parse_entry_id(interaction, entry_id)
        if parsed_entry_id is None:
            return
        entry = await self.bot.services.knowledge.get(parsed_entry_id)
        if entry is None:
            await interaction.response.send_message(
                "That knowledge entry does not exist.", ephemeral=True
            )
            return
        revisions = sorted(entry.revisions, key=lambda item: item.revision_number, reverse=True)
        lines = [
            f"**{entry.subject}** (`{entry.id}`)",
            f"Current revision: `{entry.current_revision}`",
            "",
        ]
        for revision in revisions[:12]:
            marker = " **(current)**" if revision.revision_number == entry.current_revision else ""
            actor = f"<@{revision.actor_id}>" if revision.actor_id is not None else "system"
            lines.append(
                f"`r{revision.revision_number}`{marker} · `{revision.status}` · "
                f"confidence `{revision.confidence}` · actor {actor} · "
                f"{discord.utils.format_dt(revision.created_at, style='R')}\n"
                f"Game version: `{revision.game_version or 'unspecified'}` · "
                f"Reason: {revision.reason[:240]}"
            )
        if len(revisions) > 12:
            lines.append(f"…and {len(revisions) - 12} older revision(s).")
        await interaction.response.send_message("\n".join(lines)[:1950], ephemeral=True)

    @rwi.command(
        name="knowledge-report",
        description="Show knowledge completeness, freshness, conflict, and queue health",
    )
    @app_commands.describe(stale_days="Treat active knowledge older than this as stale")
    async def knowledge_report(
        self,
        interaction: discord.Interaction,
        stale_days: app_commands.Range[int, 1, 365] = 30,
    ) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        report = await self.bot.services.knowledge.integrity_report(stale_after_days=stale_days)
        statuses = " · ".join(
            f"{status}: `{count}`" for status, count in sorted(report.status_counts.items())
        )
        await interaction.response.send_message(
            "**ERIN knowledge integrity report**\n\n"
            f"Total entries: `{report.total_entries}`\n"
            f"Statuses: {statuses or 'none'}\n"
            f"Active without linked sources: `{report.active_without_sources}`\n"
            f"Active without game version: `{report.active_without_game_version}`\n"
            f"Active below 0.750 confidence: `{report.active_low_confidence}`\n"
            f"Active not verified in {report.stale_after_days} days: "
            f"`{report.stale_active}`\n"
            f"Entries with mixed supporting/opposing evidence: "
            f"`{report.possible_source_conflicts}`\n"
            f"Open or investigating review tickets: `{report.open_review_tickets}`\n"
            f"Quarantined answer caches: `{report.quarantined_caches}`",
            ephemeral=True,
        )

    @rwi.command(
        name="knowledge-create",
        description="Propose and confirm a source-backed knowledge entry",
    )
    @app_commands.describe(
        subject="Human-readable item, system, activity, or topic name",
        entity_type="Stable type such as gear, weapon, talent, activity, or mechanic",
        claim_key="Stable claim key such as stats, acquisition, or interaction",
        content_json="Verified claim content as a JSON object",
        sources_json="JSON array of typed HTTPS source evidence objects",
        reason="Why this source-backed entry is being added",
        context_json="Scope such as mode or activity as a JSON object",
        status="Initial lifecycle status",
        game_version="Applicable patch or game version, when version-scoped",
        confidence="Initial confidence from 0 to 1",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name=status.value.title(), value=status.value)
            for status in (
                KnowledgeStatus.ACTIVE,
                KnowledgeStatus.CANDIDATE,
                KnowledgeStatus.DISPUTED,
            )
        ]
    )
    async def knowledge_create(
        self,
        interaction: discord.Interaction,
        subject: str,
        entity_type: str,
        claim_key: str,
        content_json: str,
        sources_json: str,
        reason: str,
        context_json: str = "{}",
        status: str = KnowledgeStatus.ACTIVE.value,
        game_version: str | None = None,
        confidence: app_commands.Range[float, 0.0, 1.0] = 0.9,
    ) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        try:
            proposal = propose_create(
                subject=subject,
                entity_type=entity_type,
                claim_key=claim_key,
                content=parse_json_object(content_json, field_name="content_json"),
                context=parse_json_object(context_json, field_name="context_json"),
                status=KnowledgeStatus(status),
                game_version=game_version,
                confidence=confidence,
                sources=parse_source_evidence(sources_json),
                reason=reason,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._confirm_knowledge_create(interaction, proposal)

    @rwi.command(
        name="seed-red-horizon",
        description="Preview and confirm the official Red Horizon knowledge baseline",
    )
    async def seed_red_horizon(self, interaction: discord.Interaction) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        preview = await preview_red_horizon_seed(self.bot.services.knowledge)
        if preview.missing == 0:
            await interaction.response.send_message(
                f"All `{preview.total}` official `{GAME_VERSION}` baseline entries already "
                "exist. Nothing was changed.",
                ephemeral=True,
            )
            return

        subjects = ", ".join(seed.subject for seed in RED_HORIZON_SEEDS)
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            f"Confirm the official **{GAME_VERSION}** baseline import.\n\n"
            f"- Source: [Ubisoft launch notes]({OFFICIAL_SOURCE_URL})\n"
            f"- Baseline entries: `{preview.total}`\n"
            f"- New entries: `{preview.missing}`\n"
            f"- Existing entries skipped: `{preview.existing}`\n"
            "- Policy: create-only; existing identities are never overwritten\n"
            "- Initial state: active, revision 1, source-backed\n\n"
            f"**Subjects:** {subjects}"[:1950],
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Red Horizon baseline import cancelled or confirmation expired.",
                view=None,
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="ERIN entered maintenance mode; no baseline entries were imported.",
                view=None,
            )
            return

        try:
            result = await apply_red_horizon_seed(
                self.bot.services.knowledge,
                actor_id=interaction.user.id,
            )
        except (SourceMetadataConflictError, ValueError) as exc:
            message = str(exc.args[0]) if exc.args else "The baseline import could not finish."
            await interaction.edit_original_response(
                content=f"{message} Run the command again to review the remaining entries.",
                view=None,
            )
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="knowledge.red_horizon_seeded",
                actor_id=interaction.user.id,
                target_type="knowledge_catalog",
                target_id=GAME_VERSION,
                reason="Confirmed official Red Horizon launch baseline import",
                details={
                    "source_url": OFFICIAL_SOURCE_URL,
                    "created_count": len(result.created_entry_ids),
                    "created_entry_ids": [str(entry_id) for entry_id in result.created_entry_ids],
                    "skipped_existing": result.skipped_existing,
                },
            )
        )
        await interaction.edit_original_response(
            content=(
                f"Imported `{len(result.created_entry_ids)}` official `{GAME_VERSION}` "
                f"entries; skipped `{result.skipped_existing}` identities that already existed."
            ),
            view=None,
        )

    @rwi.command(
        name="knowledge-revise",
        description="Propose and confirm a typed revision to a knowledge entry",
    )
    @app_commands.describe(
        entry_id="Knowledge entry UUID",
        content_json="Complete replacement content as a JSON object",
        reason="Why this verified change is needed",
        context_json="Replacement context JSON; omit to preserve it",
        status="Replacement lifecycle status; omit to preserve it",
        game_version="Replacement game version; omit to preserve it",
        clear_game_version="Remove the current game version instead of preserving it",
        confidence="Replacement confidence from 0 to 1; omit to preserve it",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name=status.value.title(), value=status.value)
            for status in KnowledgeStatus
        ]
    )
    async def knowledge_revise(
        self,
        interaction: discord.Interaction,
        entry_id: str,
        content_json: str,
        reason: str,
        context_json: str | None = None,
        status: str | None = None,
        game_version: str | None = None,
        clear_game_version: bool = False,
        confidence: app_commands.Range[float, 0.0, 1.0] | None = None,
    ) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        parsed_entry_id = await self._parse_entry_id(interaction, entry_id)
        if parsed_entry_id is None:
            return
        try:
            content = parse_json_object(content_json, field_name="content_json")
            context = (
                None
                if context_json is None
                else parse_json_object(context_json, field_name="context_json")
            )
            next_status = None if status is None else KnowledgeStatus(status)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        entry = await self.bot.services.knowledge.get(parsed_entry_id)
        if entry is None:
            await interaction.response.send_message(
                "That knowledge entry does not exist.", ephemeral=True
            )
            return
        try:
            proposal = propose_revision(
                entry,
                content=content,
                context=context,
                status=next_status,
                game_version=game_version,
                clear_game_version=clear_game_version,
                confidence=confidence,
                reason=reason,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._confirm_knowledge_change(interaction, proposal)

    @rwi.command(
        name="knowledge-rollback",
        description="Propose and confirm rollback by creating a new current revision",
    )
    @app_commands.describe(
        entry_id="Knowledge entry UUID",
        revision="Historical revision number to restore",
        reason="Why rollback is needed",
    )
    async def knowledge_rollback(
        self,
        interaction: discord.Interaction,
        entry_id: str,
        revision: app_commands.Range[int, 1],
        reason: str,
    ) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        parsed_entry_id = await self._parse_entry_id(interaction, entry_id)
        if parsed_entry_id is None:
            return
        entry = await self.bot.services.knowledge.get(parsed_entry_id)
        if entry is None:
            await interaction.response.send_message(
                "That knowledge entry does not exist.", ephemeral=True
            )
            return
        try:
            proposal = propose_rollback(
                entry,
                target_revision_number=revision,
                reason=reason,
            )
        except (KeyError, ValueError) as exc:
            message = str(exc.args[0]) if exc.args else "The rollback proposal is invalid."
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self._confirm_knowledge_change(interaction, proposal)

    @rwi.command(
        name="review-queue",
        description="Inspect privacy-sanitized unresolved and disputed answer tickets",
    )
    @app_commands.describe(limit="Maximum tickets to show")
    async def review_queue(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 20] = 12,
    ) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        tickets = await self.bot.services.tickets.review_queue(limit=limit)
        if not tickets:
            await interaction.response.send_message(
                "The Technician review queue is empty.", ephemeral=True
            )
            return
        lines = ["**Technician review queue**", ""]
        for ticket in tickets:
            question = " ".join(sanitize_for_technicians(ticket.sanitized_question).split())[:320]
            question = discord.utils.escape_mentions(question)
            lines.append(
                f"`{ticket.id}` · **{ticket.status}** · {ticket.duplicate_count} report(s) · "
                f"{discord.utils.format_dt(ticket.created_at, style='R')}\n> {question}"
            )
        await interaction.response.send_message("\n".join(lines)[:1950], ephemeral=True)

    @rwi.command(
        name="review-claim",
        description="Mark an open review ticket as under Technician investigation",
    )
    @app_commands.describe(ticket_id="Review ticket UUID")
    async def review_claim(self, interaction: discord.Interaction, ticket_id: str) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        parsed_ticket_id = await self._parse_uuid(interaction, ticket_id, field_name="ticket_id")
        if parsed_ticket_id is None:
            return
        try:
            await self.bot.services.tickets.claim(parsed_ticket_id)
        except (KeyError, TicketStateConflictError) as exc:
            message = str(exc.args[0]) if exc.args else "The review ticket could not be claimed."
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="knowledge.review_claimed",
                actor_id=interaction.user.id,
                target_type="unanswered_ticket",
                target_id=str(parsed_ticket_id),
                reason="Technician investigation started",
                details={
                    "from_status": TicketStatus.OPEN.value,
                    "to_status": TicketStatus.INVESTIGATING.value,
                },
            )
        )
        await interaction.response.send_message(
            "Review ticket marked as **investigating**.", ephemeral=True
        )

    @rwi.command(
        name="review-resolve",
        description="Resolve a review ticket against a verified knowledge entry",
    )
    @app_commands.describe(
        ticket_id="Review ticket UUID",
        entry_id="Knowledge entry UUID that resolves the question",
        note="Reproducible resolution summary without private member information",
    )
    async def review_resolve(
        self,
        interaction: discord.Interaction,
        ticket_id: str,
        entry_id: str,
        note: str,
    ) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        parsed_ticket_id = await self._parse_uuid(interaction, ticket_id, field_name="ticket_id")
        if parsed_ticket_id is None:
            return
        parsed_entry_id = await self._parse_entry_id(interaction, entry_id)
        if parsed_entry_id is None:
            return
        ticket = await self.bot.services.tickets.get(parsed_ticket_id)
        entry = await self.bot.services.knowledge.get(parsed_entry_id)
        if ticket is None or entry is None:
            missing = "review ticket" if ticket is None else "knowledge entry"
            await interaction.response.send_message(
                f"That {missing} does not exist.", ephemeral=True
            )
            return
        try:
            expected_status = TicketStatus(ticket.status)
        except ValueError:
            await interaction.response.send_message(
                f"Ticket status `{ticket.status}` cannot be resolved from this queue.",
                ephemeral=True,
            )
            return
        if expected_status not in (TicketStatus.OPEN, TicketStatus.INVESTIGATING):
            await interaction.response.send_message(
                f"Ticket status `{ticket.status}` cannot be resolved from this queue.",
                ephemeral=True,
            )
            return
        clean_note = sanitize_for_technicians(note)
        if not clean_note:
            await interaction.response.send_message(
                "A resolution note is required.", ephemeral=True
            )
            return
        question = discord.utils.escape_mentions(
            " ".join(sanitize_for_technicians(ticket.sanitized_question).split())[:500]
        )
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            f"Confirm review resolution.\n\n"
            f"- Ticket `{ticket.id}`: `{expected_status.value}` → `resolved`\n"
            f"- Knowledge entry: **{entry.subject}** (`{entry.id}`, revision "
            f"`{entry.current_revision}`)\n"
            f"- Resolution note: {clean_note[:500]}\n\n"
            f"> {question}",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Review resolution cancelled or confirmation expired.", view=None
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="ERIN entered maintenance mode; the review ticket was not changed.",
                view=None,
            )
            return
        try:
            await self.bot.services.tickets.resolve(
                ticket_id=parsed_ticket_id,
                entry_id=parsed_entry_id,
                resolution_note=clean_note,
                expected_status=expected_status,
            )
        except (KeyError, ValueError, TicketStateConflictError) as exc:
            message = str(exc.args[0]) if exc.args else "The review ticket could not be resolved."
            await interaction.edit_original_response(content=message, view=None)
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="knowledge.review_resolved",
                actor_id=interaction.user.id,
                target_type="unanswered_ticket",
                target_id=str(parsed_ticket_id),
                reason=clean_note,
                details={
                    "from_status": expected_status.value,
                    "to_status": TicketStatus.RESOLVED.value,
                    "resolved_entry_id": str(parsed_entry_id),
                    "resolved_entry_revision": entry.current_revision,
                },
            )
        )
        await interaction.edit_original_response(
            content="Review ticket resolved and linked to the verified knowledge entry.",
            view=None,
        )

    @rwi.command(
        name="cache-status",
        description="Inspect shared answer-cache state without displaying answer text",
    )
    @app_commands.describe(cache_id="Answer-cache UUID")
    async def cache_status(self, interaction: discord.Interaction, cache_id: str) -> None:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return
        parsed_cache_id = await self._parse_uuid(interaction, cache_id, field_name="cache_id")
        if parsed_cache_id is None:
            return
        cache = await self.bot.services.cache.get(parsed_cache_id)
        if cache is None:
            await interaction.response.send_message(
                "That answer cache does not exist.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"**Answer cache** `{cache.id}`\n"
            f"State: `{cache.state}`\n"
            f"Intent: `{cache.normalized_intent[:120]}`\n"
            f"Tier: `{cache.answer_tier}`\n"
            f"Dependencies: `{len(cache.dependency_revision_ids)}`\n"
            f"Citations: `{len(cache.citations)}`\n"
            f"Feedback: `+{cache.positive_feedback}` / `-{cache.negative_feedback}`\n"
            f"Expires: {discord.utils.format_dt(cache.expires_at, style='R')}",
            ephemeral=True,
        )

    @rwi.command(
        name="cache-quarantine",
        description="Confirm immediate quarantine of a suspect shared answer cache",
    )
    @app_commands.describe(
        cache_id="Answer-cache UUID",
        reason="Why this cached answer must no longer be served",
    )
    async def cache_quarantine(
        self,
        interaction: discord.Interaction,
        cache_id: str,
        reason: str,
    ) -> None:
        if not await self._knowledge_change_allowed(interaction):
            return
        parsed_cache_id = await self._parse_uuid(interaction, cache_id, field_name="cache_id")
        if parsed_cache_id is None:
            return
        clean_reason = sanitize_for_technicians(reason)
        if not clean_reason:
            await interaction.response.send_message(
                "A quarantine reason is required.", ephemeral=True
            )
            return
        cache = await self.bot.services.cache.get(parsed_cache_id)
        if cache is None:
            await interaction.response.send_message(
                "That answer cache does not exist.", ephemeral=True
            )
            return
        try:
            expected_state = CacheState(cache.state)
        except ValueError:
            await interaction.response.send_message(
                f"Cache state `{cache.state}` is not recognized; no change was made.",
                ephemeral=True,
            )
            return
        if expected_state == CacheState.QUARANTINED:
            await interaction.response.send_message(
                "That answer cache is already quarantined.", ephemeral=True
            )
            return
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            f"Confirm answer-cache quarantine.\n\n"
            f"- Cache: `{cache.id}`\n"
            f"- State: `{expected_state.value}` → `quarantined`\n"
            f"- Intent: `{cache.normalized_intent[:120]}`\n"
            f"- Reason: {clean_reason[:500]}\n\n"
            "The cached answer will stop being served immediately; verified knowledge is "
            "not changed.",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Cache quarantine cancelled or confirmation expired.", view=None
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="ERIN entered maintenance mode; the cache state was not changed.",
                view=None,
            )
            return
        try:
            await self.bot.services.cache.quarantine(
                parsed_cache_id,
                expected_state=expected_state,
            )
        except (KeyError, ValueError, CacheStateConflictError) as exc:
            message = str(exc.args[0]) if exc.args else "The cache could not be quarantined."
            await interaction.edit_original_response(content=message, view=None)
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="cache.technician_quarantined",
                actor_id=interaction.user.id,
                target_type="answer_cache",
                target_id=str(parsed_cache_id),
                reason=clean_reason,
                details={
                    "from_state": expected_state.value,
                    "to_state": CacheState.QUARANTINED.value,
                    "dependency_count": len(cache.dependency_revision_ids),
                    "citation_count": len(cache.citations),
                },
            )
        )
        await interaction.edit_original_response(
            content="Answer cache quarantined. Verified knowledge was not changed.",
            view=None,
        )

    async def _confirm_knowledge_create(
        self,
        interaction: discord.Interaction,
        proposal: KnowledgeCreateProposal,
    ) -> None:
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            discord.utils.escape_mentions(render_create_proposal(proposal)),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Knowledge creation cancelled or confirmation expired.", view=None
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="ERIN entered maintenance mode; the knowledge entry was not created.",
                view=None,
            )
            return
        try:
            entry_id = await self.bot.services.knowledge.add_candidate(
                subject=proposal.subject,
                entity_type=proposal.entity_type,
                claim_key=proposal.claim_key,
                content=proposal.content,
                context=proposal.context,
                actor_id=interaction.user.id,
                reason=proposal.reason,
                game_version=proposal.game_version,
                confidence=float(proposal.confidence),
                status=proposal.status,
                sources=proposal.sources,
            )
        except (
            KnowledgeIdentityConflictError,
            SourceMetadataConflictError,
            ValueError,
        ) as exc:
            message = str(exc.args[0]) if exc.args else "The knowledge entry could not be created."
            await interaction.edit_original_response(content=message, view=None)
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="knowledge.created",
                actor_id=interaction.user.id,
                target_type="knowledge_entry",
                target_id=str(entry_id),
                reason=proposal.reason,
                details={
                    "revision": 1,
                    "entity_type": proposal.entity_type,
                    "claim_key": proposal.claim_key,
                    "status": proposal.status.value,
                    "game_version": proposal.game_version,
                    "confidence": str(proposal.confidence),
                    "source_count": len(proposal.sources),
                    "supporting_source_count": sum(
                        source.supports_claim for source in proposal.sources
                    ),
                    "source_types": sorted(
                        {source.source_type.value for source in proposal.sources}
                    ),
                },
            )
        )
        await interaction.edit_original_response(
            content=(
                f"Knowledge entry `{entry_id}` created at revision `1` with "
                f"{len(proposal.sources)} immutable source snapshot(s)."
            ),
            view=None,
        )

    async def _confirm_knowledge_change(
        self,
        interaction: discord.Interaction,
        proposal: KnowledgeChangeProposal,
    ) -> None:
        view = ConfirmationView(interaction.user.id)
        await interaction.response.send_message(
            render_proposal(proposal),
            ephemeral=True,
            view=view,
        )
        await view.wait()
        if view.confirmed is not True:
            await interaction.edit_original_response(
                content="Knowledge change cancelled or confirmation expired.", view=None
            )
            return
        if self.bot.services.maintenance.halted:
            await interaction.edit_original_response(
                content="ERIN entered maintenance mode; the knowledge change was not applied.",
                view=None,
            )
            return
        try:
            if proposal.action == KnowledgeAction.REVISE:
                revision_id = await self.bot.services.knowledge.revise(
                    entry_id=proposal.entry_id,
                    actor_id=interaction.user.id,
                    content=proposal.content,
                    context=proposal.context,
                    status=proposal.status,
                    reason=proposal.reason,
                    game_version=proposal.game_version,
                    confidence=float(proposal.confidence),
                    expected_current_revision=proposal.expected_current_revision,
                )
                event_type = "knowledge.revised"
            else:
                assert proposal.target_revision_number is not None
                revision_id = await self.bot.services.knowledge.rollback(
                    entry_id=proposal.entry_id,
                    target_revision_number=proposal.target_revision_number,
                    actor_id=interaction.user.id,
                    reason=proposal.reason,
                    expected_current_revision=proposal.expected_current_revision,
                )
                event_type = "knowledge.rolled_back"
        except KnowledgeRevisionConflictError as exc:
            await interaction.edit_original_response(
                content=f"{exc} Run the command again to review the latest values.", view=None
            )
            return
        except (KeyError, ValueError) as exc:
            message = str(exc.args[0]) if exc.args else "The knowledge change could not be applied."
            await interaction.edit_original_response(content=message, view=None)
            return
        await self.bot.services.audit.record(
            AuditRecord(
                event_type=event_type,
                actor_id=interaction.user.id,
                target_type="knowledge_entry",
                target_id=str(proposal.entry_id),
                reason=proposal.reason,
                details={
                    "revision_id": str(revision_id),
                    "from_revision": proposal.expected_current_revision,
                    "to_revision": proposal.next_revision_number,
                    "rollback_target_revision": proposal.target_revision_number,
                    "status": proposal.status.value,
                    "game_version": proposal.game_version,
                    "confidence": str(proposal.confidence),
                    "diff": proposal.audit_diff(),
                },
            )
        )
        await interaction.edit_original_response(
            content=(
                f"Knowledge entry updated to revision `{proposal.next_revision_number}`. "
                "The immutable revision and audit event were recorded, and dependent caches "
                "were invalidated."
            ),
            view=None,
        )

    async def _knowledge_change_allowed(self, interaction: discord.Interaction) -> bool:
        if not self._maintenance_operator(interaction):
            await self._deny(interaction)
            return False
        if self.bot.services.maintenance.halted:
            await interaction.response.send_message(
                "Knowledge changes are disabled while ERIN is in maintenance mode.",
                ephemeral=True,
            )
            return False
        return True

    @staticmethod
    async def _parse_entry_id(interaction: discord.Interaction, entry_id: str) -> UUID | None:
        return await AdminCog._parse_uuid(interaction, entry_id, field_name="entry_id")

    @staticmethod
    async def _parse_uuid(
        interaction: discord.Interaction,
        value: str,
        *,
        field_name: str,
    ) -> UUID | None:
        try:
            return UUID(value.strip())
        except ValueError:
            message = f"{field_name} must be a valid UUID."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return None

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

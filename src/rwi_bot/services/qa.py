from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import structlog

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient, WebSearchScope
from rwi_bot.ai.prompts import SYSTEM_PROMPT_VERSION, compose_answer_input
from rwi_bot.domain.schemas import (
    AnswerRequest,
    AnswerResult,
    AuditRecord,
    ConfidenceLabel,
    IntentKind,
    SourceCitation,
)
from rwi_bot.services.audit import AuditService
from rwi_bot.services.budget import SpendingClass
from rwi_bot.services.community import CommunityLoadoutHit, CommunityLoadoutRepository
from rwi_bot.services.community_learning import (
    CommunityClaimRepository,
    community_claim_context,
)
from rwi_bot.services.knowledge import (
    CacheRepository,
    KnowledgeRepository,
    TicketRepository,
    knowledge_context,
    sanitize_for_technicians,
)
from rwi_bot.services.language import interpret_locally, question_signature
from rwi_bot.services.maintenance import MaintenanceManager
from rwi_bot.services.privacy import ProfileRepository

MAINTENANCE_MESSAGE = (
    "ERIN is in maintenance mode. I'm not accepting questions or starting external checks "
    "until a Technician or Division Commander resumes service."
)


class QuestionAnsweringService:
    def __init__(
        self,
        *,
        maintenance: MaintenanceManager,
        knowledge: KnowledgeRepository,
        cache: CacheRepository,
        tickets: TicketRepository,
        profiles: ProfileRepository,
        ai: RwiOpenAIClient,
        audit: AuditService,
        web_search_enabled: bool,
        community_loadouts: CommunityLoadoutRepository | None = None,
        community_claims: CommunityClaimRepository | None = None,
        current_game_version: str = "Y8S3 Red Horizon",
        current_game_version_started_on: date = date(2026, 8, 27),
    ) -> None:
        self.maintenance = maintenance
        self.knowledge = knowledge
        self.cache = cache
        self.tickets = tickets
        self.profiles = profiles
        self.ai = ai
        self.audit = audit
        self.web_search_enabled = web_search_enabled
        self.community_loadouts = community_loadouts
        self.community_claims = community_claims
        self.current_game_version = current_game_version
        self.current_game_version_started_on = current_game_version_started_on
        self.log = structlog.get_logger("qa")

    async def answer(self, request: AnswerRequest) -> AnswerResult:
        correlation_id = uuid4()
        if self.maintenance.halted:
            return AnswerResult(text=MAINTENANCE_MESSAGE, confidence=ConfidenceLabel.UNKNOWN)

        learning_opt_out = await self.profiles.learning_opted_out(request.user_id)
        interpreted = interpret_locally(request.question)
        if interpreted.intent is IntentKind.BUILD_ADVICE and self.community_loadouts is not None:
            try:
                community_hits = await self.community_loadouts.search(
                    interpreted.normalized_question,
                    guild_id=request.guild_id,
                    game_version=self.current_game_version,
                )
            except Exception:
                self.log.exception("community_loadout_search_failed")
            else:
                if community_hits:
                    await self.audit.record(
                        AuditRecord(
                            event_type="answer.community_loadout_match",
                            actor_id=request.user_id,
                            target_type="community_loadout",
                            correlation_id=correlation_id,
                            details={
                                "is_dm": request.is_dm,
                                "game_version": self.current_game_version,
                                "loadout_ids": [str(hit.loadout.id) for hit in community_hits],
                                "similarities": [
                                    round(hit.similarity, 3) for hit in community_hits
                                ],
                            },
                        )
                    )
                    return AnswerResult(
                        text=render_community_loadouts(
                            community_hits, game_version=self.current_game_version
                        ),
                        citations=[
                            SourceCitation(
                                title=hit.loadout.title,
                                url=hit.loadout.source_url,
                                source_type="community_loadout",
                                verified_at=hit.loadout.updated_at,
                                official=False,
                            )
                            for hit in community_hits
                        ],
                        assumptions=request.assumptions,
                        confidence=ConfidenceLabel.MEDIUM,
                        learning_opt_out=learning_opt_out,
                    )
        assumptions_dict = request.assumptions.model_dump(mode="json")
        effective_constraints = {
            **interpreted.constraints,
            "current_game_version": self.current_game_version,
        }
        signature = question_signature(
            interpreted.normalized_question,
            assumptions=assumptions_dict,
            constraints=effective_constraints,
        )
        community_claim_hits = []
        if self.community_claims is not None:
            try:
                community_claim_hits = await self.community_claims.search(
                    interpreted.normalized_question,
                    guild_id=request.guild_id,
                    game_version=self.current_game_version,
                )
            except Exception:
                self.log.exception("community_claim_search_failed")
            else:
                if community_claim_hits:
                    await self.audit.record(
                        AuditRecord(
                            event_type="answer.reviewed_community_claim_match",
                            actor_id=request.user_id,
                            target_type="community_claim",
                            correlation_id=correlation_id,
                            details={
                                "is_dm": request.is_dm,
                                "game_version": self.current_game_version,
                                "claim_ids": [str(hit.claim.id) for hit in community_claim_hits],
                                "similarities": [
                                    round(hit.similarity, 3) for hit in community_claim_hits
                                ],
                            },
                        )
                    )
        cached = (
            None if community_claim_hits else await self.cache.get_valid(signature, request.tier)
        )
        if cached is not None:
            await self.audit.record(
                AuditRecord(
                    event_type="answer.cache_hit",
                    actor_id=request.user_id,
                    target_type="answer_cache",
                    target_id=str(cached.id),
                    correlation_id=correlation_id,
                    details={
                        "is_dm": request.is_dm,
                        "tier": request.tier.value,
                        "learning_opt_out": learning_opt_out,
                    },
                )
            )
            return AnswerResult(
                text=cached.answer_text,
                citations=[SourceCitation.model_validate(item) for item in cached.citations],
                assumptions=request.assumptions,
                confidence=ConfidenceLabel.VERIFIED,
                cache_entry_id=cached.id,
                cache_hit=True,
                learning_opt_out=learning_opt_out,
            )

        hits = await self.knowledge.search(
            interpreted.normalized_question,
            game_version=self.current_game_version,
        )
        context, revision_ids, knowledge_citations = knowledge_context(hits)
        reviewed_context = community_claim_context(community_claim_hits)
        if reviewed_context:
            context = f"{context}\n\n{reviewed_context}" if context else reviewed_context
        complexity = (
            "complex"
            if interpreted.intent.value in {"build_advice", "build_rating", "mission_guide"}
            else "normal"
        )
        input_text = compose_answer_input(
            question=request.question,
            member_name=request.member_name,
            detail_tier=request.tier.value,
            assumptions=_format_assumptions(assumptions_dict),
            current_game_version=self.current_game_version,
            freshness_boundary=self.current_game_version_started_on.isoformat(),
            knowledge_context=context,
            conversation_summary=request.conversation_summary,
        )

        try:
            if hits or community_claim_hits:
                generated = await self.ai.answer(
                    input_text=input_text,
                    user_id=request.user_id,
                    correlation_id=correlation_id,
                    complexity=complexity,
                )
                citations = _merge_citations(knowledge_citations, generated.citations)
                confidence = ConfidenceLabel.HIGH
                used_web = False
            elif self.web_search_enabled:
                generated = await self.ai.answer(
                    input_text=input_text,
                    user_id=request.user_id,
                    correlation_id=correlation_id,
                    complexity=complexity,
                    web_search=True,
                    search_scope=WebSearchScope.CURATED,
                    spending_class=SpendingClass.MEMBER_ANSWER,
                )
                citations = generated.citations
                if not citations:
                    generated = await self.ai.answer(
                        input_text=input_text,
                        user_id=request.user_id,
                        correlation_id=correlation_id,
                        complexity=complexity,
                        web_search=True,
                        search_scope=WebSearchScope.OPEN,
                        spending_class=SpendingClass.MEMBER_ANSWER,
                    )
                    citations = generated.citations
                confidence = ConfidenceLabel.MEDIUM if citations else ConfidenceLabel.LOW
                used_web = True
            else:
                raise OpenAIUnavailableError("Web fallback is disabled and no knowledge matched.")
        except OpenAIUnavailableError as exc:
            ticket_id = await self._open_ticket(
                request,
                signature,
                correlation_id,
                str(exc),
                learning_opt_out=learning_opt_out,
            )
            return AnswerResult(
                text=(
                    "I couldn't verify that answer from ERIN's library right now. "
                    f"I opened Technician ticket `{ticket_id}` so it can be researched and added."
                ),
                assumptions=request.assumptions,
                confidence=ConfidenceLabel.UNKNOWN,
                ticket_id=ticket_id,
                learning_opt_out=learning_opt_out,
            )

        if not generated.text.strip():
            ticket_id = await self._open_ticket(
                request,
                signature,
                correlation_id,
                "The response contained no usable answer.",
                learning_opt_out=learning_opt_out,
            )
            return AnswerResult(
                text=(
                    "I couldn't verify a usable answer. "
                    f"Technician ticket `{ticket_id}` has been opened."
                ),
                assumptions=request.assumptions,
                confidence=ConfidenceLabel.UNKNOWN,
                ticket_id=ticket_id,
                learning_opt_out=learning_opt_out,
            )

        cache_entry_id = None
        if not learning_opt_out and not community_claim_hits:
            cache_entry_id = await self.cache.create_candidate(
                signature=signature,
                normalized_intent=interpreted.intent.value,
                entities=interpreted.entities,
                constraints=effective_constraints,
                assumptions=assumptions_dict,
                answer_text=generated.text,
                tier=request.tier,
                dependency_revision_ids=revision_ids,
                citations=citations,
                model_name=self.ai._select_model(complexity),
                prompt_version=SYSTEM_PROMPT_VERSION,
            )
        await self.audit.record(
            AuditRecord(
                event_type="answer.completed",
                actor_id=request.user_id,
                target_type="answer_cache" if cache_entry_id is not None else "answer",
                target_id=str(cache_entry_id) if cache_entry_id is not None else None,
                correlation_id=correlation_id,
                details={
                    "cache_hit": False,
                    "used_web_search": used_web,
                    "citation_count": len(citations),
                    "knowledge_revision_count": len(revision_ids),
                    "is_dm": request.is_dm,
                    "learning_opt_out": learning_opt_out,
                },
            )
        )
        return AnswerResult(
            text=generated.text,
            citations=citations,
            assumptions=request.assumptions,
            confidence=confidence,
            knowledge_revision_ids=revision_ids,
            cache_entry_id=cache_entry_id,
            used_web_search=used_web,
            learning_opt_out=learning_opt_out,
        )

    async def _open_ticket(
        self,
        request: AnswerRequest,
        signature: str,
        correlation_id: UUID,
        reason: str,
        *,
        learning_opt_out: bool,
    ) -> UUID:
        ticket_id = await self.tickets.open_or_increment(
            signature=signature,
            sanitized_question=sanitize_for_technicians(request.question),
            requester_user_id=None if learning_opt_out else request.user_id,
        )
        self.log.info(
            "unanswered_ticket",
            ticket_id=str(ticket_id),
            correlation_id=str(correlation_id),
            reason=reason,
        )
        await self.audit.record(
            AuditRecord(
                event_type="knowledge.unanswered_ticket",
                actor_id=request.user_id,
                target_type="unanswered_ticket",
                target_id=str(ticket_id),
                correlation_id=correlation_id,
                reason=reason,
                details={"is_dm": request.is_dm, "learning_opt_out": learning_opt_out},
            )
        )
        return ticket_id


def _format_assumptions(values: dict[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _merge_citations(
    first: list[SourceCitation], second: list[SourceCitation]
) -> list[SourceCitation]:
    merged: list[SourceCitation] = []
    seen: set[str] = set()
    for citation in [*first, *second]:
        key = str(citation.url)
        if key not in seen:
            seen.add(key)
            merged.append(citation)
    return merged


def render_community_loadouts(hits: list[CommunityLoadoutHit], *, game_version: str) -> str:
    lines = [
        f"I found {len(hits)} locally indexed community loadout(s) matching that description "
        f"for **{game_version}**. These are player-submitted builds.",
        "",
    ]
    for index, hit in enumerate(hits, start=1):
        loadout = hit.loadout
        title = loadout.title.replace("[", "\\[").replace("]", "\\]")
        tags = ", ".join(loadout.tags) if loadout.tags else "untagged"
        excerpt = " ".join(loadout.content.split())
        if len(excerpt) > 420:
            excerpt = excerpt[:419].rstrip() + "…"
        lines.extend(
            (
                f"**{index}. [{title}]({loadout.source_url})**",
                f"Tags: {tags} · Match: {hit.similarity:.0%}",
                f"> {excerpt}",
                "",
            )
        )
    lines.append(
        "I can use one of these as a starting point and adapt it to your inventory or role."
    )
    return "\n".join(lines)

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient
from rwi_bot.db.models import KnowledgeStatus, SourceType
from rwi_bot.domain.schemas import AuditRecord, GameResearchFinding, SourceCitation
from rwi_bot.services.audit import AuditService
from rwi_bot.services.knowledge import (
    CacheRepository,
    KnowledgeIdentityConflictError,
    KnowledgeRepository,
    SourceEvidence,
    SourceMetadataConflictError,
)
from rwi_bot.services.qa import QuestionAnsweringService


@dataclass(slots=True)
class AutonomyState:
    current_game_version: str
    season_started_on: str
    last_check_at: str | None = None
    last_full_sweep_at: str | None = None
    last_fingerprint: str | None = None
    last_status: str = "never_run"
    last_summary: str = "Autonomous research has not run yet."
    consecutive_failures: int = 0


@dataclass(frozen=True, slots=True)
class AutonomousResearchOutcome:
    correlation_id: UUID
    status: str
    summary: str
    full_sweep: bool
    season_changed: bool
    promoted: int
    staged: int
    duplicates: int
    citations: tuple[SourceCitation, ...]


class AutonomyStateStore:
    def __init__(
        self,
        path: Path,
        *,
        initial_game_version: str,
        initial_started_on: date,
    ) -> None:
        self.path = path
        self.initial_game_version = initial_game_version
        self.initial_started_on = initial_started_on

    async def load(self) -> AutonomyState:
        try:
            raw = await asyncio.to_thread(self.path.read_text, encoding="utf-8")
            data = json.loads(raw)
            state = AutonomyState(**data)
            if not state.current_game_version.strip() or len(state.current_game_version) > 80:
                raise ValueError("invalid persisted game version")
            date.fromisoformat(state.season_started_on)
            return state
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            return AutonomyState(
                current_game_version=self.initial_game_version,
                season_started_on=self.initial_started_on.isoformat(),
            )

    async def save(self, state: AutonomyState) -> None:
        await asyncio.to_thread(self.path.parent.mkdir, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = json.dumps(asdict(state), sort_keys=True, indent=2)
        await asyncio.to_thread(temporary.write_text, payload, encoding="utf-8")
        await asyncio.to_thread(temporary.replace, self.path)


class AutonomousResearchService:
    """Bounded autonomy for detecting and safely incorporating game changes."""

    def __init__(
        self,
        *,
        ai: RwiOpenAIClient,
        knowledge: KnowledgeRepository,
        cache: CacheRepository,
        qa: QuestionAnsweringService,
        audit: AuditService,
        state_store: AutonomyStateStore,
        owner_user_id: int,
        enabled: bool,
        full_sweep_hours: int,
        maximum_findings: int,
        auto_promote_official: bool,
    ) -> None:
        self.ai = ai
        self.knowledge = knowledge
        self.cache = cache
        self.qa = qa
        self.audit = audit
        self.state_store = state_store
        self.owner_user_id = owner_user_id
        self.enabled = enabled
        self.full_sweep_hours = full_sweep_hours
        self.maximum_findings = maximum_findings
        self.auto_promote_official = auto_promote_official
        self._state: AutonomyState | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> AutonomyState:
        state = await self.state_store.load()
        self.qa.set_current_game_version(
            state.current_game_version,
            date.fromisoformat(state.season_started_on),
        )
        self._state = state
        return state

    async def status(self) -> AutonomyState:
        if self._state is None:
            return await self.initialize()
        return self._state

    async def run_once(self, *, force_full: bool = False) -> AutonomousResearchOutcome:
        if not self.enabled:
            raise RuntimeError("Autonomous research is disabled.")
        async with self._lock:
            state = await self.status()
            now = datetime.now(UTC)
            full_sweep = force_full or self._full_sweep_due(state, now)
            correlation_id = uuid4()
            await self.audit.record(
                AuditRecord(
                    event_type="autonomy.research_started",
                    actor_id=self.owner_user_id,
                    target_type="game_update_watch",
                    target_id=str(correlation_id),
                    reason=(
                        "ERIN began a full cross-source game research sweep."
                        if full_sweep
                        else "ERIN began a scheduled current-game update check."
                    ),
                    correlation_id=correlation_id,
                    details={"full_sweep": full_sweep},
                )
            )
            try:
                result = await self.ai.research_game_updates(
                    current_game_version=state.current_game_version,
                    current_season_started_on=state.season_started_on,
                    full_sweep=full_sweep,
                    actor_id=self.owner_user_id,
                    correlation_id=correlation_id,
                    maximum_findings=self.maximum_findings,
                )
                outcome = await self._incorporate(
                    state,
                    result.report,
                    tuple(result.citations),
                    full_sweep=full_sweep,
                    correlation_id=correlation_id,
                    now=now,
                )
            except Exception as exc:
                state.last_check_at = now.isoformat()
                state.last_status = "failed"
                state.last_summary = f"Research failed: {type(exc).__name__}"
                state.consecutive_failures += 1
                await self.state_store.save(state)
                await self.audit.record(
                    AuditRecord(
                        event_type="autonomy.research_failed",
                        actor_id=self.owner_user_id,
                        target_type="game_update_watch",
                        target_id=str(correlation_id),
                        reason=(
                            "ERIN's scheduled research check failed without changing the "
                            "active knowledge base."
                        ),
                        correlation_id=correlation_id,
                        details={
                            "error_type": type(exc).__name__,
                            "consecutive_failures": state.consecutive_failures,
                        },
                    )
                )
                if isinstance(exc, OpenAIUnavailableError):
                    raise
                raise RuntimeError("Autonomous research failed safely.") from exc
            self._state = state
            return outcome

    async def _incorporate(
        self,
        state: AutonomyState,
        report: object,
        citations: tuple[SourceCitation, ...],
        *,
        full_sweep: bool,
        correlation_id: UUID,
        now: datetime,
    ) -> AutonomousResearchOutcome:
        from rwi_bot.domain.schemas import GameResearchReport

        if not isinstance(report, GameResearchReport):
            raise TypeError("research response was not a GameResearchReport")
        citation_by_url = {_normalize_url(str(item.url)): item for item in citations}
        official_urls = {
            _normalize_url(str(url))
            for url in report.official_evidence_urls
            if (citation := citation_by_url.get(_normalize_url(str(url)))) is not None
            and citation.official
        }
        fingerprint = _report_fingerprint(report.model_dump(mode="json"))
        season_changed = bool(
            report.change_detected
            and report.current_game_version != state.current_game_version
            and report.season_started_on is not None
            and report.season_started_on >= date.fromisoformat(state.season_started_on)
            and official_urls
        )
        next_game_version = (
            report.current_game_version if season_changed else state.current_game_version
        )
        next_started_on = (
            report.season_started_on
            if season_changed and report.season_started_on is not None
            else date.fromisoformat(state.season_started_on)
        )

        promoted = 0
        staged = 0
        duplicates = 0
        promoted_subjects: list[str] = []
        staged_subjects: list[str] = []
        if fingerprint != state.last_fingerprint:
            for finding in report.findings[: self.maximum_findings]:
                source_evidence = _source_evidence(finding, citation_by_url)
                if not source_evidence:
                    continue
                status = KnowledgeStatus.CANDIDATE
                if self._auto_promotable(
                    finding,
                    source_evidence,
                    active_started_on=next_started_on,
                ):
                    status = KnowledgeStatus.ACTIVE
                context = {
                    **finding.context,
                    "autonomous_research": True,
                    "evidence_class": finding.evidence_class,
                }
                try:
                    await self.knowledge.add_candidate(
                        subject=finding.subject,
                        entity_type=finding.entity_type,
                        claim_key=finding.claim_key,
                        content={**finding.content, "summary": finding.summary},
                        context=context,
                        actor_id=self.owner_user_id,
                        reason=(
                            "Auto-promoted from current official evidence."
                            if status == KnowledgeStatus.ACTIVE
                            else "Staged by autonomous research for Technician review."
                        ),
                        game_version=next_game_version,
                        confidence=finding.confidence,
                        status=status,
                        sources=source_evidence,
                    )
                except (KnowledgeIdentityConflictError, SourceMetadataConflictError):
                    duplicates += 1
                    continue
                if status == KnowledgeStatus.ACTIVE:
                    promoted += 1
                    promoted_subjects.append(finding.subject)
                else:
                    staged += 1
                    staged_subjects.append(finding.subject)

        next_state = AutonomyState(
            current_game_version=next_game_version,
            season_started_on=next_started_on.isoformat(),
            last_check_at=now.isoformat(),
            last_full_sweep_at=(now.isoformat() if full_sweep else state.last_full_sweep_at),
            last_fingerprint=fingerprint,
            last_status="completed",
            last_summary=report.summary,
            consecutive_failures=0,
        )
        await self.state_store.save(next_state)
        stale_cache_count = 0
        if season_changed:
            try:
                stale_cache_count = await self.cache.invalidate_all()
            except Exception:
                stale_cache_count = -1
            self.qa.set_current_game_version(next_game_version, next_started_on)
        _copy_state(next_state, state)
        event_type = (
            "autonomy.season_transition"
            if season_changed
            else "autonomy.no_change"
            if not report.change_detected and not promoted and not staged
            else "autonomy.research_completed"
        )
        await self.audit.record(
            AuditRecord(
                event_type=event_type,
                actor_id=self.owner_user_id,
                target_type="game_version",
                target_id=state.current_game_version,
                reason=report.summary,
                correlation_id=correlation_id,
                details={
                    "full_sweep": full_sweep,
                    "change_detected": report.change_detected,
                    "season_changed": season_changed,
                    "promoted_official_findings": promoted,
                    "staged_for_review": staged,
                    "duplicates_skipped": duplicates,
                    "stale_answer_caches": stale_cache_count,
                    "cache_invalidation_failed": stale_cache_count < 0,
                    "citation_count": len(citations),
                    "promoted_subjects": promoted_subjects[:10],
                    "staged_subjects": staged_subjects[:10],
                    "unresolved_questions": report.unresolved_questions[:10],
                },
            )
        )
        return AutonomousResearchOutcome(
            correlation_id=correlation_id,
            status="completed",
            summary=report.summary,
            full_sweep=full_sweep,
            season_changed=season_changed,
            promoted=promoted,
            staged=staged,
            duplicates=duplicates,
            citations=citations,
        )

    def _auto_promotable(
        self,
        finding: GameResearchFinding,
        sources: tuple[SourceEvidence, ...],
        *,
        active_started_on: date,
    ) -> bool:
        if not self.auto_promote_official:
            return False
        if finding.evidence_class != "official" or finding.confidence < 0.95:
            return False
        if not finding.material_change or not all(
            source.source_type == SourceType.OFFICIAL for source in sources
        ):
            return False
        try:
            published_on = date.fromisoformat(str(finding.context["published_on"]))
        except (KeyError, TypeError, ValueError):
            return False
        return published_on >= active_started_on

    def _full_sweep_due(self, state: AutonomyState, now: datetime) -> bool:
        if state.last_full_sweep_at is None:
            return True
        try:
            previous = datetime.fromisoformat(state.last_full_sweep_at)
        except ValueError:
            return True
        return now - previous >= timedelta(hours=self.full_sweep_hours)


def _source_evidence(
    finding: GameResearchFinding,
    citation_by_url: dict[str, SourceCitation],
) -> tuple[SourceEvidence, ...]:
    evidence: list[SourceEvidence] = []
    for source_url in finding.source_urls:
        citation = citation_by_url.get(_normalize_url(str(source_url)))
        if citation is None:
            continue
        evidence.append(
            SourceEvidence(
                url=str(citation.url),
                title=citation.title,
                source_type=(SourceType.OFFICIAL if citation.official else SourceType.COMMUNITY),
                trust_score=Decimal("0.980") if citation.official else Decimal("0.650"),
                publisher="Ubisoft" if citation.official else None,
                note=(
                    "Retrieved during guarded autonomous research; community evidence remains "
                    "review-gated."
                ),
            )
        )
    return tuple(evidence)


def _normalize_url(url: str) -> str:
    return url.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0].rstrip("/").casefold()


def _report_fingerprint(report: dict[str, object]) -> str:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _copy_state(source: AutonomyState, target: AutonomyState) -> None:
    target.current_game_version = source.current_game_version
    target.season_started_on = source.season_started_on
    target.last_check_at = source.last_check_at
    target.last_full_sweep_at = source.last_full_sweep_at
    target.last_fingerprint = source.last_fingerprint
    target.last_status = source.last_status
    target.last_summary = source.last_summary
    target.consecutive_failures = source.consecutive_failures

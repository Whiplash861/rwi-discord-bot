from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from rwi_bot.db.models import KnowledgeEntry, KnowledgeRevision, KnowledgeStatus, SourceType
from rwi_bot.services.knowledge import SourceEvidence, normalized_confidence

_SENSITIVE_QUERY_NAMES = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "password",
        "secret",
        "signature",
        "token",
    }
)


class KnowledgeAction(StrEnum):
    CREATE = "create"
    REVISE = "revise"
    ROLLBACK = "rollback"


@dataclass(frozen=True, slots=True)
class FieldChange:
    path: str
    before: Any
    after: Any

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "before": self.before, "after": self.after}


@dataclass(frozen=True, slots=True)
class KnowledgeChangeProposal:
    action: KnowledgeAction
    entry_id: UUID
    subject: str
    expected_current_revision: int
    changes: tuple[FieldChange, ...]
    reason: str
    content: dict[str, Any]
    context: dict[str, Any]
    status: KnowledgeStatus
    game_version: str | None
    confidence: Decimal
    target_revision_number: int | None = None

    @property
    def next_revision_number(self) -> int:
        return self.expected_current_revision + 1

    def audit_diff(self) -> list[dict[str, Any]]:
        return [change.as_dict() for change in self.changes]


@dataclass(frozen=True, slots=True)
class KnowledgeCreateProposal:
    subject: str
    entity_type: str
    claim_key: str
    content: dict[str, Any]
    context: dict[str, Any]
    status: KnowledgeStatus
    game_version: str | None
    confidence: Decimal
    sources: tuple[SourceEvidence, ...]
    reason: str


class _SourceEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    source_type: SourceType
    trust_score: float = Field(ge=0.0, le=1.0)
    publisher: str | None = Field(default=None, max_length=200)
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    supports_claim: bool = True
    note: str | None = Field(default=None, max_length=1000)


def parse_json_object(value: str, *, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{field_name} must be valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return parsed


def parse_source_evidence(value: str) -> tuple[SourceEvidence, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"sources_json must be valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError("sources_json must be a JSON array.")
    if not parsed:
        raise ValueError("At least one source is required.")
    if len(parsed) > 8:
        raise ValueError("No more than eight sources may be attached at once.")

    sources: list[SourceEvidence] = []
    for index, raw_source in enumerate(parsed):
        try:
            source = _SourceEvidenceInput.model_validate(raw_source)
        except ValidationError as exc:
            error = exc.errors(include_url=False)[0]
            location = ".".join(str(part) for part in error["loc"])
            suffix = f".{location}" if location else ""
            raise ValueError(f"sources_json[{index}]{suffix}: {error['msg']}.") from exc
        url = str(source.url)
        parts = urlsplit(url)
        if source.url.scheme != "https":
            raise ValueError(f"sources_json[{index}].url must use HTTPS.")
        if parts.username is not None or parts.password is not None:
            raise ValueError(f"sources_json[{index}].url must not contain credentials.")
        query_names = {name.casefold() for name, _ in parse_qsl(parts.query)}
        if query_names & _SENSITIVE_QUERY_NAMES:
            raise ValueError(
                f"sources_json[{index}].url appears to contain a credential or secret."
            )
        sources.append(
            SourceEvidence(
                url=url,
                title=source.title,
                source_type=source.source_type,
                trust_score=normalized_confidence(source.trust_score),
                publisher=source.publisher or None,
                content_hash=(
                    None if source.content_hash is None else source.content_hash.casefold()
                ),
                supports_claim=source.supports_claim,
                note=source.note or None,
            )
        )
    if len({source.url for source in sources}) != len(sources):
        raise ValueError("sources_json contains the same source URL more than once.")
    return tuple(sources)


def propose_create(
    *,
    subject: str,
    entity_type: str,
    claim_key: str,
    content: dict[str, Any],
    context: dict[str, Any],
    status: KnowledgeStatus,
    game_version: str | None,
    confidence: float,
    sources: tuple[SourceEvidence, ...],
    reason: str,
) -> KnowledgeCreateProposal:
    clean_subject = " ".join(subject.split())
    if not clean_subject:
        raise ValueError("A subject is required.")
    if len(clean_subject) > 300:
        raise ValueError("subject must not exceed 300 characters.")
    clean_entity_type = _validated_identifier(entity_type, field_name="entity_type", limit=80)
    clean_claim_key = _validated_identifier(claim_key, field_name="claim_key", limit=160)
    if not content:
        raise ValueError("content_json must contain at least one field.")
    if status not in {
        KnowledgeStatus.ACTIVE,
        KnowledgeStatus.CANDIDATE,
        KnowledgeStatus.DISPUTED,
    }:
        raise ValueError("A new entry must be active, candidate, or disputed.")
    if not sources:
        raise ValueError("At least one source is required.")
    if status == KnowledgeStatus.ACTIVE and not any(source.supports_claim for source in sources):
        raise ValueError("An active entry requires at least one supporting source.")
    clean_game_version = None if game_version is None else game_version.strip() or None
    if clean_game_version is not None and len(clean_game_version) > 80:
        raise ValueError("game_version must not exceed 80 characters.")
    return KnowledgeCreateProposal(
        subject=clean_subject,
        entity_type=clean_entity_type,
        claim_key=clean_claim_key,
        content=content,
        context=context,
        status=status,
        game_version=clean_game_version,
        confidence=normalized_confidence(confidence),
        sources=sources,
        reason=_validated_reason(reason),
    )


def propose_revision(
    entry: KnowledgeEntry,
    *,
    content: dict[str, Any],
    context: dict[str, Any] | None,
    status: KnowledgeStatus | None,
    game_version: str | None,
    clear_game_version: bool = False,
    confidence: float | None,
    reason: str,
) -> KnowledgeChangeProposal:
    clean_reason = _validated_reason(reason)
    if clear_game_version and game_version is not None:
        raise ValueError("Set game_version or clear_game_version, not both.")
    next_context = entry.context if context is None else context
    next_status = KnowledgeStatus(entry.status) if status is None else status
    next_game_version = (
        None
        if clear_game_version
        else entry.game_version
        if game_version is None
        else game_version.strip() or None
    )
    next_confidence = (
        Decimal(entry.confidence) if confidence is None else normalized_confidence(confidence)
    )
    before = _snapshot(
        content=entry.content,
        context=entry.context,
        status=KnowledgeStatus(entry.status),
        game_version=entry.game_version,
        confidence=Decimal(entry.confidence),
    )
    after = _snapshot(
        content=content,
        context=next_context,
        status=next_status,
        game_version=next_game_version,
        confidence=next_confidence,
    )
    changes = tuple(_json_diff(before, after))
    if not changes:
        raise ValueError("The proposed revision does not change the current knowledge entry.")
    return KnowledgeChangeProposal(
        action=KnowledgeAction.REVISE,
        entry_id=entry.id,
        subject=entry.subject,
        expected_current_revision=entry.current_revision,
        changes=changes,
        reason=clean_reason,
        content=content,
        context=next_context,
        status=next_status,
        game_version=next_game_version,
        confidence=next_confidence,
    )


def propose_rollback(
    entry: KnowledgeEntry,
    *,
    target_revision_number: int,
    reason: str,
) -> KnowledgeChangeProposal:
    clean_reason = _validated_reason(reason)
    if target_revision_number < 1:
        raise ValueError("The rollback revision must be positive.")
    if target_revision_number == entry.current_revision:
        raise ValueError("The requested revision is already current.")
    target = next(
        (
            revision
            for revision in entry.revisions
            if revision.revision_number == target_revision_number
        ),
        None,
    )
    if target is None:
        raise KeyError(f"Knowledge entry has no revision {target_revision_number}.")
    before = _snapshot(
        content=entry.content,
        context=entry.context,
        status=KnowledgeStatus(entry.status),
        game_version=entry.game_version,
        confidence=Decimal(entry.confidence),
    )
    after = _snapshot_from_revision(target)
    changes = tuple(_json_diff(before, after))
    if not changes:
        raise ValueError("The target revision has the same knowledge values as the current entry.")
    return KnowledgeChangeProposal(
        action=KnowledgeAction.ROLLBACK,
        entry_id=entry.id,
        subject=entry.subject,
        expected_current_revision=entry.current_revision,
        changes=changes,
        reason=clean_reason,
        content=target.content,
        context=target.context,
        status=KnowledgeStatus(target.status),
        game_version=target.game_version,
        confidence=Decimal(target.confidence),
        target_revision_number=target_revision_number,
    )


def render_proposal(proposal: KnowledgeChangeProposal, *, max_chars: int = 1750) -> str:
    action = "revision" if proposal.action == KnowledgeAction.REVISE else "rollback"
    lines = [
        f"Confirm knowledge {action} for **{proposal.subject}** (`{proposal.entry_id}`).",
        f"Current revision: `{proposal.expected_current_revision}` → new revision: "
        f"`{proposal.next_revision_number}`",
    ]
    if proposal.target_revision_number is not None:
        lines.append(f"Rollback snapshot: revision `{proposal.target_revision_number}`")
    lines.extend((f"Reason: {proposal.reason}", "", "Proposed diff:"))
    omitted = 0
    for index, change in enumerate(proposal.changes):
        line = (f"- `{change.path}`: {_compact(change.before)} → {_compact(change.after)}").replace(
            "```", "'''"
        )
        reserve = 80
        if len("\n".join([*lines, line])) > max_chars - reserve:
            omitted = len(proposal.changes) - index
            break
        lines.append(line)
    if omitted:
        lines.append(f"- …and {omitted} more changed field(s).")
    lines.append("\nThis takes effect immediately and invalidates dependent answer caches.")
    return "\n".join(lines)[:max_chars]


def render_create_proposal(proposal: KnowledgeCreateProposal, *, max_chars: int = 1750) -> str:
    lines = [
        f"Confirm new knowledge entry for **{proposal.subject}**.",
        f"Identity: `{proposal.entity_type}` / `{proposal.claim_key}`",
        f"Status: `{proposal.status.value}` · confidence: `{proposal.confidence}` · "
        f"game version: `{proposal.game_version or 'unspecified'}`",
        f"Reason: {proposal.reason}",
        "",
        f"Content: `{_compact(proposal.content, limit=360)}`",
        f"Context: `{_compact(proposal.context, limit=240)}`",
        "",
        f"Source evidence ({len(proposal.sources)}):",
    ]
    omitted = 0
    for index, source in enumerate(proposal.sources):
        support = "supports" if source.supports_claim else "opposes"
        line = (
            f"- {_compact(source.title, limit=100)} · `{source.source_type.value}` · "
            f"trust `{source.trust_score}` · {support} · <{source.url}>"
        ).replace("```", "'''")
        if len("\n".join([*lines, line])) > max_chars - 110:
            omitted = len(proposal.sources) - index
            break
        lines.append(line)
    if omitted:
        lines.append(f"- …and {omitted} more source(s).")
    lines.append("\nThis immediately creates revision `1` with an immutable source snapshot.")
    return "\n".join(lines)[:max_chars]


def _snapshot(
    *,
    content: dict[str, Any],
    context: dict[str, Any],
    status: KnowledgeStatus,
    game_version: str | None,
    confidence: Decimal,
) -> dict[str, Any]:
    return {
        "content": content,
        "context": context,
        "status": status.value,
        "game_version": game_version,
        "confidence": str(confidence),
    }


def _snapshot_from_revision(revision: KnowledgeRevision) -> dict[str, Any]:
    return _snapshot(
        content=revision.content,
        context=revision.context,
        status=KnowledgeStatus(revision.status),
        game_version=revision.game_version,
        confidence=Decimal(revision.confidence),
    )


def _json_diff(before: Any, after: Any, *, path: str = "$") -> list[FieldChange]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[FieldChange] = []
        for key in sorted(before.keys() | after.keys()):
            child_path = f"{path}.{key}"
            if key not in before:
                changes.append(FieldChange(child_path, "<missing>", after[key]))
            elif key not in after:
                changes.append(FieldChange(child_path, before[key], "<missing>"))
            else:
                changes.extend(_json_diff(before[key], after[key], path=child_path))
        return changes
    return [FieldChange(path, before, after)]


def _validated_reason(reason: str) -> str:
    clean = reason.strip()
    if not clean:
        raise ValueError("A reason is required.")
    return clean[:1000]


def _validated_identifier(value: str, *, field_name: str, limit: int) -> str:
    clean = value.strip().casefold()
    if not clean:
        raise ValueError(f"{field_name} is required.")
    if len(clean) > limit:
        raise ValueError(f"{field_name} must not exceed {limit} characters.")
    if re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", clean) is None:
        raise ValueError(
            f"{field_name} may contain only letters, numbers, periods, underscores, and hyphens."
        )
    return clean


def _compact(value: Any, *, limit: int = 160) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 1] + "…"

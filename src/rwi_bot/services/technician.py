from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from rwi_bot.db.models import KnowledgeEntry, KnowledgeRevision, KnowledgeStatus
from rwi_bot.services.knowledge import normalized_confidence


class KnowledgeAction(StrEnum):
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


def _compact(value: Any, *, limit: int = 160) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 1] + "…"

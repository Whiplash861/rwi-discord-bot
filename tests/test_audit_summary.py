from __future__ import annotations

from uuid import uuid4

from rwi_bot.bot.client import build_audit_summary_embed
from rwi_bot.domain.schemas import AuditRecord


def test_unanswered_ticket_embed_explains_the_question_and_failure() -> None:
    ticket_id = uuid4()
    record = AuditRecord(
        event_type="knowledge.unanswered_ticket",
        actor_id=42,
        target_type="unanswered_ticket",
        target_id=str(ticket_id),
        reason="Current evidence was inconclusive.",
        details={
            "question": "Does Resolved trigger when a projectile hits an enemy shield?",
            "failure_code": "insufficient_current_evidence",
            "failure_summary": (
                "Current sources did not establish how Resolved treats shield impacts."
            ),
            "used_web_search": True,
            "requested_action": (
                "Test the interaction in Red Horizon and document any armor exceptions."
            ),
        },
    )

    embed = build_audit_summary_embed(record, uuid4())
    fields = {field.name: field.value for field in embed.fields}

    assert embed.title == "ERIN needs help with an unanswered question"
    assert "Resolved" in fields["Original question"]
    assert "shield impacts" in fields["What went wrong"]
    assert "web search: attempted" in fields["Checks already attempted"].casefold()
    assert "Test the interaction" in fields["What the Technician should verify"]
    assert fields["Ticket ID"] == f"`{ticket_id}`"
    assert "Event ID" not in fields


def test_autonomy_embed_explains_knowledge_handling() -> None:
    record = AuditRecord(
        event_type="autonomy.research_completed",
        target_type="game_version",
        target_id="Y8S3 Red Horizon",
        reason="A scheduled source sweep completed.",
        details={
            "promoted_official_findings": 2,
            "staged_for_review": 3,
            "duplicates_skipped": 4,
            "stale_answer_caches": 0,
            "staged_subjects": ["Reported talent interaction"],
        },
    )

    embed = build_audit_summary_embed(record, uuid4())
    fields = {field.name: field.value for field in embed.fields}

    assert embed.title == "ERIN completed a game-update check"
    assert "Official findings promoted: **2**" in fields["Knowledge handling"]
    assert "Reported talent interaction" in fields["Technician review queue"]

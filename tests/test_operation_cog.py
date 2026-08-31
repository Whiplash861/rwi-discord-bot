from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from rwi_bot.cogs.operations import (
    OperationConfirmationView,
    OperationRsvpView,
    render_operation_embed,
)
from rwi_bot.db.models import OperationRsvp, OperationRsvpStatus, ScheduledOperation


def test_operation_views_are_persistent_and_event_scoped() -> None:
    operation_id = UUID("11111111-2222-3333-4444-555555555555")
    rsvp_view = OperationRsvpView(operation_id)
    confirmation_view = OperationConfirmationView(operation_id)

    assert rsvp_view.timeout is None
    assert confirmation_view.timeout is None
    custom_ids = {item.custom_id for item in (*rsvp_view.children, *confirmation_view.children)}
    assert None not in custom_ids
    assert len(custom_ids) == 6
    assert all(operation_id.hex in custom_id for custom_id in custom_ids if custom_id)


def test_operation_embed_separates_going_standby_and_confirmation() -> None:
    operation_id = UUID("11111111-2222-3333-4444-555555555555")
    operation = ScheduledOperation(
        id=operation_id,
        guild_id=1,
        organizer_user_id=10,
        activity="Broken Rain",
        activity_type="incursion",
        organizer_role="Tank",
        start_at=datetime(2026, 9, 2, 23, tzinfo=UTC),
        capacity=4,
        status="scheduled",
    )
    rsvps = [
        OperationRsvp(
            operation_id=operation_id,
            discord_user_id=10,
            status=OperationRsvpStatus.GOING,
            selected_role="Tank",
            confirmed_at=datetime(2026, 9, 2, 22, 5, tzinfo=UTC),
        ),
        OperationRsvp(
            operation_id=operation_id,
            discord_user_id=11,
            status=OperationRsvpStatus.MAYBE,
            selected_role="Healer",
        ),
    ]

    embed = render_operation_embed(operation, rsvps)

    fields = {field.name: field.value for field in embed.fields}
    assert embed.title == "Broken Rain"
    assert "Going — 1/4" in fields
    assert "<@10> — Tank ✅ confirmed" in fields["Going — 1/4"]
    assert "<@11> — Healer" in fields["Maybe / Standby — 1"]
    assert embed.footer.text == f"RWI_OPERATION_{operation_id.hex}"

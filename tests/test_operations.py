from __future__ import annotations

from datetime import UTC, datetime

from rwi_bot.services.operations import (
    is_operation_schedule_request,
    parse_operation_activity,
    parse_operation_request,
    parse_operation_role,
    parse_operation_start,
)


def test_broken_rain_relative_schedule_request_requires_missing_time() -> None:
    parsed = parse_operation_request(
        "Set up a Broken Rain run in 2 days",
        now=datetime(2026, 8, 31, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.activity == "Broken Rain"
    assert parsed.activity_type == "incursion"
    assert parsed.capacity == 4
    assert parsed.target_date is not None
    assert parsed.target_date.isoformat() == "2026-09-02"
    assert parsed.start_at is None


def test_full_raid_schedule_is_converted_to_utc() -> None:
    parsed = parse_operation_request(
        "Schedule an Iron Horse raid in 2 days at 8:30 PM ET",
        now=datetime(2026, 8, 31, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.activity == "Operation Iron Horse"
    assert parsed.capacity == 8
    assert parsed.start_at == datetime(2026, 9, 3, 0, 30, tzinfo=UTC)


def test_follow_up_time_uses_existing_date_and_requires_timezone() -> None:
    parsed = parse_operation_request(
        "Plan a Paradise Lost incursion tomorrow",
        now=datetime(2026, 8, 31, 15, tzinfo=UTC),
    )
    assert parsed is not None

    assert (
        parse_operation_start(
            "8 PM",
            target_date=parsed.target_date,
            now=datetime(2026, 8, 31, 15, tzinfo=UTC),
        )
        is None
    )
    assert parse_operation_start(
        "8 PM PT",
        target_date=parsed.target_date,
        now=datetime(2026, 8, 31, 15, tzinfo=UTC),
    ) == datetime(2026, 9, 2, 3, tzinfo=UTC)


def test_operation_role_parser_supports_requested_roles() -> None:
    assert parse_operation_role("I'll run healer") == "Healer"
    assert parse_operation_role("DPS") == "DPS"
    assert parse_operation_role("I'm not sure yet") == "Undecided"
    assert parse_operation_role("I can be the drone killer") == "Drone Killer"
    assert parse_operation_role("Put me down for CC") == "Crowd Control"


def test_scheduler_supports_incursion_and_raid_activity_aliases() -> None:
    assert parse_operation_activity("Merit Estate run") == ("Paradise Lost", "incursion", 4)
    assert parse_operation_activity("ODH raid") == ("Operation Dark Hours", "raid", 8)


def test_weekday_and_24_hour_time_are_supported() -> None:
    parsed = parse_operation_request(
        "Schedule a Broken Rain run next Friday at 20:30 ET",
        now=datetime(2026, 8, 31, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.target_date is not None
    assert parsed.target_date.isoformat() == "2026-09-04"
    assert parsed.start_at == datetime(2026, 9, 5, 0, 30, tzinfo=UTC)


def test_noon_and_midnight_are_supported() -> None:
    assert parse_operation_start(
        "noon PT",
        target_date=datetime(2026, 9, 2, tzinfo=UTC).date(),
    ) == datetime(2026, 9, 2, 19, tzinfo=UTC)


def test_unrelated_division_message_does_not_start_scheduler() -> None:
    assert not is_operation_schedule_request("How does Broken Rain work?")

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from rwi_bot.db.models import (
    OperationRsvp,
    OperationRsvpStatus,
    ScheduledOperation,
    ScheduledOperationStatus,
)
from rwi_bot.db.session import Database

SERVER_TIMEZONE = ZoneInfo("America/New_York")
ACTIVITIES: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    ("Broken Rain", "incursion", 4, ("broken rain", "brokenrain", "broken reign")),
    (
        "Paradise Lost",
        "incursion",
        4,
        ("paradise lost", "meret estate", "merit estate"),
    ),
    ("Operation Dark Hours", "raid", 8, ("dark hours", "operation dark hours", "odh")),
    (
        "Operation Iron Horse",
        "raid",
        8,
        ("iron horse", "operation iron horse", "ih raid"),
    ),
)
OPERATION_ROLES = (
    "Tank",
    "Healer",
    "DPS",
    "Support",
    "Mechanics",
    "Crowd Control",
    "Drone Killer",
    "Kite",
    "Undecided",
)

_REQUEST_INTENT = re.compile(
    r"\b(?:schedule|organize|organise|plan|set\s+up|create)\b.{0,160}"
    r"\b(?:run|raid|incursion|operation|event)\b|"
    r"\b(?:schedule|organize|organise|plan|set\s+up|create)\b.{0,160}"
    r"\b(?:broken\s*rain|broken\s+reign|paradise\s+lost|mer[ei]t\s+estate|"
    r"dark\s+hours|iron\s+horse)\b",
    re.IGNORECASE,
)
_ROLE = re.compile(
    r"\b(tank|healer|medic|dps|damage|support|mechanics?|crowd\s+control|cc|"
    r"drone\s+killer|kite|kiter|undecided|not\s+sure)\b",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b(?:\s*(et|est|edt|ct|cst|cdt|"
    r"mt|mst|mdt|pt|pst|pdt|utc|gmt))?",
    re.IGNORECASE,
)
_TIME_24 = re.compile(
    r"\b(?:at\s*)?([01]?\d|2[0-3]):([0-5]\d)\b(?:\s*(et|est|edt|ct|cst|cdt|"
    r"mt|mst|mdt|pt|pst|pdt|utc|gmt))?",
    re.IGNORECASE,
)
_SPECIAL_TIME = re.compile(
    r"\b(?:at\s+)?(noon|midnight)\b(?:\s*(et|est|edt|ct|cst|cdt|"
    r"mt|mst|mdt|pt|pst|pdt|utc|gmt))?",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_RELATIVE_DAYS = re.compile(r"\bin\s+(\d{1,3})\s+days?\b", re.IGNORECASE)
_WEEKDAY = re.compile(
    r"\b(?:(this|next)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_ZONE_NAMES = {
    "et": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "ct": "America/Chicago",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "mt": "America/Denver",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "pt": "America/Los_Angeles",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "utc": "UTC",
    "gmt": "UTC",
}


@dataclass(frozen=True, slots=True)
class ParsedOperationRequest:
    activity: str | None
    activity_type: str | None
    capacity: int | None
    target_date: date | None
    start_at: datetime | None
    time_needs_timezone: bool = False


class OperationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(
        self,
        *,
        guild_id: int,
        organizer_user_id: int,
        activity: str,
        activity_type: str,
        organizer_role: str,
        start_at: datetime,
        capacity: int,
        source_channel_id: int | None,
        matchmaking_role_id: int | None,
        notes: str | None = None,
    ) -> ScheduledOperation:
        operation = ScheduledOperation(
            guild_id=guild_id,
            organizer_user_id=organizer_user_id,
            activity=activity,
            activity_type=activity_type,
            organizer_role=organizer_role,
            start_at=start_at.astimezone(UTC),
            capacity=capacity,
            notes=notes,
            source_channel_id=source_channel_id,
            matchmaking_role_id=matchmaking_role_id,
            status=ScheduledOperationStatus.SCHEDULED,
        )
        async with self.database.session() as session:
            session.add(operation)
            await session.flush()
        return operation

    async def get(self, operation_id: UUID) -> ScheduledOperation | None:
        async with self.database.session() as session:
            return await session.get(ScheduledOperation, operation_id)

    async def active(self) -> list[ScheduledOperation]:
        statement = (
            select(ScheduledOperation)
            .where(ScheduledOperation.status == ScheduledOperationStatus.SCHEDULED)
            .order_by(ScheduledOperation.start_at)
        )
        async with self.database.session() as session:
            return list((await session.scalars(statement)).all())

    async def attach_announcement(
        self,
        operation_id: UUID,
        *,
        channel_id: int,
        message_id: int,
    ) -> None:
        async with self.database.session() as session:
            await session.execute(
                update(ScheduledOperation)
                .where(ScheduledOperation.id == operation_id)
                .values(
                    announcement_channel_id=channel_id,
                    announcement_message_id=message_id,
                )
            )

    async def upsert_rsvp(
        self,
        operation_id: UUID,
        *,
        user_id: int,
        status: OperationRsvpStatus,
        selected_role: str,
    ) -> OperationRsvp:
        async with self.database.session() as session:
            rsvp = await session.get(OperationRsvp, (operation_id, user_id))
            if rsvp is None:
                rsvp = OperationRsvp(
                    operation_id=operation_id,
                    discord_user_id=user_id,
                    status=status,
                    selected_role=selected_role,
                )
                session.add(rsvp)
            else:
                rsvp.status = status
                rsvp.selected_role = selected_role
                if status == OperationRsvpStatus.WITHDRAWN:
                    rsvp.confirmed_at = None
            await session.flush()
            return rsvp

    async def rsvps(self, operation_id: UUID) -> list[OperationRsvp]:
        statement = (
            select(OperationRsvp)
            .where(OperationRsvp.operation_id == operation_id)
            .order_by(OperationRsvp.created_at)
        )
        async with self.database.session() as session:
            return list((await session.scalars(statement)).all())

    async def confirm(self, operation_id: UUID, *, user_id: int, now: datetime) -> bool:
        async with self.database.session() as session:
            rsvp = await session.get(OperationRsvp, (operation_id, user_id), with_for_update=True)
            if rsvp is None or rsvp.status == OperationRsvpStatus.WITHDRAWN:
                return False
            rsvp.status = OperationRsvpStatus.GOING
            rsvp.confirmed_at = now.astimezone(UTC)
            return True

    async def due_reminders(self, *, now: datetime) -> list[ScheduledOperation]:
        horizon = now.astimezone(UTC) + timedelta(hours=1)
        statement = (
            select(ScheduledOperation)
            .where(ScheduledOperation.status == ScheduledOperationStatus.SCHEDULED)
            .where(ScheduledOperation.reminder_sent_at.is_(None))
            .where(ScheduledOperation.start_at > now.astimezone(UTC))
            .where(ScheduledOperation.start_at <= horizon)
            .order_by(ScheduledOperation.start_at)
        )
        async with self.database.session() as session:
            return list((await session.scalars(statement)).all())

    async def mark_reminder_sent(
        self,
        operation_id: UUID,
        *,
        message_id: int,
        sent_at: datetime,
    ) -> None:
        async with self.database.session() as session:
            await session.execute(
                update(ScheduledOperation)
                .where(ScheduledOperation.id == operation_id)
                .values(reminder_message_id=message_id, reminder_sent_at=sent_at.astimezone(UTC))
            )

    async def complete_past(self, *, before: datetime) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                update(ScheduledOperation)
                .where(ScheduledOperation.status == ScheduledOperationStatus.SCHEDULED)
                .where(ScheduledOperation.start_at <= before.astimezone(UTC))
                .values(status=ScheduledOperationStatus.COMPLETED)
            )
            return int(getattr(result, "rowcount", 0) or 0)


def is_operation_schedule_request(text: str) -> bool:
    return _REQUEST_INTENT.search(" ".join(text.split())) is not None


def parse_operation_request(
    text: str,
    *,
    now: datetime | None = None,
) -> ParsedOperationRequest | None:
    clean = " ".join(text.split())
    if not is_operation_schedule_request(clean):
        return None
    activity, activity_type, capacity = _activity(clean)
    current = (now or datetime.now(UTC)).astimezone(SERVER_TIMEZONE)
    target_date = _date_from_text(clean, current=current)
    parsed_time, zone = _time_and_zone(clean)
    start_at = _combine(target_date, parsed_time, zone)
    return ParsedOperationRequest(
        activity=activity,
        activity_type=activity_type,
        capacity=capacity,
        target_date=target_date,
        start_at=start_at,
        time_needs_timezone=parsed_time is not None and zone is None,
    )


def parse_operation_role(text: str) -> str | None:
    if not (match := _ROLE.search(" ".join(text.split()))):
        return None
    value = match.group(1).casefold()
    if value in {"mechanic", "mechanics"}:
        return "Mechanics"
    if value in {"medic"}:
        return "Healer"
    if value in {"damage"}:
        return "DPS"
    if value in {"crowd control", "cc"}:
        return "Crowd Control"
    if value == "drone killer":
        return "Drone Killer"
    if value in {"kite", "kiter"}:
        return "Kite"
    if value in {"not sure", "undecided"}:
        return "Undecided"
    return value.upper() if value == "dps" else value.title()


def parse_operation_activity(text: str) -> tuple[str, str, int] | None:
    activity, activity_type, capacity = _activity(" ".join(text.split()))
    if activity is None or activity_type is None or capacity is None:
        return None
    return activity, activity_type, capacity


def parse_operation_start(
    text: str,
    *,
    target_date: date | None,
    now: datetime | None = None,
) -> datetime | None:
    clean = " ".join(text.split())
    current = (now or datetime.now(UTC)).astimezone(SERVER_TIMEZONE)
    resolved_date = _date_from_text(clean, current=current) or target_date
    parsed_time, zone = _time_and_zone(clean)
    return _combine(resolved_date, parsed_time, zone)


def _activity(text: str) -> tuple[str | None, str | None, int | None]:
    lowered = text.casefold()
    for name, activity_type, capacity, aliases in ACTIVITIES:
        if any(alias in lowered for alias in aliases):
            return name, activity_type, capacity
    return None, None, None


def _date_from_text(text: str, *, current: datetime) -> date | None:
    if match := _RELATIVE_DAYS.search(text):
        return current.date() + timedelta(days=int(match.group(1)))
    lowered = text.casefold()
    if "tomorrow" in lowered:
        return current.date() + timedelta(days=1)
    if "today" in lowered:
        return current.date()
    if match := _ISO_DATE.search(text):
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    if match := _WEEKDAY.search(text):
        qualifier = (match.group(1) or "").casefold()
        target_weekday = _WEEKDAYS[match.group(2).casefold()]
        days_ahead = (target_weekday - current.weekday()) % 7
        if days_ahead == 0 and qualifier == "next":
            days_ahead = 7
        return current.date() + timedelta(days=days_ahead)
    for date_format in ("%B %d", "%b %d"):
        for match in re.finditer(r"\b([A-Za-z]+\s+\d{1,2})\b", text):
            try:
                parsed = (
                    datetime.strptime(match.group(1), date_format).date().replace(year=current.year)
                )
            except ValueError:
                continue
            if parsed < current.date():
                parsed = parsed.replace(year=current.year + 1)
            return parsed
    return None


def _time_and_zone(text: str) -> tuple[time | None, ZoneInfo | None]:
    if match := _TIME.search(text):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if not 1 <= hour <= 12 or minute > 59:
            return None, None
        if match.group(3).casefold() == "pm" and hour != 12:
            hour += 12
        elif match.group(3).casefold() == "am" and hour == 12:
            hour = 0
        zone_key = (match.group(4) or "").casefold()
    elif match := _TIME_24.search(text):
        hour = int(match.group(1))
        minute = int(match.group(2))
        zone_key = (match.group(3) or "").casefold()
    elif match := _SPECIAL_TIME.search(text):
        hour = 12 if match.group(1).casefold() == "noon" else 0
        minute = 0
        zone_key = (match.group(2) or "").casefold()
    else:
        return None, None
    zone = ZoneInfo(_ZONE_NAMES[zone_key]) if zone_key else None
    return time(hour=hour, minute=minute), zone


def _combine(
    target_date: date | None,
    target_time: time | None,
    zone: ZoneInfo | None,
) -> datetime | None:
    if target_date is None or target_time is None or zone is None:
        return None
    return datetime.combine(target_date, target_time, tzinfo=zone).astimezone(UTC)

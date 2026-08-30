from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class SpamAction(StrEnum):
    WARNING = "spam_warning"
    TIMEOUT = "spam_timeout"
    KICK = "spam_kick"


@dataclass(frozen=True, slots=True)
class SpamSignal:
    detected: bool = False
    severe: bool = False
    reasons: tuple[str, ...] = ()
    observed_messages: int = 0
    repeated_messages: int = 0


@dataclass(frozen=True, slots=True)
class _MessageEvent:
    observed_at: datetime
    fingerprint: str


class SpamDetector:
    """Detect bursts without retaining message text or attachments."""

    def __init__(
        self,
        *,
        burst_messages: int = 7,
        repeated_messages: int = 3,
        severe_messages: int = 12,
        window: timedelta = timedelta(seconds=10),
        incident_cooldown: timedelta = timedelta(seconds=4),
    ) -> None:
        if repeated_messages < 2:
            raise ValueError("repeated_messages must be at least 2")
        if burst_messages < repeated_messages:
            raise ValueError("burst_messages cannot be below repeated_messages")
        if severe_messages < burst_messages:
            raise ValueError("severe_messages cannot be below burst_messages")
        if window <= timedelta(0) or incident_cooldown < timedelta(0):
            raise ValueError("window must be positive and cooldown cannot be negative")

        self.burst_messages = burst_messages
        self.repeated_messages = repeated_messages
        self.severe_messages = severe_messages
        self.window = window
        self.incident_cooldown = incident_cooldown
        self._events: dict[tuple[int, int], deque[_MessageEvent]] = defaultdict(deque)
        self._cooldowns: dict[tuple[int, int], datetime] = {}

    def inspect(
        self,
        *,
        guild_id: int,
        user_id: int,
        content: str,
        attachment_count: int = 0,
        now: datetime | None = None,
    ) -> SpamSignal:
        observed_at = now or datetime.now(UTC)
        key = (guild_id, user_id)
        events = self._events[key]
        cutoff = observed_at - self.window
        while events and events[0].observed_at < cutoff:
            events.popleft()

        fingerprint = self._fingerprint(content, attachment_count)
        events.append(_MessageEvent(observed_at=observed_at, fingerprint=fingerprint))
        repeated = sum(event.fingerprint == fingerprint for event in events)
        observed = len(events)

        cooldown_until = self._cooldowns.get(key)
        if cooldown_until is not None and observed_at < cooldown_until:
            return SpamSignal(observed_messages=observed, repeated_messages=repeated)

        reasons: list[str] = []
        if repeated >= self.repeated_messages:
            reasons.append("repeated_message")
        if observed >= self.burst_messages:
            reasons.append("message_burst")
        detected = bool(reasons)
        severe = observed >= self.severe_messages
        if detected:
            self._cooldowns[key] = observed_at + self.incident_cooldown
        return SpamSignal(
            detected=detected,
            severe=severe,
            reasons=tuple(reasons),
            observed_messages=observed,
            repeated_messages=repeated,
        )

    @staticmethod
    def _fingerprint(content: str, attachment_count: int) -> str:
        normalized = " ".join(content.casefold().split())
        payload = f"{normalized}\0attachments:{attachment_count}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def choose_spam_action(previous_incidents: int, *, severe: bool) -> SpamAction:
    if previous_incidents < 0:
        raise ValueError("previous_incidents cannot be negative")
    if previous_incidents >= 2 or (severe and previous_incidents >= 1):
        return SpamAction.KICK
    if previous_incidents >= 1 or severe:
        return SpamAction.TIMEOUT
    return SpamAction.WARNING

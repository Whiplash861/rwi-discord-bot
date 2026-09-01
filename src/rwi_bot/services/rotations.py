from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient
from rwi_bot.domain.schemas import (
    RotationResearchItem,
    RotationResearchReport,
    SourceCitation,
    TargetedLootAssignment,
    VendorStockEntry,
)

JsonFetcher = Callable[[str], Awaitable[object]]
TextFetcher = Callable[[str], Awaitable[str]]


class RotationCacheState(BaseModel):
    last_refresh_at: datetime | None = None
    last_web_research_at: datetime | None = None
    last_status: str = "never_run"
    last_summary: str = "Rotation intelligence has not run yet."
    consecutive_failures: int = 0
    web_report: RotationResearchReport | None = None
    web_citations: list[SourceCitation] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EscalationRotation:
    week: date
    day: date
    missions: tuple[tuple[str, str], ...]
    prototype_gear_cache: str | None
    prototype_weapon_cache: str | None


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    name: str
    title: str
    category: str
    occurs: str
    duration_seconds: int
    scheduled_start: datetime | None = None
    scheduled_active_end: datetime | None = None
    cycle_seed: datetime | None = None
    cycle_duration: int | None = None


@dataclass(frozen=True, slots=True)
class VendorFeed:
    updated_at: datetime
    source_url: str
    items: tuple[VendorStockEntry, ...]


@dataclass(frozen=True, slots=True)
class RotationField:
    name: str
    value: str
    inline: bool = False


@dataclass(frozen=True, slots=True)
class RotationImage:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class RotationPublication:
    key: str
    channel_name: str
    title: str
    description: str
    fields: tuple[RotationField, ...]
    marker: str
    images: tuple[RotationImage, ...] = ()

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "title": self.title,
                "description": self.description,
                "fields": [
                    {"name": field.name, "value": field.value, "inline": field.inline}
                    for field in self.fields
                ],
                "images": [{"label": image.label, "url": image.url} for image in self.images],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RotationSnapshot:
    correlation_id: UUID
    publications: tuple[RotationPublication, ...]
    warnings: tuple[str, ...]
    web_researched: bool
    used_cached_web: bool


class RotationStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def load(self) -> RotationCacheState:
        try:
            raw = await asyncio.to_thread(self.path.read_text, encoding="utf-8")
            return RotationCacheState.model_validate_json(raw)
        except (FileNotFoundError, ValueError):
            return RotationCacheState()

    async def save(self, state: RotationCacheState) -> None:
        await asyncio.to_thread(self.path.parent.mkdir, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = state.model_dump_json(indent=2)
        await asyncio.to_thread(temporary.write_text, payload, encoding="utf-8")
        await asyncio.to_thread(temporary.replace, self.path)


class RotationService:
    """Collect current rotations without treating an old or unverified value as current."""

    def __init__(
        self,
        *,
        ai: RwiOpenAIClient,
        state_store: RotationStateStore,
        owner_user_id: int,
        current_game_version: Callable[[], str],
        escalation_url: str,
        calendar_url: str,
        vendor_page_url: str | None = None,
        vendor_gear_url: str | None = None,
        vendor_weapons_url: str | None = None,
        vendor_mods_url: str | None = None,
        web_refresh_hours: int,
        enabled: bool,
        fetch_json: JsonFetcher | None = None,
        fetch_text: TextFetcher | None = None,
    ) -> None:
        self.ai = ai
        self.state_store = state_store
        self.owner_user_id = owner_user_id
        self.current_game_version = current_game_version
        self.escalation_url = escalation_url
        self.calendar_url = calendar_url
        self.vendor_page_url = vendor_page_url
        self.vendor_gear_url = vendor_gear_url
        self.vendor_weapons_url = vendor_weapons_url
        self.vendor_mods_url = vendor_mods_url
        self.web_refresh_hours = web_refresh_hours
        self.enabled = enabled
        self.fetch_json = fetch_json or self._fetch_json
        self.fetch_text = fetch_text or self._fetch_text
        self._state: RotationCacheState | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> RotationCacheState:
        self._state = await self.state_store.load()
        return self._state

    async def status(self) -> RotationCacheState:
        if self._state is None:
            return await self.initialize()
        return self._state

    async def collect(
        self,
        *,
        force_web: bool = False,
        now: datetime | None = None,
    ) -> RotationSnapshot:
        if not self.enabled:
            raise RuntimeError("Rotation publishing is disabled.")
        async with self._lock:
            current = (now or datetime.now(UTC)).astimezone(UTC)
            state = await self.status()
            correlation_id = uuid4()
            warnings: list[str] = []
            direct_results = await asyncio.gather(
                self.fetch_json(self.escalation_url),
                self.fetch_json(self.calendar_url),
                self._load_vendor_feed(),
                return_exceptions=True,
            )
            escalation: EscalationRotation | None = None
            calendar: tuple[CalendarEvent, ...] = ()
            vendor_feed: VendorFeed | None = None
            if isinstance(direct_results[0], BaseException):
                warnings.append("The structured Escalation feed was unavailable.")
            else:
                try:
                    escalation = _parse_escalation(direct_results[0], current.date())
                except (TypeError, ValueError, KeyError):
                    warnings.append("The structured Escalation feed was invalid or out of date.")
            if isinstance(direct_results[1], BaseException):
                warnings.append("The reset calendar feed was unavailable.")
            else:
                try:
                    calendar = _parse_calendar(direct_results[1])
                except (TypeError, ValueError, KeyError):
                    warnings.append("The reset calendar feed returned an invalid response.")
            if isinstance(direct_results[2], BaseException):
                warnings.append("The structured weekly vendor feed was unavailable or invalid.")
            elif isinstance(direct_results[2], VendorFeed):
                vendor_feed = direct_results[2]
                if vendor_feed.updated_at < current - timedelta(days=8):
                    warnings.append("The weekly vendor feed was older than eight days.")
                    vendor_feed = None

            web_researched = force_web or _web_research_due(
                state.last_web_research_at,
                current,
                hours=self.web_refresh_hours,
                calendar=calendar,
            )
            used_cached_web = False
            if web_researched:
                try:
                    result = await self.ai.research_current_rotations(
                        current_game_version=self.current_game_version(),
                        actor_id=self.owner_user_id,
                        correlation_id=correlation_id,
                    )
                    if result.report.as_of != current.date():
                        raise ValueError("rotation research was not dated for today")
                    state.web_report = result.report
                    state.web_citations = result.citations
                    state.last_web_research_at = current
                except (OpenAIUnavailableError, ValueError):
                    warnings.append(
                        "Current community rotation research failed; ERIN retained only "
                        "still-valid cached findings."
                    )
                    used_cached_web = state.web_report is not None
            elif state.web_report is not None:
                used_cached_web = True

            accepted_items = _accepted_web_items(
                state.web_report,
                tuple(state.web_citations),
                today=current.date(),
            )
            publications = _build_publications(
                current,
                escalation=escalation,
                calendar=calendar,
                web_items=accepted_items,
                vendor_feed=vendor_feed,
            )
            state.last_refresh_at = current
            state.last_status = "completed" if not warnings else "partial"
            state.last_summary = (
                f"Prepared {len(publications)} rotation posts with "
                f"{len(accepted_items)} confidence-gated researched item(s)."
            )
            if warnings:
                state.consecutive_failures += 1
            else:
                state.consecutive_failures = 0
            await self.state_store.save(state)
            self._state = state
            return RotationSnapshot(
                correlation_id=correlation_id,
                publications=publications,
                warnings=tuple(warnings),
                web_researched=web_researched,
                used_cached_web=used_cached_web,
            )

    @staticmethod
    async def _fetch_json(url: str) -> object:
        timeout = httpx.Timeout(15.0, connect=5.0)
        headers = {"User-Agent": "ERIN-RWI-Rotation-Monitor/1.0"}
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def _fetch_text(url: str) -> str:
        timeout = httpx.Timeout(15.0, connect=5.0)
        headers = {"User-Agent": "ERIN-RWI-Rotation-Monitor/1.0"}
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _load_vendor_feed(self) -> VendorFeed | None:
        urls = (
            self.vendor_page_url,
            self.vendor_gear_url,
            self.vendor_weapons_url,
            self.vendor_mods_url,
        )
        if any(url is None for url in urls):
            return None
        page_url, gear_url, weapons_url, mods_url = (str(url) for url in urls)
        page, gear, weapons, mods = await asyncio.gather(
            self.fetch_text(page_url),
            self.fetch_json(gear_url),
            self.fetch_json(weapons_url),
            self.fetch_json(mods_url),
        )
        return _parse_vendor_feed(
            page,
            (gear, weapons, mods),
            source_url=page_url,
        )


def _parse_escalation(payload: object, today: date) -> EscalationRotation:
    root = _mapping(payload)
    rotations = root.get("Escalation")
    if not isinstance(rotations, list) or not rotations:
        raise ValueError("missing Escalation rotations")
    for raw_rotation in rotations:
        rotation = _mapping(raw_rotation)
        week = date.fromisoformat(str(rotation["week"]))
        mission_names = rotation.get("missions")
        days = rotation.get("target_loot_by_day")
        if not isinstance(mission_names, list) or not isinstance(days, list):
            continue
        for raw_day in days:
            day_data = _mapping(raw_day)
            day = date.fromisoformat(str(day_data["day"]))
            loot = day_data.get("target_loot")
            if not isinstance(loot, list) or len(loot) != len(mission_names):
                continue
            candidate = EscalationRotation(
                week=week,
                day=day,
                missions=tuple(
                    (str(mission).strip(), str(target).strip())
                    for mission, target in zip(mission_names, loot, strict=True)
                    if str(mission).strip() and str(target).strip()
                ),
                prototype_gear_cache=_optional_text(day_data.get("prototype_gear_cache")),
                prototype_weapon_cache=_optional_text(day_data.get("prototype_weapon_cache")),
            )
            if day == today:
                return candidate
    raise ValueError("Escalation feed has no current day")


def _parse_calendar(payload: object) -> tuple[CalendarEvent, ...]:
    root = _mapping(payload)
    calendar = _mapping(root.get("calendar"))
    raw_events = calendar.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("calendar events are missing")
    events: list[CalendarEvent] = []
    for raw_event in raw_events:
        event = _mapping(raw_event)
        name = str(event.get("name") or "").strip()
        if not name:
            continue
        events.append(
            CalendarEvent(
                name=name,
                title=str(event.get("title") or name).strip(),
                category=str(event.get("category") or "Other").strip(),
                occurs=str(event.get("occurs") or "Unknown").strip(),
                duration_seconds=_integer(event.get("durationSeconds"), default=0),
                scheduled_start=_optional_datetime(event.get("scheduledStart")),
                scheduled_active_end=_optional_datetime(event.get("scheduledActiveEnd")),
                cycle_seed=_optional_datetime(event.get("cycleSeed")),
                cycle_duration=_optional_integer(event.get("cycleDuration")),
            )
        )
    if not events:
        raise ValueError("calendar contained no usable events")
    return tuple(events)


def _parse_vendor_feed(
    page: str,
    payloads: tuple[object, ...],
    *,
    source_url: str,
) -> VendorFeed:
    modified_match = re.search(
        r'<meta\s+property=["\']article:modified_time["\']\s+'
        r'content=["\']([^"\']+)["\']',
        page,
        flags=re.IGNORECASE,
    )
    if modified_match is None:
        raise ValueError("vendor page did not expose a modification timestamp")
    updated_at = _optional_datetime(modified_match.group(1))
    if updated_at is None:
        raise ValueError("vendor page modification timestamp was invalid")
    vendor_names = {
        "cassie": "Cassie Mendoza",
        "cassie mendoza": "Cassie Mendoza",
        "clan": "Clan Vendor",
        "countdown": "Countdown Requisition",
        "dz east": "Dark Zone East Vendor",
        "dz south": "Dark Zone South Vendor",
        "dz west": "Dark Zone West Vendor",
    }
    items: list[VendorStockEntry] = []
    for payload in payloads:
        if not isinstance(payload, list):
            raise TypeError("vendor inventory was not a list")
        for raw_item in payload:
            item = _mapping(raw_item)
            vendor = vendor_names.get(str(item.get("vendor") or "").strip().casefold())
            if vendor is None:
                continue
            category = str(item.get("type") or "other").strip().casefold()
            if category not in {"gear", "weapon", "mod", "cache", "other"}:
                category = "other"
            name = _clean_vendor_text(item.get("name"))
            if not name:
                continue
            items.append(
                VendorStockEntry(
                    vendor=vendor,
                    category=category,
                    name=name,
                    details=_vendor_item_details(item, category),
                )
            )
    if not items:
        raise ValueError("vendor inventory contained no relevant stock")
    return VendorFeed(updated_at=updated_at, source_url=source_url, items=tuple(items))


def _vendor_item_details(item: dict[str, Any], category: str) -> str | None:
    parts: list[str] = []
    rarity = str(item.get("rarity") or "").casefold()
    if "named" in rarity:
        parts.append("Named")
    if category == "gear":
        parts.extend(
            _clean_vendor_text(item.get(key))
            for key in ("brand", "slot", "core", "attributes", "talents")
        )
    elif category == "weapon":
        weapon_stats = " / ".join(
            part
            for part in (
                f"{_clean_vendor_text(item.get('dmg'))} DMG"
                if _clean_vendor_text(item.get("dmg"))
                else "",
                f"{_clean_vendor_text(item.get('rpm'))} RPM"
                if _clean_vendor_text(item.get("rpm"))
                else "",
                f"{_clean_vendor_text(item.get('mag'))} MAG"
                if _clean_vendor_text(item.get("mag"))
                else "",
            )
            if part
        )
        parts.extend(
            (
                weapon_stats,
                _clean_vendor_text(item.get("talent")),
                _clean_vendor_text(item.get("attribute1")),
                _clean_vendor_text(item.get("attribute2")),
                _clean_vendor_text(item.get("attribute3")),
            )
        )
    else:
        parts.append(_clean_vendor_text(item.get("attributes")))
    clean_parts = [part for part in parts if part]
    return " · ".join(clean_parts)[:500] or None


def _clean_vendor_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", " · ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split()).strip(" ·")


def _accepted_web_items(
    report: RotationResearchReport | None,
    citations: tuple[SourceCitation, ...],
    *,
    today: date,
) -> tuple[RotationResearchItem, ...]:
    if report is None or report.as_of > today:
        return ()
    citation_by_url = {_normalize_url(str(citation.url)): citation for citation in citations}
    accepted: list[RotationResearchItem] = []
    for item in report.items:
        if item.kind.startswith("targeted_loot_") and report.as_of != today:
            continue
        if item.valid_from > today or (item.valid_until is not None and item.valid_until < today):
            continue
        matched = [
            citation_by_url[_normalize_url(str(url))]
            for url in item.source_urls
            if _normalize_url(str(url)) in citation_by_url
        ]
        if len(matched) != len(item.source_urls) or item.evidence_class == "community_unverified":
            continue
        if item.evidence_class == "official":
            if item.confidence < 0.85 or not all(citation.official for citation in matched):
                continue
        elif item.confidence < 0.80:
            continue
        elif len({_normalize_url(str(citation.url)) for citation in matched}) < 2 and not all(
            citation.source_type in {"community_reference", "official_live_service"}
            for citation in matched
        ):
            continue
        if item.kind.startswith("targeted_loot_") and not _targeted_loot_complete(item):
            continue
        if item.kind == "invaded_missions" and item.invaded is None:
            continue
        if item.kind == "descent_pool" and item.descent is None:
            continue
        if item.kind == "dark_zone_mode":
            if {assignment.zone for assignment in item.dark_zones} != {
                "Dark Zone East",
                "Dark Zone South",
                "Dark Zone West",
            }:
                continue
            if any(
                not assignment.faction or not assignment.targeted_loot
                for assignment in item.dark_zones
            ):
                continue
        if item.kind == "vendor_stock" and not item.vendor_stock:
            continue
        accepted.append(item)
    return tuple(accepted)


def _targeted_loot_complete(item: RotationResearchItem) -> bool:
    if item.map_images:
        return True
    if not item.targeted_loot:
        return False
    if item.kind != "targeted_loot_dc":
        return True
    locations = {entry.location.casefold() for entry in item.targeted_loot}
    required_locations = (
        "the pentagon",
        "coney island amusement park",
        "coney island ballpark",
        "dark hours",
        "iron horse",
    )
    return all(
        any(required in location for location in locations) for required in required_locations
    )


def _build_publications(
    now: datetime,
    *,
    escalation: EscalationRotation | None,
    calendar: tuple[CalendarEvent, ...],
    web_items: tuple[RotationResearchItem, ...],
    vendor_feed: VendorFeed | None,
) -> tuple[RotationPublication, ...]:
    daily_reset = _next_weekday_reset(now, weekday=None, hour=8)
    weekly_reset = _next_weekday_reset(now, weekday=1, hour=8)
    vendor_reset = _next_weekday_reset(now, weekday=5, hour=8)
    descent_reset = _descent_reset(calendar, now)
    by_kind: dict[str, RotationResearchItem] = {
        item.kind: item for item in web_items if item.kind != "other_rotation"
    }
    vendor_stock = _merged_vendor_stock(vendor_feed, by_kind.get("vendor_stock"))

    daily_fields: list[RotationField] = []
    daily_images: list[RotationImage] = []
    for kind, label in (
        ("targeted_loot_dc", "Washington, D.C."),
        ("targeted_loot_nyc", "New York"),
        ("targeted_loot_brooklyn", "Brooklyn"),
    ):
        item = by_kind.get(kind)
        if item is None:
            continue
        daily_fields.extend(_targeted_loot_fields(label, item))
        daily_images.extend(
            RotationImage(label=image.label, url=str(image.url)) for image in item.map_images
        )
    daily_fields.extend(
        (
            RotationField("━━ ESCALATION TARGETED LOOT ━━", "\u200b"),
            RotationField("Mission Assignments", _escalation_loot(escalation)),
            RotationField("Requisition Caches", _escalation_caches(escalation), inline=True),
            RotationField("Next Daily Reset", _discord_time(daily_reset), inline=True),
        )
    )
    invaded_item = by_kind.get("invaded_missions")
    weekly_fields = (
        RotationField("Escalation Mission Rotation", _escalation_missions(escalation)),
        RotationField("Invaded Mission Rotation", _invaded_rotation(invaded_item)),
        RotationField(
            "Legendary Completion Project", _item_value(by_kind.get("legendary_project"))
        ),
        RotationField(
            "Free Classified Assignment", _item_value(by_kind.get("classified_assignment"))
        ),
        RotationField("Next Weekly Reset", _discord_time(weekly_reset), inline=True),
    )
    descent_item = by_kind.get("descent_pool")
    descent_fields = (
        RotationField("Current Talent Pool", _descent_pool(descent_item)),
        *_descent_talent_fields(descent_item),
        RotationField("Rotation Cadence", "Every **3 days**.", inline=True),
        RotationField(
            "Next Pool Change",
            _discord_time(descent_reset) if descent_reset else "Calendar timing unavailable.",
            inline=True,
        ),
    )
    active, upcoming = _calendar_windows(calendar, now)
    seasonal_fields: list[RotationField] = [
        RotationField("Active Now", _event_list(active)),
        RotationField("Coming Up", _event_list(upcoming)),
    ]
    for item in web_items:
        if item.kind == "other_rotation":
            seasonal_fields.append(RotationField(item.title, _item_value(item)))
    dark_zone_fields = list(_dark_zone_fields(by_kind.get("dark_zone_mode")))
    dark_zone_fields.append(RotationField("━━ DARK ZONE VENDORS ━━", "\u200b"))
    for vendor in (
        "Dark Zone East Vendor",
        "Dark Zone South Vendor",
        "Dark Zone West Vendor",
    ):
        dark_zone_fields.extend(_vendor_fields(vendor, vendor_stock))
    vendor_fields: list[RotationField] = []
    if vendor_feed is not None:
        vendor_fields.append(
            RotationField(
                "Feed Last Confirmed",
                _discord_time(vendor_feed.updated_at),
                inline=True,
            )
        )
    for vendor in (
        "Cassie Mendoza",
        "Danny Weaver",
        "Countdown Requisition",
        "Clan Vendor",
    ):
        fields = _vendor_fields(vendor, vendor_stock)
        if fields:
            vendor_fields.extend(fields)
        else:
            vendor_fields.append(RotationField(vendor, _vendor_unavailable_message(vendor)))
    vendor_fields.append(
        RotationField("Next Vendor Reset", _discord_time(vendor_reset), inline=True)
    )
    timer_fields = (
        RotationField("Daily Targeted Loot & Projects", _discord_time(daily_reset)),
        RotationField("Weekly Invasion, Projects & Raids", _discord_time(weekly_reset)),
        RotationField("Vendor Stock", _discord_time(vendor_reset)),
        RotationField(
            "Descent Talent Pool",
            _discord_time(descent_reset) if descent_reset else "Calendar timing unavailable.",
        ),
    )
    date_label = now.strftime("%B %d, %Y")
    return (
        RotationPublication(
            key="daily-targeted-loot",
            channel_name="daily-targeted-loot",
            title=f"Daily Targeted Loot — {date_label}",
            description=(
                "Current map-backed regional assignments and the dated Escalation feed. "
                "Regional sections appear only when a complete current map is available."
            ),
            fields=tuple(daily_fields),
            images=tuple(daily_images[:4]),
            marker="ERIN_ROTATION:daily-targeted-loot",
        ),
        RotationPublication(
            key="weekly-mission-rotations",
            channel_name="weekly-mission-rotations",
            title=f"Weekly Mission Rotations — {date_label}",
            description="Current weekly activity assignments and completion projects.",
            fields=weekly_fields,
            marker="ERIN_ROTATION:weekly-mission-rotations",
        ),
        RotationPublication(
            key="descent-rotation",
            channel_name="descent-rotation",
            title=f"Descent Talent Rotation — {date_label}",
            description="Current named Descent pool and the next three-day rollover.",
            fields=descent_fields,
            marker="ERIN_ROTATION:descent-rotation",
        ),
        RotationPublication(
            key="seasonal-rotations",
            channel_name="seasonal-rotations",
            title=f"Seasonal Rotations — {date_label}",
            description="Active and upcoming seasonal, Manhunt, and event intelligence.",
            fields=tuple(seasonal_fields),
            marker="ERIN_ROTATION:seasonal-rotations",
        ),
        RotationPublication(
            key="dark-zone-rotations",
            channel_name="dark-zone-rotations",
            title=f"Dark Zone Rotations — {date_label}",
            description=(
                "Current faction, DZ type, targeted loot, and vendor inventory for each zone."
            ),
            fields=tuple(dark_zone_fields[:25]),
            marker="ERIN_ROTATION:dark-zone-rotations",
        ),
        RotationPublication(
            key="vendors",
            channel_name="vendors",
            title=f"Special Vendor Stock — {date_label}",
            description=(
                "Cassie Mendoza, Danny Weaver, Countdown Requisition, and Clan stock only."
            ),
            fields=tuple(vendor_fields[:25]),
            marker="ERIN_ROTATION:vendors",
        ),
        RotationPublication(
            key="reset-timers",
            channel_name="reset-timers",
            title="Division 2 Reset Timers",
            description="Reset timestamps automatically render in each member's local time.",
            fields=timer_fields,
            marker="ERIN_ROTATION:reset-timers",
        ),
    )


def _item_value(item: RotationResearchItem | None) -> str:
    if item is None:
        return "*A complete dated assignment is not available yet.*"
    return _limit("\n".join(f"• {detail}" for detail in item.details), 1024)


def _targeted_loot_fields(
    region_label: str,
    item: RotationResearchItem,
) -> tuple[RotationField, ...]:
    fields: list[RotationField] = [RotationField(f"━━ {region_label.upper()} ━━", "\u200b")]
    category_labels = (
        ("main_or_invaded_mission", "Main / Invaded Missions"),
        ("area", "Areas"),
        ("classified_assignment", "Classified Assignments"),
        ("raid", "Raids"),
        ("other_location", "Other Locations"),
    )
    for category, label in category_labels:
        assignments = sorted(
            (entry for entry in item.targeted_loot if entry.category == category),
            key=_targeted_loot_sort_key,
        )
        if not assignments:
            continue
        value = "\n".join(f"• **{entry.location}:** {entry.loot}" for entry in assignments)
        fields.append(RotationField(label, _limit(value, 1024)))
    if item.map_images and len(fields) == 1:
        fields.append(RotationField("Current Map", "See the dated map image below."))
    return tuple(fields)


def _targeted_loot_sort_key(entry: TargetedLootAssignment) -> tuple[int, str]:
    return entry.map_order, entry.location.casefold()


def _invaded_rotation(item: RotationResearchItem | None) -> str:
    if item is None or item.invaded is None:
        return "*Awaiting a complete dated set: 3 missions, 1 stronghold, then Tidal Basin.*"
    invaded = item.invaded
    lines = [
        *(
            f"**{index}. Main Mission:** {mission}"
            for index, mission in enumerate(invaded.main_missions, 1)
        ),
        f"**4. Stronghold:** {invaded.stronghold}",
        f"**5. Finale:** {invaded.final_mission}",
    ]
    return "\n".join(lines)


def _descent_pool(item: RotationResearchItem | None) -> str:
    if item is None or item.descent is None:
        return "*The current named pool has not been established from a dated source.*"
    return f"**{item.descent.name}**"


def _descent_talent_fields(item: RotationResearchItem | None) -> tuple[RotationField, ...]:
    if item is None or item.descent is None:
        return ()
    groups = (
        ("Offensive Talents", item.descent.offensive_talents),
        ("Defensive Talents", item.descent.defensive_talents),
        ("Utility Talents", item.descent.utility_talents),
        ("Exotic Talents", item.descent.exotic_talents),
    )
    return tuple(
        RotationField(label, _limit(" • ".join(talents), 1024))
        for label, talents in groups
        if talents
    )


def _dark_zone_fields(item: RotationResearchItem | None) -> tuple[RotationField, ...]:
    if item is None or len(item.dark_zones) != 3:
        return (
            RotationField(
                "Current DZ State",
                (
                    "ERIN is still searching dated in-game reports for all three zones; "
                    "older rotation patterns are not substituted for live data."
                ),
            ),
        )
    order = {"Dark Zone East": 0, "Dark Zone South": 1, "Dark Zone West": 2}
    fields: list[RotationField] = []
    for assignment in sorted(item.dark_zones, key=lambda entry: order[entry.zone]):
        fields.append(
            RotationField(
                assignment.zone,
                "\n".join(
                    (
                        f"**Faction:** {assignment.faction}",
                        f"**DZ Type:** {assignment.mode}",
                        f"**Targeted Loot:** {assignment.targeted_loot}",
                    )
                ),
            )
        )
    return tuple(fields)


def _merged_vendor_stock(
    feed: VendorFeed | None,
    researched: RotationResearchItem | None,
) -> tuple[VendorStockEntry, ...]:
    merged: dict[tuple[str, str, str], VendorStockEntry] = {}
    if researched is not None:
        for item in researched.vendor_stock:
            merged[(item.vendor, item.category, item.name.casefold())] = item
    if feed is not None:
        for item in feed.items:
            merged[(item.vendor, item.category, item.name.casefold())] = item
    return tuple(
        sorted(
            merged.values(),
            key=lambda item: (item.vendor, item.category, item.name.casefold()),
        )
    )


def _vendor_fields(
    vendor: str,
    stock: tuple[VendorStockEntry, ...],
) -> tuple[RotationField, ...]:
    entries = [item for item in stock if item.vendor == vendor]
    if not entries:
        return ()
    fields: list[RotationField] = []
    labels = {
        "gear": "Gear",
        "weapon": "Weapons",
        "mod": "Mods",
        "cache": "Caches",
        "other": "Other",
    }
    for category in ("gear", "weapon", "mod", "cache", "other"):
        lines = [_vendor_stock_line(item) for item in entries if item.category == category]
        chunks = _chunk_lines(lines, maximum=1024)
        for index, chunk in enumerate(chunks, 1):
            suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
            fields.append(
                RotationField(
                    f"{vendor} — {labels[category]}{suffix}",
                    chunk,
                )
            )
    return tuple(fields)


def _vendor_stock_line(item: VendorStockEntry) -> str:
    details = f" — {item.details}" if item.details else ""
    return _limit(f"• **{item.name}**{details}", 1000)


def _chunk_lines(lines: list[str], *, maximum: int) -> tuple[str, ...]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in lines:
        extra = len(line) + (1 if current else 0)
        if current and current_length + extra > maximum:
            chunks.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += len(line) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current))
    return tuple(chunks)


def _vendor_unavailable_message(vendor: str) -> str:
    if vendor == "Cassie Mendoza":
        return (
            "Cassie's stock is added after she opens on Wednesday. ERIN will publish it "
            "as soon as the dated weekly feed updates."
        )
    if vendor == "Danny Weaver":
        return (
            "Danny Weaver's Textile cache quantities are not exposed by the structured "
            "vendor feed. ERIN is checking dated community reports each research cycle."
        )
    return "The current structured inventory is temporarily unavailable."


def _escalation_loot(rotation: EscalationRotation | None) -> str:
    if rotation is None:
        return "*The dated Escalation feed is temporarily unavailable.*"
    return _limit(
        "\n".join(f"• **{mission}:** {loot}" for mission, loot in rotation.missions),
        1024,
    )


def _escalation_missions(rotation: EscalationRotation | None) -> str:
    if rotation is None:
        return "*The current Escalation mission playlist is temporarily unavailable.*"
    return "\n".join(f"• {mission}" for mission, _ in rotation.missions)


def _escalation_caches(rotation: EscalationRotation | None) -> str:
    if rotation is None:
        return "Unavailable"
    gear = rotation.prototype_gear_cache or "Unconfirmed"
    weapon = rotation.prototype_weapon_cache or "Unconfirmed"
    return f"Gear: **{gear.title()}**\nWeapon: **{weapon.upper()}**"


def _calendar_windows(
    events: tuple[CalendarEvent, ...], now: datetime
) -> tuple[tuple[CalendarEvent, ...], tuple[CalendarEvent, ...]]:
    scheduled = [
        event
        for event in events
        if event.scheduled_start is not None and event.scheduled_active_end is not None
    ]
    active = tuple(
        sorted(
            (
                event
                for event in scheduled
                if event.scheduled_start is not None
                and event.scheduled_active_end is not None
                and event.scheduled_start <= now < event.scheduled_active_end
            ),
            key=lambda event: event.scheduled_active_end or now,
        )[:8]
    )
    upcoming = tuple(
        sorted(
            (
                event
                for event in scheduled
                if event.scheduled_start is not None and event.scheduled_start > now
            ),
            key=lambda event: event.scheduled_start or now,
        )[:6]
    )
    return active, upcoming


def _event_list(events: tuple[CalendarEvent, ...]) -> str:
    if not events:
        return "*No dated events are available from the calendar feed.*"
    lines = []
    for event in events:
        boundary = event.scheduled_active_end or event.scheduled_start
        suffix = f" — until {_discord_time(boundary)}" if boundary else ""
        lines.append(f"• **{event.title}**{suffix}")
    return _limit("\n".join(lines), 1024)


def _descent_reset(events: tuple[CalendarEvent, ...], now: datetime) -> datetime | None:
    event = next((item for item in events if item.name == "Descent Playlist Rotation"), None)
    if event is None or event.cycle_seed is None or not event.cycle_duration:
        return None
    if now < event.cycle_seed:
        return event.cycle_seed
    elapsed = int((now - event.cycle_seed).total_seconds())
    cycles = elapsed // event.cycle_duration + 1
    return event.cycle_seed + timedelta(seconds=cycles * event.cycle_duration)


def _next_weekday_reset(now: datetime, *, weekday: int | None, hour: int) -> datetime:
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if weekday is None:
        return candidate if candidate > now else candidate + timedelta(days=1)
    days = (weekday - candidate.weekday()) % 7
    candidate += timedelta(days=days)
    return candidate if candidate > now else candidate + timedelta(days=7)


def _discord_time(value: datetime) -> str:
    timestamp = int(value.timestamp())
    return f"<t:{timestamp}:F> (<t:{timestamp}:R>)"


def _web_research_due(
    previous: datetime | None,
    now: datetime,
    *,
    hours: int,
    calendar: tuple[CalendarEvent, ...],
) -> bool:
    if previous is None:
        return True
    previous_utc = previous.astimezone(UTC)
    daily_reset = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if daily_reset > now:
        daily_reset -= timedelta(days=1)
    if previous_utc < daily_reset <= now:
        return True
    descent = next((event for event in calendar if event.name == "Descent Playlist Rotation"), None)
    if descent is not None and descent.cycle_seed is not None and descent.cycle_duration:
        if now >= descent.cycle_seed:
            elapsed = int((now - descent.cycle_seed).total_seconds())
            cycles = elapsed // descent.cycle_duration
            latest_descent_reset = descent.cycle_seed + timedelta(
                seconds=cycles * descent.cycle_duration
            )
            if previous_utc < latest_descent_reset <= now:
                return True
    return now - previous_utc >= timedelta(hours=hours)


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected an object")
    return {str(key): item for key, item in value.items()}


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _integer(value: object, *, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    parsed = _integer(value, default=0)
    return parsed if parsed > 0 else None


def _optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}{parsed.path.rstrip('/')}"


def _limit(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    return value[: maximum - 1].rstrip() + "…"

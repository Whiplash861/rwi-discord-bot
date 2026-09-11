from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from sqlalchemy import select

from rwi_bot.db.models import AuditEvent
from rwi_bot.db.session import Database


class ReleaseSection(StrEnum):
    CRITICAL = "Critical"
    PRIVACY_SAFETY = "Privacy & Safety"
    HIGH_IMPACT = "High Impact"
    NEW_FEATURES = "New Features"
    IMPROVEMENTS = "Improvements"
    FIXES = "Fixes"
    MAINTENANCE = "Reliability & Maintenance"


RELEASE_SECTION_ORDER = (
    ReleaseSection.CRITICAL,
    ReleaseSection.PRIVACY_SAFETY,
    ReleaseSection.HIGH_IMPACT,
    ReleaseSection.NEW_FEATURES,
    ReleaseSection.IMPROVEMENTS,
    ReleaseSection.FIXES,
    ReleaseSection.MAINTENANCE,
)


@dataclass(frozen=True, slots=True)
class ReleaseNote:
    section: ReleaseSection
    text: str
    community_visible: bool = True

    def __post_init__(self) -> None:
        clean = " ".join(self.text.split())
        if not clean:
            raise ValueError("Release notes cannot be empty.")
        if len(clean) > 500:
            raise ValueError("A release-note item cannot exceed 500 characters.")
        object.__setattr__(self, "text", clean)


@dataclass(frozen=True, slots=True)
class Release:
    release_id: str
    update_number: int
    version: str
    released_on: date
    notes: tuple[ReleaseNote, ...]
    automatic: bool = False
    legacy_release_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", self.release_id):
            raise ValueError("release_id must be a stable lowercase identifier.")
        if self.update_number < 1:
            raise ValueError("update_number must be positive.")
        if not re.fullmatch(r"V\d+\.\d+\.\d+", self.version):
            raise ValueError("Release versions must use Vmajor.minor.patch.")
        if not self.notes:
            raise ValueError("A release must contain at least one patch note.")
        if any(
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", release_id)
            for release_id in self.legacy_release_ids
        ):
            raise ValueError("legacy_release_ids must be stable lowercase identifiers.")

    @property
    def all_release_ids(self) -> tuple[str, ...]:
        return (self.release_id, *self.legacy_release_ids)


@dataclass(frozen=True, slots=True)
class DeploymentSnapshot:
    fingerprint: str
    module_hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class PublishedDeployment:
    release_id: str
    update_number: int
    version: str
    fingerprint: str
    module_hashes: dict[str, str]


class ReleaseHistoryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def published_in_channel(self, release_id: str, channel_id: int) -> bool:
        statement = (
            select(AuditEvent.details)
            .where(AuditEvent.event_type == "release.published")
            .where(AuditEvent.target_id == release_id)
            .order_by(AuditEvent.created_at.desc())
        )
        async with self.database.session() as session:
            rows = list(await session.scalars(statement))
        return any(str(details.get("channel_id")) == str(channel_id) for details in rows)

    async def published_version_in_channel(
        self,
        release_ids: tuple[str, ...],
        channel_id: int,
    ) -> str | None:
        statement = (
            select(AuditEvent.details)
            .where(AuditEvent.event_type == "release.published")
            .where(AuditEvent.target_id.in_(release_ids))
            .order_by(AuditEvent.created_at.desc())
        )
        async with self.database.session() as session:
            rows = list(await session.scalars(statement))
        for details in rows:
            if str(details.get("channel_id")) != str(channel_id):
                continue
            version = details.get("version")
            return version if isinstance(version, str) else None
        return None

    async def latest_deployment(self) -> PublishedDeployment | None:
        statement = (
            select(AuditEvent)
            .where(AuditEvent.event_type == "release.published")
            .order_by(AuditEvent.created_at.desc())
            .limit(50)
        )
        async with self.database.session() as session:
            events = list(await session.scalars(statement))
        for event in events:
            details = event.details
            fingerprint = details.get("deployment_fingerprint")
            module_hashes = details.get("module_hashes")
            update_number = details.get("update_number")
            version = details.get("version")
            if not (
                event.target_id
                and isinstance(fingerprint, str)
                and isinstance(module_hashes, dict)
                and isinstance(update_number, int)
                and isinstance(version, str)
            ):
                continue
            return PublishedDeployment(
                release_id=event.target_id,
                update_number=update_number,
                version=version,
                fingerprint=fingerprint,
                module_hashes={str(key): str(value) for key, value in module_hashes.items()},
            )
        return None


def render_release_description(release: Release) -> str:
    lines = [release.version, "", release.released_on.strftime("%B %d, %Y"), "", "__Patch Notes__"]
    for section in RELEASE_SECTION_ORDER:
        notes = [
            note.text
            for note in release.notes
            if note.section == section and note.community_visible
        ]
        if not notes:
            continue
        lines.extend(("", f"**{section.value}**", *(f"- {note}" for note in notes)))
    description = "\n".join(lines)
    if len(description) > 4000:
        raise ValueError("The release announcement exceeds Discord's safe embed size.")
    return description


def release_marker(release_id: str) -> str:
    return f"ERIN_RELEASE:{release_id}"


def deployment_snapshot(root: Path | None = None) -> DeploymentSnapshot:
    project_root = (root or Path.cwd()).resolve()
    hashes: dict[str, str] = {}

    def add_file(path: Path, label: str) -> None:
        if path.is_file():
            hashes[label.replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()

    def add_tree(path: Path, label: str, pattern: str = "*.py") -> None:
        if not path.is_dir():
            return
        for child in sorted(path.rglob(pattern)):
            add_file(child, f"{label}/{child.relative_to(path).as_posix()}")

    source_root = project_root / "src" / "rwi_bot"
    if not source_root.is_dir():
        source_root = Path(__file__).resolve().parents[1]
    add_tree(source_root, "src/rwi_bot")
    add_tree(project_root / "alembic", "alembic")
    add_tree(project_root / "scripts", "scripts", "*")
    for filename in ("pyproject.toml", "README.md", "alembic.ini", "Dockerfile", "compose.yml"):
        add_file(project_root / filename, filename)

    release_inputs = project_root / "release-inputs"
    if release_inputs.is_dir():
        for child in sorted(path for path in release_inputs.rglob("*") if path.is_file()):
            add_file(child, child.relative_to(release_inputs).as_posix())

    digest = hashlib.sha256()
    for label, file_hash in sorted(hashes.items()):
        digest.update(label.encode())
        digest.update(b"\0")
        digest.update(file_hash.encode())
        digest.update(b"\0")
    return DeploymentSnapshot(fingerprint=digest.hexdigest(), module_hashes=hashes)


def automatic_release(
    snapshot: DeploymentSnapshot,
    previous: PublishedDeployment | None,
    *,
    released_on: date,
) -> Release:
    update_number = 1 if previous is None else previous.update_number + 1
    version = "V1.0.0" if previous is None else _increment_patch(previous.version)
    previous_hashes = {} if previous is None else previous.module_hashes
    changed = {
        path
        for path in set(snapshot.module_hashes) | set(previous_hashes)
        if snapshot.module_hashes.get(path) != previous_hashes.get(path)
    }
    notes: list[ReleaseNote] = []

    # Public notes describe affected player-facing features, not administrative internals.
    areas = (
        (
            ("privacy",),
            ReleaseSection.PRIVACY_SAFETY,
            "Member privacy, saved-profile export or learning controls changed.",
        ),
        (
            ("services/qa", "ai/prompts", "ai/client"),
            ReleaseSection.IMPROVEMENTS,
            "Question interpretation, evidence handling or answer generation changed.",
        ),
        (
            ("member_profiles", "onboarding"),
            ReleaseSection.IMPROVEMENTS,
            "Introductions, saved player preferences or personalized advice changed.",
        ),
        (
            ("community.py", "community_learning"),
            ReleaseSection.IMPROVEMENTS,
            "Community build references or gameplay contribution handling changed.",
        ),
        (
            ("video_inspection",),
            ReleaseSection.IMPROVEMENTS,
            "Screenshot or gameplay-video inspection changed.",
        ),
        (
            ("rotations",),
            ReleaseSection.IMPROVEMENTS,
            "Rotation collection, reset handling or rotation channel displays changed.",
        ),
        (
            ("announcements", "cogs/autonomy"),
            ReleaseSection.IMPROVEMENTS,
            "Important developer update announcements changed.",
        ),
        (
            ("operations",),
            ReleaseSection.IMPROVEMENTS,
            "Raid and Incursion scheduling or attendance coordination changed.",
        ),
        (
            ("cogs/releases", "data/releases"),
            ReleaseSection.NEW_FEATURES,
            "Community patch-note presentation changed.",
        ),
        (
            ("data/red_horizon", "services/knowledge", "autonomous_research"),
            ReleaseSection.IMPROVEMENTS,
            "The local Division 2 research library or current-game knowledge checks changed.",
        ),
    )
    for fragments, section, description in areas:
        if _matches(changed, fragments):
            notes.append(ReleaseNote(section, description))
    if _matches(changed, ("src/rwi_bot/db/", "alembic/")):
        notes.append(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Persistent data structures changed.",
                community_visible=False,
            )
        )
    if not notes:
        notes.append(
            ReleaseNote(
                ReleaseSection.MAINTENANCE, "Internal deployment changes.", community_visible=False
            )
        )
    return Release(
        release_id=f"automatic-{snapshot.fingerprint[:16]}",
        update_number=update_number,
        version=version,
        released_on=released_on,
        notes=tuple(notes),
        automatic=True,
    )


def _matches(paths: set[str], fragments: tuple[str, ...]) -> bool:
    return any(fragment in path for path in paths for fragment in fragments)


def _increment_patch(version: str) -> str:
    match = re.fullmatch(r"V(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        return "V1.0.0"
    major, minor, patch = (int(value) for value in match.groups())
    return f"V{major}.{minor}.{patch + 1}"

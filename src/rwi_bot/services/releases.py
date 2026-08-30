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

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", self.release_id):
            raise ValueError("release_id must be a stable lowercase identifier.")
        if self.update_number < 1:
            raise ValueError("update_number must be positive.")
        if not re.fullmatch(r"V\d+\.\d+\.\d+", self.version):
            raise ValueError("Release versions must use Vmajor.minor.patch.")
        if not self.notes:
            raise ValueError("A release must contain at least one patch note.")


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
        notes = [note.text for note in release.notes if note.section == section]
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

    if _matches(changed, ("privacy", "moderation", "maintenance", "budget", "ai/client")):
        notes.append(
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Privacy, moderation, maintenance, or cost-control safeguards changed.",
            )
        )
    if _matches(changed, ("src/rwi_bot/db/", "alembic/")):
        notes.append(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "ERIN's persistent data layer or database migrations changed.",
            )
        )
    if _matches(
        changed,
        ("src/rwi_bot/services/qa", "services/knowledge", "src/rwi_bot/data/", "ai/prompts"),
    ):
        notes.append(
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN's game-intelligence, knowledge, or answer systems changed.",
            )
        )
    if _matches(changed, ("src/rwi_bot/bot/", "src/rwi_bot/cogs/")):
        notes.append(
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Discord commands, channels, or community interactions changed.",
            )
        )
    if _matches(
        changed,
        ("src/rwi_bot/config", "preflight", "Dockerfile", "compose.yml", "scripts/"),
    ):
        notes.append(
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Runtime configuration, health checks, or deployment tooling changed.",
            )
        )
    if not notes:
        notes.append(
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "ERIN was deployed with internal application improvements.",
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

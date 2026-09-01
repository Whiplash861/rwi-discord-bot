from __future__ import annotations

from datetime import date

from rwi_bot.cogs.releases import release_embed
from rwi_bot.data.releases import RELEASES
from rwi_bot.services.releases import (
    DeploymentSnapshot,
    PublishedDeployment,
    ReleaseSection,
    automatic_release,
    deployment_snapshot,
    render_release_description,
)


def test_authored_release_catalog_is_unique_and_uses_requested_format() -> None:
    ids = {release.release_id for release in RELEASES}
    numbers = {release.update_number for release in RELEASES}
    versions = {release.version for release in RELEASES}
    release = RELEASES[0]

    assert len(ids) == len(RELEASES)
    assert len(numbers) == len(RELEASES)
    assert len(versions) == len(RELEASES)
    assert [release.update_number for release in RELEASES] == list(range(1, len(RELEASES) + 1))
    assert release.update_number == 1
    assert release.version == "V0.1.0"
    assert release.released_on == date(2026, 8, 30)

    description = render_release_description(release)
    embed = release_embed(release)
    assert embed.title == "ERIN Update 1"
    assert description.startswith("V0.1.0\n\nAugust 30, 2026\n\n__Patch Notes__")
    assert description.index("**Privacy & Safety**") < description.index("**High Impact**")
    assert description.index("**High Impact**") < description.index("**New Features**")
    assert embed.footer.text == "ERIN_RELEASE:erin-update-1"
    assert release.legacy_release_ids == ("erin-update-1-v1.22.333",)

    latest = RELEASES[-1]
    assert latest.update_number == 24
    assert latest.version == "V0.1.23"
    assert render_release_description(latest).startswith(
        "V0.1.23\n\nAugust 31, 2026\n\n__Patch Notes__"
    )


def test_deployment_snapshot_changes_with_application_source(tmp_path) -> None:
    package = tmp_path / "src" / "rwi_bot"
    package.mkdir(parents=True)
    source = package / "feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    first = deployment_snapshot(tmp_path)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    second = deployment_snapshot(tmp_path)

    assert first.fingerprint != second.fingerprint
    assert "src/rwi_bot/feature.py" in second.module_hashes


def test_automatic_release_increments_version_and_classifies_changed_components() -> None:
    previous = PublishedDeployment(
        release_id="erin-update-1",
        update_number=1,
        version="V0.1.0",
        fingerprint="a" * 64,
        module_hashes={
            "src/rwi_bot/db/models.py": "old-db",
            "src/rwi_bot/cogs/privacy.py": "old-privacy",
        },
    )
    snapshot = DeploymentSnapshot(
        fingerprint="b" * 64,
        module_hashes={
            "src/rwi_bot/db/models.py": "new-db",
            "src/rwi_bot/cogs/privacy.py": "new-privacy",
            "src/rwi_bot/cogs/releases.py": "new-channel",
        },
    )

    release = automatic_release(snapshot, previous, released_on=date(2026, 8, 31))

    assert release.release_id == "automatic-bbbbbbbbbbbbbbbb"
    assert release.update_number == 2
    assert release.version == "V0.1.1"
    assert release.automatic
    sections = {note.section for note in release.notes}
    assert ReleaseSection.PRIVACY_SAFETY in sections
    assert ReleaseSection.HIGH_IMPACT in sections
    assert ReleaseSection.NEW_FEATURES in sections

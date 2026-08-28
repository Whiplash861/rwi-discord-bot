from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rwi_bot.services.maintenance import MaintenanceManager, ResumeCheck


@pytest.mark.asyncio
async def test_halt_survives_manager_restart(tmp_path: Path) -> None:
    manager = MaintenanceManager(tmp_path)
    await manager.load()
    halted = await manager.halt(actor_id=7, reason="failure loop")

    restarted = MaintenanceManager(tmp_path)
    loaded = await restarted.load()

    assert halted.halted
    assert loaded.halted
    assert loaded.reason == "failure loop"
    assert loaded.actor_id == 7
    assert loaded.revision == 1


@pytest.mark.asyncio
async def test_invalid_state_fails_closed(tmp_path: Path) -> None:
    tmp_path.joinpath("maintenance.json").write_text("not-json", encoding="utf-8")

    state = await MaintenanceManager(tmp_path).load()

    assert state.halted
    assert state.fail_closed
    assert "could not be verified" in (state.reason or "")


@pytest.mark.asyncio
async def test_failed_resume_check_keeps_halt_active(tmp_path: Path) -> None:
    manager = MaintenanceManager(tmp_path)
    await manager.load()
    await manager.halt(actor_id=7, reason="database failure")

    async def checks() -> list[ResumeCheck]:
        return [ResumeCheck(name="database", passed=False, detail="unavailable")]

    state, results = await manager.resume(actor_id=7, checks=checks)

    assert state.halted
    assert not results[0].passed


@pytest.mark.asyncio
async def test_new_halt_wins_over_in_progress_resume(tmp_path: Path) -> None:
    manager = MaintenanceManager(tmp_path)
    await manager.load()
    await manager.halt(actor_id=7, reason="first halt")
    checks_started = asyncio.Event()
    release_checks = asyncio.Event()

    async def checks() -> list[ResumeCheck]:
        checks_started.set()
        await release_checks.wait()
        return [ResumeCheck(name="database", passed=True, detail="available")]

    resume_task = asyncio.create_task(manager.resume(actor_id=7, checks=checks))
    await checks_started.wait()
    newer = await manager.halt(actor_id=8, reason="newer halt")
    release_checks.set()
    state, results = await resume_task

    assert state.halted
    assert state.event_id == newer.event_id
    assert state.reason == "newer halt"
    assert any(result.name == "maintenance_revision" for result in results)

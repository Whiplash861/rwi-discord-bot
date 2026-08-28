from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MaintenanceState(BaseModel):
    halted: bool = False
    reason: str | None = None
    actor_id: int | None = None
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_id: UUID = Field(default_factory=uuid4)
    revision: int = 0
    fail_closed: bool = False


class ResumeCheck(BaseModel):
    name: str
    passed: bool
    detail: str


ResumeChecks = Callable[[], Awaitable[list[ResumeCheck]]]


class MaintenanceManager:
    """Durable emergency state independent of Discord and PostgreSQL.

    A missing state file means first boot and therefore online. An unreadable or invalid
    state file fails closed: the command listener may start, but paid/background work may not.
    """

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.state_path = runtime_dir / "maintenance.json"
        self._lock = asyncio.Lock()
        self._state = MaintenanceState()

    @property
    def state(self) -> MaintenanceState:
        return self._state.model_copy(deep=True)

    @property
    def halted(self) -> bool:
        return self._state.halted

    async def load(self) -> MaintenanceState:
        async with self._lock:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            if not self.state_path.exists():
                await asyncio.to_thread(self._atomic_write, self._state)
                return self.state
            try:
                raw = await asyncio.to_thread(self.state_path.read_text, encoding="utf-8")
                self._state = MaintenanceState.model_validate_json(raw)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._state = MaintenanceState(
                    halted=True,
                    fail_closed=True,
                    reason=f"Maintenance state could not be verified: {type(exc).__name__}",
                    revision=self._state.revision + 1,
                )
            return self.state

    async def halt(self, *, actor_id: int, reason: str) -> MaintenanceState:
        reason = reason.strip()
        if not reason:
            raise ValueError("A halt reason is required.")
        async with self._lock:
            self._state = MaintenanceState(
                halted=True,
                actor_id=actor_id,
                reason=reason[:1000],
                revision=self._state.revision + 1,
            )
            await asyncio.to_thread(self._atomic_write, self._state)
            return self.state

    async def resume(
        self,
        *,
        actor_id: int,
        checks: ResumeChecks,
        force: bool = False,
    ) -> tuple[MaintenanceState, list[ResumeCheck]]:
        starting_event_id = self._state.event_id
        results = await checks()
        if any(not check.passed for check in results) and not force:
            return self.state, results
        async with self._lock:
            if self._state.event_id != starting_event_id:
                results.append(
                    ResumeCheck(
                        name="maintenance_revision",
                        passed=False,
                        detail="Maintenance state changed while health checks were running.",
                    )
                )
                return self.state, results
            self._state = MaintenanceState(
                halted=False,
                actor_id=actor_id,
                reason="Force-resumed despite failed checks" if force else "Health checks passed",
                revision=self._state.revision + 1,
            )
            await asyncio.to_thread(self._atomic_write, self._state)
            return self.state, results

    def _atomic_write(self, state: MaintenanceState) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(f".{os.getpid()}.tmp")
        payload = state.model_dump_json(indent=2)
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.state_path)
        finally:
            temporary.unlink(missing_ok=True)

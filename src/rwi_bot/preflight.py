from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import text

from rwi_bot.config import Settings, get_settings
from rwi_bot.db.session import Database
from rwi_bot.services.maintenance import MaintenanceManager


@dataclass(frozen=True, slots=True)
class PreflightResult:
    name: str
    passed: bool
    detail: str


async def run_preflight(settings: Settings) -> list[PreflightResult]:
    results: list[PreflightResult] = []
    maintenance = MaintenanceManager(settings.runtime_dir)
    state = await maintenance.load()
    results.append(
        PreflightResult(
            name="maintenance_state",
            passed=not state.fail_closed,
            detail=(
                "Durable maintenance state loaded."
                if not state.fail_closed
                else "Durable maintenance state is unreadable; RWI failed closed."
            ),
        )
    )

    database = Database(settings.database_url.get_secret_value())
    try:
        async with database.session() as session:
            await session.execute(text("SELECT 1"))
        results.append(
            PreflightResult(
                name="database",
                passed=True,
                detail="PostgreSQL responded.",
            )
        )
    except Exception as exc:
        results.append(
            PreflightResult(
                name="database",
                passed=False,
                detail=f"PostgreSQL check failed: {type(exc).__name__}",
            )
        )
    finally:
        await database.dispose()
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate RWI bot runtime dependencies.")
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Emit a compact container-health result.",
    )
    return parser


async def _run(arguments: argparse.Namespace) -> int:
    try:
        settings = get_settings()
    except ValidationError as exc:
        missing = sorted(str(error["loc"][0]) for error in exc.errors() if error.get("loc"))
        label = ", ".join(missing) if missing else "runtime configuration"
        print(f"FAIL configuration: invalid or missing fields ({label})")
        return 1

    results = await run_preflight(settings)
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"{marker} {result.name}: {result.detail}")
    return 0 if all(result.passed for result in results) else 1


def cli(argv: Sequence[str] | None = None) -> None:
    arguments = _parser().parse_args(argv)
    if not arguments.healthcheck:
        print("RWI preflight")
    raise SystemExit(asyncio.run(_run(arguments)))


if __name__ == "__main__":
    cli(sys.argv[1:])

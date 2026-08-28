from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from rwi_bot.bot.checks import is_commander, is_maintenance_operator
from rwi_bot.bot.names import DIVISION_COMMANDER, DIVISION_COORDINATOR, TECHNICIAN


def member(member_id: int, *roles: str, administrator: bool = False) -> Any:
    return SimpleNamespace(
        id=member_id,
        roles=[SimpleNamespace(name=name) for name in roles],
        guild_permissions=SimpleNamespace(administrator=administrator),
    )


@pytest.mark.parametrize(
    "candidate",
    [
        member(10, TECHNICIAN),
        member(11, DIVISION_COMMANDER),
        member(99),
    ],
)
def test_authorized_maintenance_operators(candidate: Any) -> None:
    assert is_maintenance_operator(cast(Any, candidate), owner_user_id=99)


@pytest.mark.parametrize(
    "candidate",
    [
        member(10, DIVISION_COORDINATOR),
        member(11, administrator=True),
        member(12),
    ],
)
def test_unauthorized_roles_cannot_control_maintenance(candidate: Any) -> None:
    assert not is_maintenance_operator(cast(Any, candidate), owner_user_id=99)


def test_commander_check_does_not_trust_unrelated_administrator_role() -> None:
    assert not is_commander(cast(Any, member(10, administrator=True)), owner_user_id=99)
    assert is_commander(cast(Any, member(10, DIVISION_COMMANDER)), owner_user_id=99)

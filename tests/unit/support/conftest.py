"""Fixtures for the support tests.

Support business hours are in US Central Time (UTC-6 in the sample), so
the helpers here build UTC datetimes from Central wall-clock times.
The week used in the tests: Monday 2026-01-05 to Friday 2026-01-09.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from acme_cloud.support.models import from_central


def central(day: int, hour: int, minute: int = 0, month: int = 1) -> datetime:
    """UTC datetime for a Central Time wall-clock moment in January 2026."""
    return from_central(datetime(2026, month, day, hour, minute))


@pytest.fixture
def at_central():
    """Return the ``central(day, hour, minute)`` helper."""
    return central


class FakeAudit:
    """Records ``record(event_type, actor_id, account_id, workspace_id, **metadata)`` calls."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, str | None, dict]] = []

    def record(self, event_type: str, actor_id: str, account_id: str,
               workspace_id: str | None = None, **metadata: object) -> None:
        self.events.append((event_type, actor_id, account_id, workspace_id, metadata))


@pytest.fixture
def audit() -> FakeAudit:
    return FakeAudit()

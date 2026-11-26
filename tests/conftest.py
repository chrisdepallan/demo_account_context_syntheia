"""Fixtures shared by every test."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from acme_cloud.common import FixedClock, IdGenerator


@pytest.fixture
def clock() -> FixedClock:
    """A clock fixed at Monday 2026-01-05 09:00 UTC. Move it with ``advance``."""
    return FixedClock(datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc))


@pytest.fixture
def ids() -> IdGenerator:
    """An ID generator with a fixed seed, so IDs are the same on every run."""
    return IdGenerator(seed=2026)

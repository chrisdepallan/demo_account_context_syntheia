"""Clocks and support business time (Monday-Friday, 08:00-18:00 Central Time)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from acme_cloud.common.clock import (
    BUSINESS_HOURS_PER_DAY, FixedClock, SystemClock, add_business_days,
    add_business_hours, is_business_time, next_business_moment,
)

MONDAY = datetime(2026, 1, 5)    # naive Central Time
FRIDAY = datetime(2026, 1, 9)
SATURDAY = datetime(2026, 1, 10)
NEXT_MONDAY = datetime(2026, 1, 12)


def at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute)


def test_fixture_clock_starts_on_monday_morning_utc(clock):
    assert clock.now() == datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
    assert clock.now().weekday() == 0


def test_fixed_clock_only_moves_when_told(clock):
    start = clock.now()
    assert clock.now() == start
    assert clock.advance(days=14) == start + timedelta(days=14)
    assert clock.advance(hours=1, minutes=30) == start + timedelta(days=14, hours=1, minutes=30)


def test_fixed_clock_treats_naive_datetimes_as_utc():
    clock = FixedClock(datetime(2026, 3, 1, 12, 0))
    assert clock.now().tzinfo is timezone.utc
    clock.set(datetime(2026, 4, 1, 8, 0))
    assert clock.now() == datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)


def test_fixed_clock_has_a_default_start():
    assert FixedClock().now().tzinfo is not None


def test_system_clock_returns_aware_utc_time():
    assert SystemClock().now().utcoffset() == timedelta(0)


def test_a_business_day_is_ten_business_hours():
    assert BUSINESS_HOURS_PER_DAY == 10


@pytest.mark.parametrize(
    ("moment", "expected"),
    [(at(MONDAY, 8), True),         # opening time counts
     (at(MONDAY, 7, 59), False),
     (at(MONDAY, 17, 59), True),
     (at(MONDAY, 18), False),       # closing time does not
     (at(FRIDAY, 12), True),
     (at(SATURDAY, 12), False)],
)
def test_is_business_time(moment, expected):
    assert is_business_time(moment) is expected


@pytest.mark.parametrize(
    ("moment", "expected"),
    [(at(MONDAY, 10, 30), at(MONDAY, 10, 30)),   # already inside
     (at(MONDAY, 7), at(MONDAY, 8)),             # before opening
     (at(MONDAY, 19), at(MONDAY + timedelta(days=1), 8)),
     (at(FRIDAY, 18, 30), at(NEXT_MONDAY, 8)),   # Friday evening
     (at(SATURDAY, 12), at(NEXT_MONDAY, 8))],    # weekend
)
def test_next_business_moment(moment, expected):
    assert next_business_moment(moment) == expected


def test_business_hours_skip_the_weekend():
    """A ticket opened Friday 17:00 with a 4-hour target is due Monday 11:00."""
    assert add_business_hours(at(FRIDAY, 17), 4) == at(NEXT_MONDAY, 11)


def test_business_hours_inside_one_day():
    assert add_business_hours(at(MONDAY, 9), 4) == at(MONDAY, 13)
    assert add_business_hours(at(MONDAY, 9), 0.5) == at(MONDAY, 9, 30)


def test_business_hours_start_counting_at_the_next_opening():
    assert add_business_hours(at(SATURDAY, 15), 1) == at(NEXT_MONDAY, 9)


@pytest.mark.parametrize(
    ("days", "expected"),
    [(1, at(MONDAY + timedelta(days=1), 9)),
     (3, at(MONDAY + timedelta(days=3), 9)),
     (5, at(NEXT_MONDAY, 9))],    # five business days is one calendar week
)
def test_business_days_are_ten_hours_each(days, expected):
    assert add_business_days(at(MONDAY, 9), days) == expected

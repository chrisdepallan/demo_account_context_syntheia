"""Clocks and business-time helpers.

Services never call ``datetime.now()`` directly. They take a ``Clock`` so
tests can move time forward with ``FixedClock.advance``.

Support business hours are Monday to Friday, 08:00 to 18:00 US Central Time.
To keep the sample free of time-zone data, business-time helpers work on
naive "Central Time" datetimes; everything else uses aware UTC datetimes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

BUSINESS_DAY_START_HOUR = 8
BUSINESS_DAY_END_HOUR = 18
BUSINESS_HOURS_PER_DAY = BUSINESS_DAY_END_HOUR - BUSINESS_DAY_START_HOUR  # 10


class Clock:
    """Interface: anything with a ``now()`` that returns an aware UTC datetime."""

    def now(self) -> datetime:  # pragma: no cover - interface
        raise NotImplementedError


class SystemClock(Clock):
    """The real clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    """A clock that only moves when told to. Used in tests and examples."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> datetime:
        """Move the clock forward, for example ``advance(days=14)``."""
        self._now = self._now + timedelta(**kwargs)
        return self._now

    def set(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        self._now = moment


def is_business_time(moment: datetime) -> bool:
    """True when ``moment`` (Central Time) is inside support business hours."""
    return moment.weekday() < 5 and BUSINESS_DAY_START_HOUR <= moment.hour < BUSINESS_DAY_END_HOUR


def next_business_moment(moment: datetime) -> datetime:
    """Return ``moment`` if inside business hours, else the next opening time."""
    current = moment
    if current.weekday() < 5 and current.hour < BUSINESS_DAY_START_HOUR:
        return current.replace(hour=BUSINESS_DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if is_business_time(current):
        return current
    current = (current + timedelta(days=1)).replace(
        hour=BUSINESS_DAY_START_HOUR, minute=0, second=0, microsecond=0
    )
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def add_business_hours(start: datetime, hours: float) -> datetime:
    """Add ``hours`` of business time to ``start`` (Central Time).

    Time outside 08:00-18:00 Monday-Friday does not count. A ticket opened
    on Friday at 17:00 with a 4-hour target is due on Monday at 11:00.
    """
    current = next_business_moment(start)
    remaining = timedelta(hours=hours)
    while remaining > timedelta(0):
        end_of_day = current.replace(hour=BUSINESS_DAY_END_HOUR, minute=0, second=0, microsecond=0)
        available = end_of_day - current
        if remaining <= available:
            return current + remaining
        remaining -= available
        current = next_business_moment(end_of_day)
    return current


def add_business_days(start: datetime, days: int) -> datetime:
    """Add whole business days. One business day is 10 business hours."""
    return add_business_hours(start, days * BUSINESS_HOURS_PER_DAY)

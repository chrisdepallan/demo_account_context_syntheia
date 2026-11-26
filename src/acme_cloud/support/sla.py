"""First-response targets (SLA) by plan and priority.

| Priority | Free | Starter | Pro | Business | Enterprise |
|----------|------|---------|-----|----------|------------|
| P1 | 3 business days | 2 business days | 4 business hours | 1 business hour | 30 minutes, 24/7 |
| P2 | 3 business days | 2 business days | 8 business hours | 4 business hours | 2 hours |
| P3 | 3 business days | 2 business days | 2 business days | 1 business day | 1 business day |
| P4 | 3 business days | 3 business days | 3 business days | 3 business days | 3 business days |

- Business hours are Monday to Friday, 08:00 to 18:00 US Central Time. A
  business day is 10 business hours. Time outside business hours does
  not count: a Pro P1 opened on Friday at 17:00 is due on Monday at 11:00.
- Enterprise P1 (30 minutes) and P2 (2 hours) are counted in clock time,
  24 hours a day, 7 days a week.
- A target is breached when the first response comes after the due
  time, or when the due time has passed with no response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from acme_cloud.common.clock import add_business_days, add_business_hours
from acme_cloud.common.enums import Plan
from acme_cloud.support.models import Priority, from_central, to_central


class SlaUnit(str, Enum):
    BUSINESS_DAYS = "business_days"
    BUSINESS_HOURS = "business_hours"
    #: Clock minutes, counted 24/7 (Enterprise P1 and P2 only).
    CLOCK_MINUTES = "clock_minutes"


@dataclass(frozen=True)
class SlaTarget:
    amount: int
    unit: SlaUnit

    @property
    def is_24x7(self) -> bool:
        return self.unit is SlaUnit.CLOCK_MINUTES

    def describe(self) -> str:
        """Text used in ticket confirmations, for example ``4 business hours``."""
        if self.unit is SlaUnit.CLOCK_MINUTES:
            if self.amount % 60 == 0:
                hours = self.amount // 60
                return f"{hours} hour{'s' if hours != 1 else ''}, 24/7"
            return f"{self.amount} minutes, 24/7"
        word = "business day" if self.unit is SlaUnit.BUSINESS_DAYS else "business hour"
        return f"{self.amount} {word}{'s' if self.amount != 1 else ''}"


def _days(n: int) -> SlaTarget:
    return SlaTarget(n, SlaUnit.BUSINESS_DAYS)


def _hours(n: int) -> SlaTarget:
    return SlaTarget(n, SlaUnit.BUSINESS_HOURS)


def _clock(minutes: int) -> SlaTarget:
    return SlaTarget(minutes, SlaUnit.CLOCK_MINUTES)


#: The first-response table. Rows are priorities, columns are plans.
FIRST_RESPONSE_TARGETS: dict[Priority, dict[Plan, SlaTarget]] = {
    Priority.P1: {Plan.FREE: _days(3), Plan.STARTER: _days(2), Plan.PRO: _hours(4),
                  Plan.BUSINESS: _hours(1), Plan.ENTERPRISE: _clock(30)},
    Priority.P2: {Plan.FREE: _days(3), Plan.STARTER: _days(2), Plan.PRO: _hours(8),
                  Plan.BUSINESS: _hours(4), Plan.ENTERPRISE: _clock(120)},
    Priority.P3: {Plan.FREE: _days(3), Plan.STARTER: _days(2), Plan.PRO: _days(2),
                  Plan.BUSINESS: _days(1), Plan.ENTERPRISE: _days(1)},
    Priority.P4: {plan: _days(3) for plan in Plan},
}


def first_response_target(plan: Plan, priority: Priority) -> SlaTarget:
    """Return the first-response target for a ticket of ``priority`` on ``plan``."""
    return FIRST_RESPONSE_TARGETS[priority][plan]


def first_response_due(plan: Plan, priority: Priority, opened_at: datetime) -> datetime:
    """When the first response is due for a ticket opened at ``opened_at`` (UTC).

    Business-time targets are worked out in Central Time with
    ``add_business_hours`` / ``add_business_days``; Enterprise P1 and P2
    simply add clock time. The result is an aware UTC datetime.
    """
    target = first_response_target(plan, priority)
    if target.unit is SlaUnit.CLOCK_MINUTES:
        return opened_at + timedelta(minutes=target.amount)
    local = to_central(opened_at)
    if target.unit is SlaUnit.BUSINESS_HOURS:
        return from_central(add_business_hours(local, target.amount))
    return from_central(add_business_days(local, target.amount))


def is_breached(due: datetime, now: datetime, responded_at: datetime | None = None) -> bool:
    """True when the first-response target was missed.

    A response exactly at the due time is on time.
    """
    if responded_at is not None:
        return responded_at > due
    return now > due


def time_remaining(due: datetime, now: datetime) -> timedelta:
    """Clock time left until ``due`` (negative once the target is breached)."""
    return due - now

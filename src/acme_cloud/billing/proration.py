"""Day-based proration for plan upgrades and seat changes.

The rule: a prorated amount is

    full-period price x whole days remaining / days in the period

rounded to the nearest cent, half up (0.5 cent rounds up).

- "Days in the period" is the number of calendar days between the period
  start and the period end: 31 for a monthly period that starts on 5 January,
  365 for an annual period in a normal year.
- "Whole days remaining" counts calendar days from today to the period end.
  The day of the change counts as remaining, so a change made on the first
  day of the period costs the full price and a change on the last day costs
  one day.

Where it is used:

- Upgrade: the difference between the new and the old seat price, times the
  seats, prorated; charged at once.
- Adding seats: seat price times seats added, prorated; charged at once.
- Removing seats: seat price times seats removed, prorated; credited on the
  next invoice (not paid out).

Example: 4 seats upgraded from Starter ($8) to Pro ($20) with 16 of 31 days
left cost (20 - 8) x 4 x 16 / 31 = $24.774..., charged as $24.77.
"""

from __future__ import annotations

from datetime import datetime

from acme_cloud.common.errors import ValidationError
from acme_cloud.common.money import Money


def days_in_period(period_start: datetime, period_end: datetime) -> int:
    """Calendar days in a billing period (28 to 31 monthly, 365 or 366 annual)."""
    days = (period_end.date() - period_start.date()).days
    if days <= 0:
        raise ValidationError("billing period must end after it starts")
    return days


def days_remaining(now: datetime, period_end: datetime) -> int:
    """Whole days from ``now`` to the period end; never negative."""
    return max((period_end.date() - now.date()).days, 0)


def prorate(amount: Money, remaining_days: int, period_days: int) -> Money:
    """Return ``amount x remaining_days / period_days``, half up to the cent."""
    if period_days <= 0:
        raise ValidationError("days in the period must be positive")
    if not 0 <= remaining_days <= period_days:
        raise ValidationError("days remaining must be between 0 and the days in the period")
    return amount.prorate(remaining_days, period_days)


def upgrade_charge(
    old_seat_price: Money, new_seat_price: Money, seats: int,
    remaining_days: int, period_days: int,
) -> Money:
    """Charge for an immediate upgrade: the prorated price difference for all seats."""
    if seats < 1:
        raise ValidationError("seats must be at least 1")
    difference = (new_seat_price - old_seat_price) * seats
    if difference.is_negative:
        raise ValidationError("an upgrade cannot lower the seat price")
    return prorate(difference, remaining_days, period_days)


def seat_add_charge(
    seat_price: Money, seats_added: int, remaining_days: int, period_days: int,
) -> Money:
    """Charge for seats added mid-period, prorated by day and charged at once."""
    if seats_added < 1:
        raise ValidationError("add at least one seat")
    return prorate(seat_price * seats_added, remaining_days, period_days)


def seat_removal_credit(
    seat_price: Money, seats_removed: int, remaining_days: int, period_days: int,
) -> Money:
    """Credit (a positive amount) for removed seats, applied to the next invoice."""
    if seats_removed < 1:
        raise ValidationError("remove at least one seat")
    return prorate(seat_price * seats_removed, remaining_days, period_days)

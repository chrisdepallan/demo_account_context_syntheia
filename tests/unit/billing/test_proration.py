"""Proration: whole days remaining / days in the period, half up to the cent."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from acme_cloud.billing import proration
from acme_cloud.common.errors import ValidationError
from acme_cloud.common.money import Money

UTC = timezone.utc
PERIOD_START = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 2, 5, 9, 0, tzinfo=UTC)


def test_monthly_period_starting_5_january_has_31_days():
    assert proration.days_in_period(PERIOD_START, PERIOD_END) == 31


def test_annual_period_in_a_normal_year_has_365_days():
    end = datetime(2027, 1, 5, 9, 0, tzinfo=UTC)
    assert proration.days_in_period(PERIOD_START, end) == 365


def test_period_must_end_after_it_starts():
    with pytest.raises(ValidationError):
        proration.days_in_period(PERIOD_END, PERIOD_START)


@pytest.mark.parametrize(
    "now, expected",
    [
        (datetime(2026, 1, 5, 9, 0, tzinfo=UTC), 31),    # first day: the whole period
        (datetime(2026, 1, 20, 23, 59, tzinfo=UTC), 16),  # time of day does not matter
        (datetime(2026, 2, 4, 0, 0, tzinfo=UTC), 1),     # last day
        (datetime(2026, 2, 5, 9, 0, tzinfo=UTC), 0),     # period end
        (datetime(2026, 3, 1, 0, 0, tzinfo=UTC), 0),     # never negative
    ],
)
def test_days_remaining_counts_whole_calendar_days(now, expected):
    assert proration.days_remaining(now, PERIOD_END) == expected


@pytest.mark.parametrize(
    "cents, remaining, period, expected",
    [
        (100, 1, 8, 13),      # 12.5 cents rounds half up to 13
        (100, 1, 3, 33),      # 33.33 rounds down
        (100, 2, 3, 67),      # 66.67 rounds up
        (2000, 31, 31, 2000),  # whole period: full price
        (2000, 0, 31, 0),     # nothing left: nothing charged
    ],
)
def test_prorate_rounds_to_the_nearest_cent_half_up(cents, remaining, period, expected):
    assert proration.prorate(Money(cents), remaining, period) == Money(expected)


def test_prorate_rejects_more_days_remaining_than_the_period_has():
    with pytest.raises(ValidationError):
        proration.prorate(Money(2000), 32, 31)


def test_upgrade_charges_the_prorated_price_difference_for_all_seats():
    """Starter $8 to Pro $20, 4 seats, 16 of 31 days left: $48 x 16/31 = $24.77."""
    charge = proration.upgrade_charge(Money(800), Money(2000), 4, 16, 31)
    assert charge == Money(2477)
    assert str(charge) == "$24.77"


def test_upgrade_on_the_first_day_charges_the_full_difference():
    assert proration.upgrade_charge(Money(800), Money(2000), 4, 31, 31) == Money(4800)


def test_upgrade_charge_rejects_a_lower_price():
    with pytest.raises(ValidationError):
        proration.upgrade_charge(Money(2000), Money(800), 4, 16, 31)


def test_added_seats_are_charged_prorated_by_day():
    """3 Pro seats ($20) with 10 of 30 days left: $60 x 10/30 = $20.00."""
    assert proration.seat_add_charge(Money(2000), 3, 10, 30) == Money(2000)


def test_removed_seats_give_a_prorated_credit():
    """2 Business seats ($45) with 15 of 30 days left: $90 x 15/30 = $45.00."""
    assert proration.seat_removal_credit(Money(4500), 2, 15, 30) == Money(4500)


def test_proration_keeps_the_currency():
    assert proration.seat_add_charge(Money(2000, "EUR"), 1, 16, 31) == Money(1032, "EUR")


@pytest.mark.parametrize("func", [proration.seat_add_charge, proration.seat_removal_credit])
def test_seat_changes_need_at_least_one_seat(func):
    with pytest.raises(ValidationError):
        func(Money(2000), 0, 10, 30)

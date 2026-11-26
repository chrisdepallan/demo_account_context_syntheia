"""Money is stored as whole cents; proration rounds half up to the cent."""

from __future__ import annotations

from decimal import Decimal

import pytest

from acme_cloud.common.money import SUPPORTED_CURRENCIES, Money


def test_only_usd_and_eur_are_supported():
    assert SUPPORTED_CURRENCIES == ("USD", "EUR")
    assert Money(100).currency == "USD"
    with pytest.raises(ValueError):
        Money(100, "GBP")


def test_cents_must_be_an_integer():
    """Floats never reach an invoice: fractions go through ``from_major``."""
    with pytest.raises(TypeError):
        Money(19.99)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("amount", "cents"),
    [("19.99", 1999), (20, 2000), (0.1, 10), (Decimal("45.00"), 4500),
     ("0.005", 1),    # half a cent rounds up
     ("0.004", 0)],
)
def test_from_major_converts_to_cents_rounding_half_up(amount, cents):
    assert Money.from_major(amount).cents == cents


def test_add_and_subtract_keep_the_currency():
    assert Money(2000) + Money(800) == Money(2800)
    assert Money(2000) - Money(4500) == Money(-2500)
    assert Money(500, "EUR") + Money(300, "EUR") == Money(800, "EUR")


def test_mixing_currencies_is_an_error():
    with pytest.raises(ValueError):
        Money(100, "USD") + Money(100, "EUR")
    with pytest.raises(ValueError):
        Money(100, "USD") - Money(100, "EUR")


def test_multiply_by_a_whole_number_of_seats():
    assert Money(2000) * 7 == Money(14000)
    with pytest.raises(TypeError):
        Money(2000) * 1.5  # type: ignore[operator]


def test_negate_and_sign_helpers():
    assert -Money(250) == Money(-250)
    assert Money(-1).is_negative
    assert not Money(0).is_negative
    assert Money.zero("EUR") == Money(0, "EUR")
    assert Money.zero().is_zero


@pytest.mark.parametrize(
    ("cents", "numerator", "denominator", "expected"),
    [(2000, 15, 30, 1000),   # half of a Pro seat
     (2000, 16, 31, 1032),   # 1032.26 rounds down
     (2000, 15, 31, 968),    # 967.74 rounds up
     (1000, 1, 3, 333),      # 333.33 rounds down
     (5, 1, 2, 3),           # 2.5 cents rounds half up
     (4500, 0, 30, 0),       # no days left
     (4500, 30, 30, 4500)],  # the whole period
)
def test_prorate_rounds_half_up_to_the_cent(cents, numerator, denominator, expected):
    """Proration is whole days remaining divided by days in the period."""
    assert Money(cents).prorate(numerator, denominator) == Money(expected)


def test_prorate_needs_a_positive_denominator():
    with pytest.raises(ValueError):
        Money(2000).prorate(1, 0)


@pytest.mark.parametrize(
    ("money", "text"),
    [(Money(2000), "$20.00"), (Money(123450), "$1,234.50"), (Money(5), "$0.05"),
     (Money(-5, "EUR"), "-€0.05"), (Money(800, "EUR"), "€8.00")],
)
def test_str_shows_symbol_thousands_and_two_decimals(money, text):
    assert str(money) == text


def test_money_is_ordered_and_hashable():
    assert Money(800) < Money(2000) < Money(4500)
    assert len({Money(800), Money(800), Money(2000)}) == 2

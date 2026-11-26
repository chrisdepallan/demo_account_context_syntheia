"""Payment methods: allowed types by plan, country, interval and amount; token storage."""

from __future__ import annotations

from dataclasses import fields

import pytest

from acme_cloud.billing.models import (
    BillingInterval,
    PaymentMethod,
    PaymentMethodType as T,
    ProcessorUnavailableError,
)
from acme_cloud.billing.payment_methods import (
    CARD_BRANDS,
    add_payment_method,
    allowed_method_types,
    require_method_allowed,
)
from acme_cloud.billing.service import FakePaymentProcessor
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PaymentFailedError, ValidationError
from acme_cloud.common.ids import is_valid_id
from acme_cloud.common.money import Money

MONTHLY, ANNUAL = BillingInterval.MONTHLY, BillingInterval.ANNUAL


@pytest.mark.parametrize(
    "plan, country, interval, amount, expected",
    [
        (Plan.FREE, "US", MONTHLY, Money(0), ()),                        # no method needed
        (Plan.STARTER, "US", MONTHLY, Money(4000), (T.CARD, T.PAYPAL)),
        (Plan.PRO, "DE", MONTHLY, Money(10_000, "EUR"), (T.CARD, T.PAYPAL)),
        (Plan.BUSINESS, "US", MONTHLY, Money(45_000), (T.CARD, T.PAYPAL)),
        (Plan.PRO, "IN", MONTHLY, Money(10_000), (T.CARD, T.UPI)),       # India: UPI, no PayPal
        (Plan.PRO, "US", ANNUAL, Money(200_000), (T.CARD, T.PAYPAL, T.ACH)),
        (Plan.PRO, "DE", ANNUAL, Money(200_000, "EUR"), (T.CARD, T.PAYPAL, T.SEPA)),
        (Plan.ENTERPRISE, "US", ANNUAL, Money(1_200_000), (T.CARD, T.ACH, T.INVOICE)),
    ],
)
def test_allowed_method_types(plan, country, interval, amount, expected):
    assert allowed_method_types(plan, country, interval, amount) == expected


@pytest.mark.parametrize("plan", [Plan.STARTER, Plan.PRO, Plan.BUSINESS, Plan.ENTERPRISE])
def test_cards_are_allowed_on_all_paid_plans(plan):
    assert T.CARD in allowed_method_types(plan, "US", MONTHLY, Money(5000))


def test_paypal_is_not_offered_on_enterprise_or_in_india():
    assert T.PAYPAL not in allowed_method_types(Plan.ENTERPRISE, "US", ANNUAL, Money(5_000_000))
    assert T.PAYPAL not in allowed_method_types(Plan.BUSINESS, "in", MONTHLY, Money(45_000))


@pytest.mark.parametrize(
    "interval, cents, allowed",
    [
        (ANNUAL, 100_000, False),   # exactly $1,000.00 is not "over $1,000"
        (ANNUAL, 100_001, True),    # $1,000.01
        (MONTHLY, 500_000, False),  # monthly plans never qualify
    ],
)
def test_bank_transfer_needs_an_annual_plan_over_1000(interval, cents, allowed):
    assert (T.ACH in allowed_method_types(Plan.BUSINESS, "US", interval, Money(cents))) is allowed
    eur = allowed_method_types(Plan.BUSINESS, "FR", interval, Money(cents, "EUR"))
    assert (T.SEPA in eur) is allowed


def test_invoice_net_30_is_enterprise_only():
    with pytest.raises(ValidationError) as error:
        require_method_allowed(T.INVOICE, Plan.BUSINESS, "US", ANNUAL, Money(900_000))
    assert error.value.code == "ERR_VALIDATION"
    require_method_allowed(T.INVOICE, Plan.ENTERPRISE, "US", ANNUAL, Money(900_000))


def _add(processor, ids, clock, method_type=T.CARD, brand="visa", plan=Plan.PRO, country="US"):
    return add_payment_method(processor, ids, clock, "acc_7F3K9Q2M", method_type, plan,
                              country, MONTHLY, Money(10_000), brand)


@pytest.mark.parametrize("brand", ["Visa", "mastercard", "AMEX", " discover "])
def test_accepted_card_brands(ids, clock, brand):
    method = _add(FakePaymentProcessor(), ids, clock, brand=brand)
    assert method.brand in CARD_BRANDS


@pytest.mark.parametrize("brand", ["diners", "", None])
def test_other_card_brands_are_rejected(ids, clock, brand):
    with pytest.raises(ValidationError):
        _add(FakePaymentProcessor(), ids, clock, brand=brand)


def test_new_method_is_checked_with_a_zero_dollar_authorization(ids, clock):
    processor = FakePaymentProcessor()
    method = _add(processor, ids, clock)
    assert processor.calls == [("authorize", method.token, Money(0))]


def test_method_is_stored_as_an_opaque_token_with_type_and_brand_only(ids, clock):
    method = _add(FakePaymentProcessor(), ids, clock)
    assert is_valid_id(method.token, "pm")
    assert (method.type, method.brand, method.added_at) == (T.CARD, "visa", clock.now())
    assert {f.name for f in fields(PaymentMethod)} == {
        "token", "account_id", "type", "brand", "added_at"}


def test_non_card_methods_have_no_brand(ids, clock):
    assert _add(FakePaymentProcessor(), ids, clock, T.PAYPAL, brand=None).brand is None
    assert _add(FakePaymentProcessor(), ids, clock, T.UPI, brand=None, country="IN").brand is None


def test_declined_authorization_raises_payment_failed(ids, clock):
    processor = FakePaymentProcessor()
    processor.decline()
    with pytest.raises(PaymentFailedError) as error:
        _add(processor, ids, clock)
    assert (error.value.code, error.value.http_status) == ("ERR_PAYMENT_FAILED", 402)


def test_processor_outage_is_reported_as_unavailable_not_as_a_decline(ids, clock):
    processor = FakePaymentProcessor()
    processor.go_down()
    with pytest.raises(ProcessorUnavailableError):
        _add(processor, ids, clock)

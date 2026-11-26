"""Refund policy: eligibility, paid-amount limit, approval tiers, goodwill, ticket number."""

from __future__ import annotations

import pytest

from acme_cloud.billing.invoices import InvoiceBook
from acme_cloud.billing.models import (
    BillingDetails, BillingInterval, ChargeOutcome, InvoiceLine, RefundStatus,
)
from acme_cloud.billing.refunds import (
    REFUND_TIMELINE_BUSINESS_DAYS,
    ApproverRole,
    RefundKind,
    can_approve,
    extract_ticket_id,
    goodwill_allowed,
    request_refund,
    required_approver,
    settle_refund,
)
from acme_cloud.common.errors import ConflictError, PermissionDeniedError, ValidationError
from acme_cloud.common.ids import is_valid_id
from acme_cloud.common.money import Money

AGENT, LEAD, MANAGER = (
    ApproverRole.SUPPORT_AGENT, ApproverRole.TEAM_LEAD, ApproverRole.BILLING_MANAGER)
REASON = "Customer cancelled, see SUP-58213"


@pytest.fixture
def book(clock, ids):
    return InvoiceBook(clock, ids)


def paid_invoice(book, cents=40_000, interval=BillingInterval.ANNUAL):
    invoice = book.create("acc_7F3K9Q2M", [InvoiceLine("plan", 1, Money(cents))],
                          BillingDetails(), interval)
    return book.mark_paid(invoice.id)


def ask(invoice, clock, ids, cents, kind=RefundKind.CANCELLATION, approver=MANAGER,
        reason=REASON, last_goodwill_at=None):
    return request_refund(invoice, Money(cents), kind, reason, approver, clock.now(), ids,
                          last_goodwill_at)


@pytest.mark.parametrize(
    "cents, role",
    [
        (1, AGENT),
        (50_000, AGENT),       # $500.00: any support agent
        (50_001, LEAD),        # $500.01: support team lead
        (500_000, LEAD),       # $5,000.00: still team lead
        (500_001, MANAGER),    # over $5,000: billing manager
    ],
)
def test_approval_tier_by_amount(cents, role):
    assert required_approver(Money(cents)) is role
    assert can_approve(role, Money(cents))
    assert can_approve(MANAGER, Money(cents))  # a higher role can always approve


def test_goodwill_needs_a_team_lead_at_any_amount():
    assert required_approver(Money(500), RefundKind.GOODWILL) is LEAD
    assert not can_approve(AGENT, Money(500), RefundKind.GOODWILL)
    assert required_approver(Money(600_000), RefundKind.GOODWILL) is MANAGER


def test_agent_cannot_approve_500_01(book, clock, ids):
    invoice = paid_invoice(book, 100_000)
    with pytest.raises(PermissionDeniedError) as error:
        ask(invoice, clock, ids, 50_001, approver=AGENT)
    assert error.value.details["required"] == "team_lead"
    assert ask(invoice, clock, ids, 50_000, approver=AGENT).approved_by_role == "support_agent"


@pytest.mark.parametrize("days, eligible", [(0, True), (30, True), (31, False)])
def test_annual_plan_is_refunded_in_full_within_30_days(book, clock, ids, days, eligible):
    invoice = paid_invoice(book)
    clock.advance(days=days)
    if eligible:
        refund = ask(invoice, clock, ids, 40_000)
        assert refund.amount == invoice.paid_amount and refund.status is RefundStatus.PENDING
    else:
        with pytest.raises(ValidationError):
            ask(invoice, clock, ids, 40_000)


def test_monthly_plans_get_no_refund_for_unused_time(book, clock, ids):
    invoice = paid_invoice(book, interval=BillingInterval.MONTHLY)
    with pytest.raises(ValidationError):
        ask(invoice, clock, ids, 1000)


@pytest.mark.parametrize("kind", [RefundKind.DUPLICATE_CHARGE, RefundKind.BILLING_ERROR])
def test_duplicate_charges_and_billing_errors_are_always_refunded(book, clock, ids, kind):
    invoice = paid_invoice(book, interval=BillingInterval.MONTHLY)
    clock.advance(days=200)
    assert ask(invoice, clock, ids, 40_000, kind).amount == Money(40_000)


def test_refund_cannot_exceed_paid_amount_minus_earlier_refunds(book, clock, ids):
    invoice = paid_invoice(book, 10_000)
    ask(invoice, clock, ids, 6000)
    with pytest.raises(ValidationError):
        ask(invoice, clock, ids, 4001)
    ask(invoice, clock, ids, 4000)
    assert invoice.refundable_amount.is_zero
    with pytest.raises(ValidationError):
        ask(invoice, clock, ids, 1)


def test_only_a_paid_invoice_can_be_refunded(book, clock, ids):
    invoice = book.create("acc_7F3K9Q2M", [InvoiceLine("plan", 1, Money(5000))], BillingDetails())
    with pytest.raises(ConflictError):
        ask(invoice, clock, ids, 5000, RefundKind.BILLING_ERROR)


@pytest.mark.parametrize("reason", ["", "customer asked", "ticket SUP-123", "see sup-58213"])
def test_reason_must_include_the_ticket_number(book, clock, ids, reason):
    with pytest.raises(ValidationError):
        ask(paid_invoice(book), clock, ids, 1000, reason=reason)


def test_refund_records_ticket_and_has_an_rf_id(book, clock, ids):
    refund = ask(paid_invoice(book), clock, ids, 1000)
    assert refund.ticket_id == extract_ticket_id(REASON) == "SUP-58213"
    assert is_valid_id(refund.id, "rf")


def test_one_goodwill_refund_per_account_per_12_months(book, clock, ids):
    invoice = paid_invoice(book, interval=BillingInterval.MONTHLY)
    first = ask(invoice, clock, ids, 1000, RefundKind.GOODWILL, LEAD)
    clock.advance(days=364)
    assert not goodwill_allowed(first.created_at, clock.now())
    with pytest.raises(ConflictError):
        ask(invoice, clock, ids, 1000, RefundKind.GOODWILL, LEAD, last_goodwill_at=first.created_at)
    clock.advance(days=1)  # exactly 12 months later
    assert goodwill_allowed(first.created_at, clock.now())
    ask(invoice, clock, ids, 1000, RefundKind.GOODWILL, LEAD, last_goodwill_at=first.created_at)


def test_refund_is_pending_then_succeeded_or_failed(book, clock, ids):
    invoice = paid_invoice(book, 10_000)
    ok = settle_refund(ask(invoice, clock, ids, 3000), invoice, ChargeOutcome.SUCCEEDED)
    assert ok.status is RefundStatus.SUCCEEDED and invoice.refunded_amount == Money(3000)
    failed = settle_refund(ask(invoice, clock, ids, 2000), invoice, ChargeOutcome.DECLINED)
    assert failed.status is RefundStatus.FAILED
    assert invoice.refunded_amount == Money(3000)  # a failed refund releases its amount
    waiting = settle_refund(ask(invoice, clock, ids, 1000), invoice, ChargeOutcome.UNAVAILABLE)
    assert waiting.status is RefundStatus.PENDING  # outage: sent again later
    with pytest.raises(ConflictError):
        settle_refund(ok, invoice, ChargeOutcome.SUCCEEDED)


def test_customer_is_told_5_to_10_business_days():
    assert REFUND_TIMELINE_BUSINESS_DAYS == (5, 10)
    assert [s.value for s in RefundStatus] == ["pending", "succeeded", "failed"]

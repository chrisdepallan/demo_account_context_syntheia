"""BillingService end to end, with a fake processor, the outbox and the audit log."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.audit import AuditLog
from acme_cloud.billing import (
    ApproverRole, BillingInterval, BillingService, ChargeOutcome, FakePaymentProcessor,
    InvoiceStatus, PaymentMethodType, ProcessorUnavailableError, RefundKind, RefundStatus,
)
from acme_cloud.common.enums import AccountState, Plan
from acme_cloud.common.errors import (
    ConflictError, LimitExceededError, PaymentFailedError, PermissionDeniedError, ValidationError,
)
from acme_cloud.common.money import Money
from acme_cloud.notifications import Outbox

ACCOUNT, OWNER = "acc_7F3K9Q2M", "usr_2B6N8R4V"
OWNER_EMAIL, BILLING_ADMIN, CONTACT = (
    "owner@example.com", "billing.admin@example.com", "finance@example.com")
MONTHLY, ANNUAL, CARD = BillingInterval.MONTHLY, BillingInterval.ANNUAL, PaymentMethodType.CARD


@pytest.fixture
def svc(clock, ids):
    service = BillingService(clock, ids, FakePaymentProcessor(), Outbox(clock), AuditLog(clock, ids))
    service.open_account(ACCOUNT, [OWNER_EMAIL, BILLING_ADMIN])
    service.profile(ACCOUNT).add_contact(CONTACT)
    return service


def subscribe(svc, plan=Plan.PRO, interval=MONTHLY, seats=5):
    return svc.subscribe(ACCOUNT, OWNER, plan, interval, seats, CARD, "visa")


def fail_renewal(svc, clock):
    """Subscribe, then let the first renewal be declined (dunning day 0)."""
    subscribe(svc)
    clock.advance(days=31)
    svc.processor.decline()
    return svc.renew(ACCOUNT)


def test_subscribe_checks_the_card_charges_the_period_and_issues_an_invoice(svc):
    result = subscribe(svc)
    assert result.outcome is ChargeOutcome.SUCCEEDED and result.amount == Money(10_000)
    assert result.invoice.status is InvoiceStatus.PAID
    assert svc.subscription(ACCOUNT).plan is Plan.PRO
    token = svc.payment_method(ACCOUNT).token
    assert svc.processor.calls == [("authorize", token, Money(0)), ("charge", token, Money(10_000))]
    assert {m.to for m in svc.notifier.by_template("invoice_ready")} == {
        OWNER_EMAIL, BILLING_ADMIN, CONTACT}
    assert svc.notifier.last().subject == f"Invoice {result.invoice.id} is ready"
    events = [e.event_type for e in svc.audit.query(ACCOUNT)]
    assert events == ["payment_method.updated", "plan.changed"]


def test_annual_subscription_costs_ten_times_monthly(svc):
    assert subscribe(svc, interval=ANNUAL).amount == Money(100_000)


def test_declined_first_charge_changes_nothing(svc):
    svc.processor.decline()
    with pytest.raises(PaymentFailedError):
        subscribe(svc)
    assert svc.subscription(ACCOUNT).plan is Plan.FREE
    assert svc.payment_method(ACCOUNT) is None and svc.invoices.for_account(ACCOUNT) == []


def test_upgrade_is_immediate_and_charged_prorated(svc, clock):
    subscribe(svc)
    clock.advance(days=15)  # 16 of 31 days left
    change = svc.change_plan(ACCOUNT, OWNER, Plan.BUSINESS)
    assert change.charge == Money(6452)  # (45 - 20) x 5 x 16/31 = $64.516
    assert svc.subscription(ACCOUNT).plan is Plan.BUSINESS
    assert svc.invoices.for_account(ACCOUNT)[-1].total == Money(6452)


def test_upgrade_does_not_apply_when_the_charge_fails(svc):
    subscribe(svc)
    svc.processor.decline()
    with pytest.raises(PaymentFailedError):
        svc.change_plan(ACCOUNT, OWNER, Plan.BUSINESS)
    svc.processor.go_down()
    with pytest.raises(ProcessorUnavailableError):
        svc.change_plan(ACCOUNT, OWNER, Plan.BUSINESS)
    assert svc.subscription(ACCOUNT).plan is Plan.PRO
    assert svc.billing_state(ACCOUNT) is AccountState.ACTIVE


def test_downgrade_waits_for_the_period_end_and_is_blocked_over_the_limits(svc, clock):
    subscribe(svc)
    with pytest.raises(LimitExceededError):
        svc.change_plan(ACCOUNT, OWNER, Plan.STARTER, members=11, workspaces=1)
    change = svc.change_plan(ACCOUNT, OWNER, Plan.STARTER, members=5, workspaces=1)
    assert not change.immediate and svc.subscription(ACCOUNT).plan is Plan.PRO
    clock.advance(days=31)
    assert svc.renew(ACCOUNT).amount == Money(4000)  # 5 Starter seats at $8
    assert svc.subscription(ACCOUNT).plan is Plan.STARTER


def test_added_seats_are_charged_now_and_removed_seats_credit_the_next_invoice(svc, clock):
    subscribe(svc)
    clock.advance(days=15)
    assert svc.change_seats(ACCOUNT, OWNER, 7).amount == Money(2065)
    credit = svc.change_seats(ACCOUNT, OWNER, 6, members_in_use=5)
    assert credit.outcome is None and credit.amount == Money(-1032)
    clock.advance(days=16)
    renewal = svc.renew(ACCOUNT)
    assert renewal.invoice.total == Money(6 * 2000 - 1032)
    assert [e.metadata["new"] for e in svc.audit.query(ACCOUNT, event_type="seats.changed")] == [7, 6]


def test_cancel_keeps_the_plan_until_the_period_ends_then_free(svc, clock):
    subscribe(svc)
    ends = svc.cancel(ACCOUNT, OWNER)
    assert ends - clock.now() == timedelta(days=31)
    assert svc.renew(ACCOUNT) is None and svc.subscription(ACCOUNT).plan is Plan.PRO
    clock.advance(days=31)
    assert svc.renew(ACCOUNT) is None  # nothing is charged on Free
    assert svc.subscription(ACCOUNT).plan is Plan.FREE


def test_failed_renewal_starts_dunning_and_emails_billing_people(svc, clock):
    result = fail_renewal(svc, clock)
    assert result.outcome is ChargeOutcome.DECLINED
    assert result.account_state is AccountState.PAST_DUE
    assert result.invoice.status is InvoiceStatus.PAYMENT_FAILED
    assert {m.to for m in svc.notifier.by_template("payment_failed")} == {
        OWNER_EMAIL, BILLING_ADMIN, CONTACT}


def test_dunning_timeline_read_only_on_day_14_and_free_on_day_44(svc, clock):
    fail_renewal(svc, clock)
    states = {}
    for day in range(1, 45):
        clock.advance(days=1)
        action = svc.run_dunning(ACCOUNT)
        states[day] = svc.billing_state(ACCOUNT)
        assert action.retry is False and action.counted_as_failure is (day in (1, 3, 7, 14))
    assert states[13] is AccountState.PAST_DUE
    assert states[14] is states[43] is AccountState.READ_ONLY
    assert states[44] is AccountState.ACTIVE and svc.subscription(ACCOUNT).plan is Plan.FREE
    assert svc.notifier.count("payment_failed", OWNER_EMAIL) == 5  # day 0 and four retries
    assert svc.notifier.count("account_read_only", CONTACT) == 0   # contacts: invoices, alerts
    assert svc.notifier.count("account_read_only", BILLING_ADMIN) == 1
    assert svc.notifier.count("account_downgraded", OWNER_EMAIL) == 1
    assert svc.run_dunning(ACCOUNT) is None


def test_processor_outage_at_renewal_is_not_a_failed_payment(svc, clock):
    """INC-2026-002: no past_due, no payment_failed email; charged when the processor is back."""
    subscribe(svc)
    clock.advance(days=31)
    svc.processor.go_down()
    result = svc.renew(ACCOUNT)
    assert result.outcome is ChargeOutcome.UNAVAILABLE and result.account_state is None
    assert svc.billing_state(ACCOUNT) is AccountState.ACTIVE
    assert svc.notifier.count("payment_failed") == 0
    svc.processor.succeed()
    assert svc.run_dunning(ACCOUNT) is None
    assert result.invoice.status is InvoiceStatus.PAID


def test_outage_during_a_dunning_retry_is_not_counted(svc, clock):
    fail_renewal(svc, clock)
    emails_before = svc.notifier.count("payment_failed")
    svc.processor.go_down()
    clock.advance(days=14)
    action = svc.run_dunning(ACCOUNT)
    assert action.retry and not action.counted_as_failure
    assert svc.billing_state(ACCOUNT) is AccountState.PAST_DUE  # not read_only
    assert svc.notifier.count("payment_failed") == emails_before


def test_updating_the_payment_method_retries_at_once_and_restores_active(svc, clock):
    invoice = fail_renewal(svc, clock).invoice
    clock.advance(days=20)
    svc.processor.succeed()
    method, action = svc.update_payment_method(ACCOUNT, OWNER, CARD, "amex")
    assert method.brand == "amex" and action.new_state is AccountState.ACTIVE
    assert svc.billing_state(ACCOUNT) is AccountState.ACTIVE
    assert invoice.status is InvoiceStatus.PAID


def test_no_new_charges_while_a_balance_is_unpaid(svc, clock):
    fail_renewal(svc, clock)
    with pytest.raises(ConflictError):
        svc.change_seats(ACCOUNT, OWNER, 8)


def test_refund_follows_policy_and_is_audited(svc):
    invoice = subscribe(svc, interval=ANNUAL).invoice  # $1,000.00
    args = (ACCOUNT, OWNER, invoice.id, Money(100_000), RefundKind.CANCELLATION, "SUP-58213")
    with pytest.raises(PermissionDeniedError):
        svc.refund(*args, ApproverRole.SUPPORT_AGENT)
    refund = svc.refund(*args, ApproverRole.TEAM_LEAD)
    assert refund.status is RefundStatus.SUCCEEDED
    with pytest.raises(ValidationError):
        svc.refund(ACCOUNT, OWNER, invoice.id, Money(1), RefundKind.BILLING_ERROR, "SUP-58213",
                   ApproverRole.TEAM_LEAD)
    event = svc.audit.query(ACCOUNT, event_type="refund.issued")[0]
    assert event.metadata["refund_id"] == refund.id and event.metadata["ticket"] == "SUP-58213"


def test_enterprise_can_pay_by_invoice_with_net_30_terms(svc):
    result = svc.subscribe(ACCOUNT, OWNER, Plan.ENTERPRISE, ANNUAL, 20,
                           PaymentMethodType.INVOICE, custom_seat_price=Money(60_000))
    assert result.outcome is None and result.invoice.status is InvoiceStatus.OPEN
    assert result.invoice.due_at - result.invoice.issued_at == timedelta(days=30)
    assert svc.processor.calls == []  # nothing to authorize or charge

"""BillingService: an in-memory facade over subscriptions, invoices, dunning and refunds.

What the service does, in business terms:

- ``subscribe``: checks the payment method ($0 authorization), charges the
  first period and issues the invoice. Annual costs 10 times monthly.
- ``change_plan``: an upgrade is charged at once (prorated difference) and
  applies only if the charge succeeds; a downgrade is booked for the period
  end and blocked while usage exceeds the lower plan's limits.
- ``change_seats``: added seats are charged at once, prorated by day; removed
  seats become a credit line on the next invoice.
- ``renew``: issues and charges the next period's invoice. A declined renewal
  or seat charge starts dunning: day 0 ``past_due``, retries on days 1, 3, 7
  and 14, ``read_only`` on day 14, downgrade to Free on day 44.
- ``run_dunning``: the daily job. A processor outage is never counted as a
  failed payment (INC-2026-002).
- ``update_payment_method``: a new method is checked with a $0 authorization
  and, if the account is in dunning, the charge is retried immediately.
- ``refund``: applies the refund policy and approval tiers.

The service does not own accounts. Account state changes are returned as
decisions (``ChargeResult.account_state``, ``DunningAction.new_state``) for
the accounts module to apply. Emails and audit events go to the optional
``notifier`` and ``audit`` collaborators.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from acme_cloud.billing import subscriptions as subs
from acme_cloud.billing.dunning import EMAIL_PAYMENT_FAILED, DunningAction, DunningProcess
from acme_cloud.billing.invoices import BillingProfile, InvoiceBook
from acme_cloud.billing.models import (
    BillingInterval, ChargeOutcome, Invoice, InvoiceLine, InvoiceStatus, PaymentMethod,
    PaymentMethodType, ProcessorUnavailableError, Refund, RefundStatus, Subscription,
)
from acme_cloud.billing.payment_methods import INVOICE_NET_TERMS_DAYS, add_payment_method
from acme_cloud.billing.refunds import ApproverRole, RefundKind, request_refund, settle_refund
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import AccountState, Plan
from acme_cloud.common.errors import ConflictError, NotFoundError, PaymentFailedError, ValidationError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.common.money import Money

#: Actor recorded in the audit log for automatic actions (renewal, dunning).
SYSTEM_ACTOR = "system"


class FakePaymentProcessor:
    """Stand-in for the payment processor. Tell it to succeed, decline or be down."""

    def __init__(self) -> None:
        self.outcome = ChargeOutcome.SUCCEEDED
        self.calls: list[tuple[str, str, Money]] = []   # (operation, token or reference, amount)

    def succeed(self) -> None:
        self.outcome = ChargeOutcome.SUCCEEDED

    def decline(self) -> None:
        self.outcome = ChargeOutcome.DECLINED

    def go_down(self) -> None:
        """Simulate a processor outage: every call answers ``unavailable``."""
        self.outcome = ChargeOutcome.UNAVAILABLE

    def authorize(self, token: str, amount: Money) -> ChargeOutcome:
        return self._call("authorize", token, amount)

    def charge(self, token: str, amount: Money) -> ChargeOutcome:
        return self._call("charge", token, amount)

    def refund(self, reference: str, amount: Money) -> ChargeOutcome:
        return self._call("refund", reference, amount)

    def _call(self, operation: str, reference: str, amount: Money) -> ChargeOutcome:
        self.calls.append((operation, reference, amount))
        return self.outcome


@dataclass
class ChargeResult:
    """Outcome of an attempt to collect money."""

    outcome: ChargeOutcome | None        # None: nothing charged now (credit, or net-30 invoice)
    invoice: Invoice | None
    amount: Money
    account_state: AccountState | None = None   # state decision; None = no change


@dataclass
class _BillingAccount:
    account_id: str
    billing_emails: list[str]            # Owner and Billing admins
    country: str
    subscription: Subscription
    profile: BillingProfile
    payment_method: PaymentMethod | None = None
    dunning: DunningProcess | None = None
    unpaid_invoice_id: str | None = None
    last_goodwill_at: datetime | None = None
    refunds: list[Refund] = field(default_factory=list)


class BillingService:
    """Billing for all accounts, kept in memory."""

    def __init__(self, clock: Clock, ids: IdGenerator, processor: Any = None,
                 notifier: Any = None, audit: Any = None) -> None:
        self.clock, self.ids = clock, ids
        self.processor = processor or FakePaymentProcessor()
        self.notifier, self.audit = notifier, audit
        self.invoices = InvoiceBook(clock, ids)
        self._accounts: dict[str, _BillingAccount] = {}

    # -- accounts -----------------------------------------------------------
    def open_account(self, account_id: str, billing_emails: list[str], country: str = "US",
                     currency: str = "USD") -> Subscription:
        """Register an account for billing on the Free plan."""
        if account_id in self._accounts:
            raise ConflictError("billing is already set up for this account")
        sub = subs.new_subscription(self.ids, account_id, Plan.FREE, BillingInterval.MONTHLY,
                                    1, self.clock.now(), currency)
        self._accounts[account_id] = _BillingAccount(
            account_id, list(billing_emails), country, sub, BillingProfile(account_id))
        return sub

    def _account(self, account_id: str) -> _BillingAccount:
        if account_id not in self._accounts:
            raise NotFoundError(f"no billing record for account {account_id}")
        return self._accounts[account_id]

    def subscription(self, account_id: str) -> Subscription:
        return self._account(account_id).subscription

    def profile(self, account_id: str) -> BillingProfile:
        return self._account(account_id).profile

    def payment_method(self, account_id: str) -> PaymentMethod | None:
        return self._account(account_id).payment_method

    def billing_state(self, account_id: str) -> AccountState:
        """``past_due`` or ``read_only`` while in dunning, else ``active``."""
        dunning = self._account(account_id).dunning
        return dunning.state if dunning else AccountState.ACTIVE

    # -- plan, seats, payment method ------------------------------------------
    def subscribe(self, account_id: str, actor_id: str, plan: Plan, interval: BillingInterval,
                  seats: int, method_type: PaymentMethodType, brand: str | None = None,
                  custom_seat_price: Money | None = None) -> ChargeResult:
        """Move a Free account to a paid plan and charge the first period."""
        acct = self._account(account_id)
        if acct.subscription.plan.is_paid:
            raise ConflictError("the account already has a paid plan; use change_plan")
        sub = subs.new_subscription(self.ids, account_id, plan, interval, seats, self.clock.now(),
                                    acct.subscription.currency, custom_seat_price)
        total = subs.period_total(sub)
        method = add_payment_method(self.processor, self.ids, self.clock, account_id,
                                    method_type, plan, acct.country, interval, total, brand)
        line = InvoiceLine(f"{plan.value} plan, {interval.value}", seats, subs.seat_price_for(sub))
        old_plan, old_method = acct.subscription.plan, acct.payment_method
        acct.payment_method = method
        try:
            result = self._collect(acct, [line], interval, must_succeed=True)
        except Exception:
            acct.payment_method = old_method   # nothing changes when the charge fails
            raise
        acct.subscription = sub
        self._audit("payment_method.updated", actor_id, account_id, type=method.type.value)
        self._audit("plan.changed", actor_id, account_id, old=old_plan.value, new=plan.value)
        return result

    def update_payment_method(self, account_id: str, actor_id: str, method_type: PaymentMethodType,
                              brand: str | None = None) -> tuple[PaymentMethod, DunningAction | None]:
        """Replace the payment method; in dunning this retries the charge at once."""
        acct, sub = self._account(account_id), self._account(account_id).subscription
        acct.payment_method = add_payment_method(
            self.processor, self.ids, self.clock, account_id, method_type, sub.plan,
            acct.country, sub.interval, subs.period_total(sub), brand)
        self._audit("payment_method.updated", actor_id, account_id, type=method_type.value)
        action = self._retry(acct) if acct.dunning else None
        return acct.payment_method, action

    def change_plan(self, account_id: str, actor_id: str, new_plan: Plan, members: int = 0,
                    workspaces: int = 0, storage_used_mb: int = 0) -> subs.PlanChange:
        """Upgrade now (charged at once) or book a downgrade for the period end."""
        acct = self._account(account_id)
        if not acct.subscription.plan.is_paid:
            raise ConflictError("the account is on Free; use subscribe")
        if new_plan.rank > acct.subscription.plan.rank:
            candidate = replace(acct.subscription)
            change = subs.upgrade(candidate, new_plan, self.clock.now())
            line = InvoiceLine(f"Upgrade to {new_plan.value}, prorated", 1, change.charge)
            self._collect(acct, [line], None, must_succeed=True)
            acct.subscription = candidate
        else:
            change = subs.schedule_downgrade(acct.subscription, new_plan, members, workspaces,
                                             storage_used_mb)
        self._audit("plan.changed", actor_id, account_id, old=change.old_plan.value,
                    new=new_plan.value, immediate=change.immediate)
        return change

    def change_seats(self, account_id: str, actor_id: str, seats: int,
                     members_in_use: int = 0) -> ChargeResult:
        """Set the seat count: more seats are charged now, fewer become a credit."""
        acct, now = self._account(account_id), self.clock.now()
        sub, old = acct.subscription, acct.subscription.seats
        if seats == old:
            raise ValidationError("the seat count is unchanged")
        if seats > old:
            charge = subs.add_seats(sub, seats - old, now)
            line = InvoiceLine(f"{seats - old} added seats, prorated", 1, charge)
            result = self._collect(acct, [line], None, must_succeed=False)
        else:
            credit = subs.remove_seats(sub, old - seats, now, members_in_use)
            result = ChargeResult(None, None, -credit)
        self._audit("seats.changed", actor_id, account_id, old=old, new=seats)
        return result

    def cancel(self, account_id: str, actor_id: str) -> datetime:
        """Cancel at the period end; returns the date the account moves to Free."""
        ends = subs.cancel(self._account(account_id).subscription)
        self._audit("plan.changed", actor_id, account_id, new=Plan.FREE.value,
                    effective_at=ends.isoformat())
        return ends

    # -- renewal and dunning ----------------------------------------------------
    def renew(self, account_id: str) -> ChargeResult | None:
        """At the period end: apply pending changes, then invoice and charge the new period."""
        acct = self._account(account_id)
        sub, old_plan = acct.subscription, acct.subscription.plan
        credit = sub.pending_credit
        if acct.unpaid_invoice_id is not None:   # dunning decides what happens next
            return None
        if not subs.roll_period(sub, self.clock.now()):
            return None
        if sub.plan is not old_plan:
            self._audit("plan.changed", SYSTEM_ACTOR, account_id, old=old_plan.value,
                        new=sub.plan.value)
        if not sub.plan.is_paid:
            return None
        lines = [InvoiceLine(f"{sub.plan.value} plan, {sub.interval.value}", sub.seats,
                             subs.seat_price_for(sub))]
        if credit and not credit.is_zero:
            lines.append(InvoiceLine("Credit for removed seats", 1, -credit))
        sub.pending_credit = None
        return self._collect(acct, lines, sub.interval, must_succeed=False)

    def run_dunning(self, account_id: str) -> DunningAction | None:
        """Daily job: retry an unpaid invoice or apply the day-14 / day-44 step."""
        acct = self._account(account_id)
        if acct.unpaid_invoice_id is None:
            return None
        if acct.dunning is None:   # the first attempt hit an outage: try again, uncounted
            outcome = self._charge(acct, self.invoices.get(acct.unpaid_invoice_id))
            return self._start_dunning(acct) if outcome is ChargeOutcome.DECLINED else None
        day = acct.dunning.day_number(self.clock.now())
        action = acct.dunning.due(day)
        if action.retry:
            return self._retry(acct)
        if action.new_plan is Plan.FREE:
            old_plan = acct.subscription.plan
            subs.downgrade_to_free(acct.subscription, self.clock.now())
            self.invoices.void(acct.unpaid_invoice_id)
            acct.dunning = acct.unpaid_invoice_id = None
            self._audit("plan.changed", SYSTEM_ACTOR, account_id, old=old_plan.value,
                        new=Plan.FREE.value, reason="dunning day 44")
        self._send(acct, action.emails, f"{account_id}:day{day}", contacts=False)
        return action

    def _retry(self, acct: _BillingAccount) -> DunningAction:
        invoice = self.invoices.get(acct.unpaid_invoice_id)
        day = acct.dunning.day_number(self.clock.now())
        action = acct.dunning.record_retry(day, self._charge(acct, invoice))
        for key in action.emails:
            self._send(acct, (key,), f"{invoice.id}:{acct.dunning.failed_attempts}",
                       contacts=key == EMAIL_PAYMENT_FAILED)
        if action.finished:
            acct.dunning = None
        return action

    def _start_dunning(self, acct: _BillingAccount) -> DunningAction:
        invoice = self.invoices.get(acct.unpaid_invoice_id)
        if invoice.status is InvoiceStatus.OPEN:
            self.invoices.mark_payment_failed(invoice.id)
        acct.dunning = DunningProcess(self.clock.now())
        action = acct.dunning.start()
        self._send(acct, action.emails, f"{invoice.id}:1", contacts=True)
        return action

    # -- refunds ------------------------------------------------------------------
    def refund(self, account_id: str, actor_id: str, invoice_id: str, amount: Money,
               kind: RefundKind, reason: str, approver: ApproverRole) -> Refund:
        """Issue a refund under the refund policy and send it to the processor."""
        acct, invoice = self._account(account_id), self.invoices.get(invoice_id)
        if invoice.account_id != account_id:
            raise NotFoundError(f"invoice {invoice_id} does not belong to this account")
        refund = request_refund(invoice, amount, kind, reason, approver, self.clock.now(),
                                self.ids, acct.last_goodwill_at)
        settle_refund(refund, invoice, self.processor.refund(invoice.id, amount))
        if kind is RefundKind.GOODWILL and refund.status is not RefundStatus.FAILED:
            acct.last_goodwill_at = refund.created_at
        acct.refunds.append(refund)
        self._audit("refund.issued", actor_id, account_id, refund_id=refund.id,
                    invoice_id=invoice_id, amount_cents=amount.cents, ticket=refund.ticket_id)
        return refund

    # -- helpers --------------------------------------------------------------------
    def _collect(self, acct: _BillingAccount, lines: list[InvoiceLine],
                 interval: BillingInterval | None, must_succeed: bool) -> ChargeResult:
        """Invoice ``lines`` and charge the payment method.

        ``must_succeed`` (first purchase, upgrade): charge first and raise on a
        decline or outage, so nothing changes. Otherwise (renewal, seats) the
        invoice is issued first; a decline starts dunning, an outage leaves
        the invoice open to be retried without counting as a failure.
        """
        method = acct.payment_method
        if method is None:
            raise ValidationError("add a payment method first")
        if acct.unpaid_invoice_id is not None:
            raise ConflictError("pay the open balance before making further charges")
        total = sum((line.amount for line in lines), Money.zero(lines[0].unit_price.currency))
        by_invoice = method.type is PaymentMethodType.INVOICE
        if must_succeed and not by_invoice and total.cents > 0:
            outcome = self.processor.charge(method.token, total)
            if outcome is ChargeOutcome.DECLINED:
                raise PaymentFailedError("the payment processor declined the charge")
            if outcome is ChargeOutcome.UNAVAILABLE:
                raise ProcessorUnavailableError("the payment processor is unavailable; try again")
        invoice = self.invoices.create(acct.account_id, lines, acct.profile.details, interval,
                                       INVOICE_NET_TERMS_DAYS if by_invoice else 0)
        self._send(acct, ("invoice_ready",), invoice.id, contacts=True)
        if by_invoice:
            return ChargeResult(None, invoice, total)
        if must_succeed or total.cents <= 0:
            self.invoices.mark_paid(invoice.id)
            return ChargeResult(ChargeOutcome.SUCCEEDED, invoice, total)
        acct.unpaid_invoice_id = invoice.id
        outcome = self._charge(acct, invoice)
        state = None
        if outcome is ChargeOutcome.DECLINED:
            state = self._start_dunning(acct).new_state
        return ChargeResult(outcome, invoice, total, state)

    def _charge(self, acct: _BillingAccount, invoice: Invoice) -> ChargeOutcome:
        outcome = self.processor.charge(acct.payment_method.token, invoice.total)
        if outcome is ChargeOutcome.SUCCEEDED:
            self.invoices.mark_paid(invoice.id)
            acct.unpaid_invoice_id = None
        return outcome

    def _send(self, acct: _BillingAccount, templates: tuple[str, ...], object_id: str,
              contacts: bool) -> None:
        if self.notifier is None:
            return
        to = acct.billing_emails + (acct.profile.contacts if contacts else [])
        invoice_id = object_id.split(":")[0] if object_id.startswith("INV-") else None
        for key in templates:
            self.notifier.send(key, to, object_id=object_id, account_id=acct.account_id,
                               invoice_id=invoice_id)

    def _audit(self, event_type: str, actor_id: str, account_id: str, **metadata: Any) -> None:
        if self.audit is not None:
            self.audit.record(event_type, actor_id, account_id, None, **metadata)

"""Refund policy: eligibility, limits, approval tiers and goodwill.

Rules implemented here:

- Annual plan closed or cancelled within 30 days of purchase: full refund.
  On day 31 or later there is no refund for unused time.
- Monthly plans: no refund for unused time.
- Duplicate charges and billing errors: always refunded in full, on any plan
  and at any time.
- A refund can never exceed the paid amount of the invoice minus earlier
  refunds.
- Approval by amount: up to $500.00 any support agent; $500.01 to $5,000.00 a
  support team lead; over $5,000.00 the billing manager.
- Goodwill refunds: team-lead approval at any amount, and only one per
  account per 12 months.
- The reason must name the support ticket, for example ``SUP-58213``.
- A refund starts as ``pending`` and becomes ``succeeded`` or ``failed`` when
  the processor answers. The customer is told 5 to 10 business days.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import Enum

from acme_cloud.billing.models import (
    BillingInterval,
    ChargeOutcome,
    Invoice,
    InvoiceStatus,
    Refund,
    RefundStatus,
    add_months,
)
from acme_cloud.common.errors import ConflictError, PermissionDeniedError, ValidationError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.common.money import Money

#: Annual plans are refunded in full when cancelled within this many days.
ANNUAL_REFUND_WINDOW_DAYS = 30

#: Largest refund a support agent may approve: $500.00.
AGENT_APPROVAL_LIMIT_CENTS = 50_000

#: Largest refund a team lead may approve: $5,000.00. Above: billing manager.
TEAM_LEAD_APPROVAL_LIMIT_CENTS = 500_000

#: One goodwill refund per account per 12 months.
GOODWILL_WINDOW_MONTHS = 12

#: Timeline told to the customer, in business days (minimum, maximum).
REFUND_TIMELINE_BUSINESS_DAYS = (5, 10)

_TICKET_RE = re.compile(r"\bSUP-\d{5}\b")


class RefundKind(str, Enum):
    """Why money is given back."""

    CANCELLATION = "cancellation"          # plan closed or cancelled
    DUPLICATE_CHARGE = "duplicate_charge"
    BILLING_ERROR = "billing_error"
    GOODWILL = "goodwill"


class ApproverRole(str, Enum):
    """Staff roles that can approve refunds, lowest to highest."""

    SUPPORT_AGENT = "support_agent"
    TEAM_LEAD = "team_lead"
    BILLING_MANAGER = "billing_manager"

    @property
    def rank(self) -> int:
        return list(ApproverRole).index(self)


def required_approver(amount: Money, kind: RefundKind = RefundKind.CANCELLATION) -> ApproverRole:
    """Lowest role that may approve a refund of ``amount``."""
    if amount.cents > TEAM_LEAD_APPROVAL_LIMIT_CENTS:
        return ApproverRole.BILLING_MANAGER
    if amount.cents > AGENT_APPROVAL_LIMIT_CENTS or kind is RefundKind.GOODWILL:
        return ApproverRole.TEAM_LEAD
    return ApproverRole.SUPPORT_AGENT


def can_approve(role: ApproverRole, amount: Money,
                kind: RefundKind = RefundKind.CANCELLATION) -> bool:
    """True when ``role`` is at or above the role the amount and kind need."""
    return role.rank >= required_approver(amount, kind).rank


def extract_ticket_id(reason: str) -> str:
    """Return the ``SUP-<5 digits>`` ticket number in ``reason``; it is required."""
    match = _TICKET_RE.search(reason or "")
    if not match:
        raise ValidationError("the refund reason must include the ticket number, e.g. SUP-58213")
    return match.group(0)


def refundable_under_policy(invoice: Invoice, kind: RefundKind, now: datetime) -> Money:
    """Most that may be refunded for ``invoice`` and ``kind``; raises if not eligible."""
    if invoice.status is not InvoiceStatus.PAID or invoice.paid_at is None:
        raise ConflictError("only a paid invoice can be refunded", status=invoice.status.value)
    if kind is RefundKind.CANCELLATION:
        if invoice.interval is not BillingInterval.ANNUAL:
            raise ValidationError("monthly plans are not refunded for unused time")
        if now - invoice.paid_at > timedelta(days=ANNUAL_REFUND_WINDOW_DAYS):
            raise ValidationError(
                f"annual plans are refunded only within {ANNUAL_REFUND_WINDOW_DAYS} days of purchase")
    return invoice.refundable_amount


def goodwill_allowed(last_goodwill_at: datetime | None, now: datetime) -> bool:
    """True when the account had no goodwill refund in the last 12 months."""
    return last_goodwill_at is None or now >= add_months(last_goodwill_at, GOODWILL_WINDOW_MONTHS)


def request_refund(
    invoice: Invoice, amount: Money, kind: RefundKind, reason: str, approver: ApproverRole,
    now: datetime, ids: IdGenerator, last_goodwill_at: datetime | None = None,
) -> Refund:
    """Validate a refund and create it as ``pending``.

    The amount is reserved on the invoice at once, so two pending refunds
    cannot together exceed what was paid.
    """
    ticket_id = extract_ticket_id(reason)
    if amount.cents <= 0:
        raise ValidationError("a refund amount must be positive")
    limit = refundable_under_policy(invoice, kind, now)
    if amount > limit:
        raise ValidationError(
            "a refund cannot exceed the paid amount minus earlier refunds",
            requested=str(amount), refundable=str(limit))
    if kind is RefundKind.GOODWILL and not goodwill_allowed(last_goodwill_at, now):
        raise ConflictError(
            f"only one goodwill refund per account per {GOODWILL_WINDOW_MONTHS} months")
    needed = required_approver(amount, kind)
    if approver.rank < needed.rank:
        raise PermissionDeniedError(
            f"this refund needs approval by a {needed.value}", required=needed.value)
    invoice.refunded_amount = invoice.refunded_amount + amount
    return Refund(
        id=ids.new("rf"), invoice_id=invoice.id, account_id=invoice.account_id, amount=amount,
        kind=kind.value, reason=reason, ticket_id=ticket_id,
        approved_by_role=approver.value, created_at=now,
    )


def settle_refund(refund: Refund, invoice: Invoice, outcome: ChargeOutcome) -> Refund:
    """Apply the processor's answer: ``succeeded``, ``failed`` or still ``pending``.

    A failed refund releases its reserved amount on the invoice. A processor
    outage leaves the refund ``pending`` to be sent again.
    """
    if refund.status is not RefundStatus.PENDING:
        raise ConflictError(f"refund is already {refund.status.value}")
    if outcome is ChargeOutcome.SUCCEEDED:
        refund.status = RefundStatus.SUCCEEDED
    elif outcome is ChargeOutcome.DECLINED:
        refund.status = RefundStatus.FAILED
        invoice.refunded_amount = invoice.refunded_amount - refund.amount
    return refund

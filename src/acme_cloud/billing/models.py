"""Billing data models: subscriptions, invoices, payment methods and refunds.

Business rules visible in these models:

- Billing intervals are ``monthly`` and ``annual``. Annual costs 10 times the
  monthly price.
- Invoice IDs look like ``INV-2026-004812``. An invoice keeps a frozen copy of
  the billing details it was issued with, so later edits to the company name,
  address, VAT/GST ID or PO number apply to future invoices only.
- Refund statuses are ``pending``, ``succeeded`` and ``failed``. Refund IDs
  look like ``rf_8M2K4Q9X7T``.
- Payment method types are ``card``, ``paypal``, ``upi``, ``ach``, ``sepa`` and
  ``invoice`` (net-30, Enterprise).
- A payment method is stored only as an opaque processor token such as
  ``pm_9XK2M4QH7T`` plus its type and card brand. There is deliberately no
  field for a card number, expiry date or security code: card numbers are
  never stored, logged or shown (ADR 0004).
- All amounts are ``Money`` in whole cents.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import AcmeError
from acme_cloud.common.money import Money


class BillingInterval(str, Enum):
    """How often a subscription renews."""

    MONTHLY = "monthly"
    ANNUAL = "annual"

    @property
    def months(self) -> int:
        """Length of one billing period in months: 1 or 12."""
        return 12 if self is BillingInterval.ANNUAL else 1


class InvoiceStatus(str, Enum):
    """Lifecycle of an invoice."""

    OPEN = "open"                      # issued, not paid yet
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"  # the processor declined the charge
    VOID = "void"                      # replaced by a reissue or written off


class RefundStatus(str, Enum):
    """A refund is ``pending`` until the processor confirms or rejects it."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentMethodType(str, Enum):
    """Kinds of payment method an account can pay with."""

    CARD = "card"
    PAYPAL = "paypal"
    UPI = "upi"
    ACH = "ach"
    SEPA = "sepa"
    INVOICE = "invoice"


class ChargeOutcome(str, Enum):
    """Answer of the payment processor to an authorization, charge or refund.

    ``UNAVAILABLE`` means the processor itself is down. It is not a decline
    and must never be counted as a dunning failure (INC-2026-002).
    """

    SUCCEEDED = "succeeded"
    DECLINED = "declined"
    UNAVAILABLE = "unavailable"


class ProcessorUnavailableError(AcmeError):
    """The payment processor is down; nothing was charged, try again later."""


def add_months(moment: datetime, months: int) -> datetime:
    """Add calendar months, clamping the day (31 January + 1 month = 28/29 February)."""
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


@dataclass(frozen=True)
class BillingDetails:
    """Company details printed on an invoice (Settings > Billing > Billing details)."""

    company_name: str = ""
    address: str = ""
    vat_id: str = ""      # company VAT/GST registration, never a personal ID
    po_number: str = ""


@dataclass
class Subscription:
    """An account's plan, seats and current paid period."""

    id: str                     # sub_ + 8
    account_id: str
    plan: Plan
    interval: BillingInterval
    seats: int
    period_start: datetime
    period_end: datetime
    currency: str = "USD"
    custom_seat_price: Money | None = None   # Enterprise only, per seat per period
    pending_plan: Plan | None = None         # downgrade waiting for the period end
    cancel_at_period_end: bool = False
    pending_credit: Money | None = None      # seat-removal credit for the next invoice


@dataclass(frozen=True)
class InvoiceLine:
    """One line of an invoice. Credits have a negative ``unit_price``."""

    description: str
    quantity: int
    unit_price: Money

    @property
    def amount(self) -> Money:
        return self.unit_price * self.quantity


@dataclass
class Invoice:
    """An issued invoice with a frozen copy of the billing details."""

    id: str                      # INV-<year>-<6 digits>
    account_id: str
    issued_at: datetime
    due_at: datetime
    lines: tuple[InvoiceLine, ...]
    billing_details: BillingDetails
    interval: BillingInterval | None = None
    status: InvoiceStatus = InvoiceStatus.OPEN
    paid_at: datetime | None = None
    paid_amount: Money | None = None
    refunded_amount: Money | None = None
    reissue_of: str | None = None

    def __post_init__(self) -> None:
        zero = Money.zero(self.currency)
        self.paid_amount = self.paid_amount or zero
        self.refunded_amount = self.refunded_amount or zero

    @property
    def currency(self) -> str:
        return self.lines[0].unit_price.currency

    @property
    def total(self) -> Money:
        """Sum of all lines, credits included."""
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.amount
        return total

    @property
    def refundable_amount(self) -> Money:
        """Paid amount minus earlier refunds: the most a new refund may be."""
        return self.paid_amount - self.refunded_amount


@dataclass(frozen=True)
class PaymentMethod:
    """A stored payment method: an opaque token, its type and card brand only."""

    token: str                   # pm_ + 10, issued by the processor
    account_id: str
    type: PaymentMethodType
    brand: str | None            # visa, mastercard, amex, discover; None if not a card
    added_at: datetime


@dataclass
class Refund:
    """A refund against one invoice."""

    id: str                      # rf_ + 10
    invoice_id: str
    account_id: str
    amount: Money
    kind: str                    # cancellation, duplicate_charge, billing_error, goodwill
    reason: str                  # free text, must name the ticket (SUP-58213)
    ticket_id: str
    approved_by_role: str
    created_at: datetime
    status: RefundStatus = RefundStatus.PENDING

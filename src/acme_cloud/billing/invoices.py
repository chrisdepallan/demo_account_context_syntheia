"""Invoices, billing details and billing contacts.

Rules implemented here:

- Invoice numbers are ``INV-<year>-<6 digits>``, for example
  ``INV-2026-004812``. The year is the year of issue.
- An invoice has one or more lines; the total is the sum of the lines.
  Credits (for removed seats) are lines with a negative amount.
- Invoices are kept for 7 years, then purged.
- An invoice can be reissued (for example with a corrected company name or
  VAT ID) only within 12 months of its issue date, and only through support.
  The reissue gets a new number and the original is marked ``void``.
- Billing details (company name, billing address, VAT/GST ID, PO number) are
  copied onto each invoice when it is issued. Editing them changes future
  invoices only; issued invoices keep the old details.
- Billing contacts: up to 5 extra email addresses receive invoices and
  payment alerts. They cannot log in unless they are also members.
- Enterprise invoices paid by invoice are due 30 days after issue (net-30);
  everything else is due on the day of issue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from acme_cloud.billing.models import (
    BillingDetails,
    BillingInterval,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    add_months,
)
from acme_cloud.common.clock import Clock
from acme_cloud.common.errors import ConflictError, LimitExceededError, NotFoundError, ValidationError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.common.money import Money

#: Invoices are kept for 7 years.
INVOICE_RETENTION_YEARS = 7

#: Support can reissue an invoice issued in the last 12 months.
REISSUE_WINDOW_MONTHS = 12

#: Extra addresses that receive invoices and payment alerts.
MAX_BILLING_CONTACTS = 5

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class BillingProfile:
    """Billing details and billing contacts of one account."""

    account_id: str
    details: BillingDetails = field(default_factory=BillingDetails)
    contacts: list[str] = field(default_factory=list)

    def update_details(self, **changes: str) -> BillingDetails:
        """Change billing details. Only invoices issued afterwards use them."""
        self.details = replace(self.details, **changes)
        return self.details

    def add_contact(self, email: str) -> None:
        """Add a billing contact; at most 5 per account."""
        email = email.strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValidationError("billing contact must be an email address")
        if email in self.contacts:
            raise ConflictError("this address is already a billing contact")
        if len(self.contacts) >= MAX_BILLING_CONTACTS:
            raise LimitExceededError(
                f"an account can have at most {MAX_BILLING_CONTACTS} billing contacts",
                limit=MAX_BILLING_CONTACTS)
        self.contacts.append(email)

    def remove_contact(self, email: str) -> None:
        email = email.strip().lower()
        if email not in self.contacts:
            raise NotFoundError("no such billing contact")
        self.contacts.remove(email)


class InvoiceBook:
    """In-memory store that issues, pays, reissues and purges invoices."""

    def __init__(self, clock: Clock, ids: IdGenerator) -> None:
        self._clock = clock
        self._ids = ids
        self._invoices: dict[str, Invoice] = {}

    def create(
        self, account_id: str, lines: list[InvoiceLine], billing_details: BillingDetails,
        interval: BillingInterval | None = None, net_terms_days: int = 0,
    ) -> Invoice:
        """Issue an ``open`` invoice with a copy of the current billing details."""
        if not lines:
            raise ValidationError("an invoice needs at least one line")
        if len({line.unit_price.currency for line in lines}) > 1:
            raise ValidationError("all lines of an invoice use one currency")
        now = self._clock.now()
        invoice = Invoice(
            id=self._ids.new_invoice_id(now.year), account_id=account_id, issued_at=now,
            due_at=now + timedelta(days=net_terms_days), lines=tuple(lines),
            billing_details=billing_details, interval=interval,
        )
        self._invoices[invoice.id] = invoice
        return invoice

    def get(self, invoice_id: str) -> Invoice:
        if invoice_id not in self._invoices:
            raise NotFoundError(f"invoice {invoice_id} does not exist")
        return self._invoices[invoice_id]

    def for_account(self, account_id: str) -> list[Invoice]:
        """Invoices of an account, oldest first."""
        return [inv for inv in self._invoices.values() if inv.account_id == account_id]

    def mark_paid(self, invoice_id: str, amount: Money | None = None) -> Invoice:
        """Record payment (default: the invoice total)."""
        invoice = self.get(invoice_id)
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.VOID):
            raise ConflictError(f"invoice is already {invoice.status.value}")
        invoice.status = InvoiceStatus.PAID
        invoice.paid_amount = amount if amount is not None else invoice.total
        invoice.paid_at = self._clock.now()
        return invoice

    def mark_payment_failed(self, invoice_id: str) -> Invoice:
        invoice = self.get(invoice_id)
        if invoice.status is not InvoiceStatus.OPEN:
            raise ConflictError(f"invoice is {invoice.status.value}, not open")
        invoice.status = InvoiceStatus.PAYMENT_FAILED
        return invoice

    def void(self, invoice_id: str) -> Invoice:
        invoice = self.get(invoice_id)
        invoice.status = InvoiceStatus.VOID
        return invoice

    def can_reissue(self, invoice: Invoice) -> bool:
        """True while the invoice is at most 12 months old and not void."""
        deadline = add_months(invoice.issued_at, REISSUE_WINDOW_MONTHS)
        return invoice.status is not InvoiceStatus.VOID and self._clock.now() <= deadline

    def reissue(self, invoice_id: str, billing_details: BillingDetails) -> Invoice:
        """Replace an invoice with a corrected copy under a new number."""
        original = self.get(invoice_id)
        if not self.can_reissue(original):
            raise ConflictError(
                f"invoices can be reissued only within {REISSUE_WINDOW_MONTHS} months of issue")
        now = self._clock.now()
        copy = replace(
            original, id=self._ids.new_invoice_id(now.year), issued_at=now,
            billing_details=billing_details, reissue_of=original.id,
        )
        original.status = InvoiceStatus.VOID
        self._invoices[copy.id] = copy
        return copy

    def retention_until(self, invoice: Invoice) -> datetime:
        """Date until which the invoice must be kept: issue date plus 7 years."""
        return add_months(invoice.issued_at, INVOICE_RETENTION_YEARS * 12)

    def purge_expired(self) -> int:
        """Delete invoices older than 7 years; return how many were deleted."""
        now = self._clock.now()
        expired = [i for i, inv in self._invoices.items() if now > self.retention_until(inv)]
        for invoice_id in expired:
            del self._invoices[invoice_id]
        return len(expired)

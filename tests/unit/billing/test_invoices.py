"""Invoices: numbering, totals, 7-year retention, 12-month reissue, billing contacts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from acme_cloud.billing.invoices import (
    INVOICE_RETENTION_YEARS,
    MAX_BILLING_CONTACTS,
    REISSUE_WINDOW_MONTHS,
    BillingProfile,
    InvoiceBook,
)
from acme_cloud.billing.models import BillingDetails, InvoiceLine, InvoiceStatus
from acme_cloud.common.errors import ConflictError, LimitExceededError, NotFoundError, ValidationError
from acme_cloud.common.ids import is_valid_id
from acme_cloud.common.money import Money

ACCOUNT = "acc_7F3K9Q2M"
DETAILS = BillingDetails(company_name="Example Ltd", address="1 Sample Street", po_number="PO-17")
LINES = [InvoiceLine("pro plan, monthly", 5, Money(2000))]


@pytest.fixture
def book(clock, ids):
    return InvoiceBook(clock, ids)


def test_constants_match_the_billing_rules():
    assert (INVOICE_RETENTION_YEARS, REISSUE_WINDOW_MONTHS, MAX_BILLING_CONTACTS) == (7, 12, 5)


def test_invoice_numbers_are_inv_year_and_six_digits(book, clock):
    first = book.create(ACCOUNT, LINES, DETAILS)
    second = book.create(ACCOUNT, LINES, DETAILS)
    assert (first.id, second.id) == ("INV-2026-000001", "INV-2026-000002")
    assert is_valid_id(first.id, "invoice")
    clock.set(datetime(2027, 3, 1, tzinfo=timezone.utc))
    assert book.create(ACCOUNT, LINES, DETAILS).id.startswith("INV-2027-")


def test_total_is_the_sum_of_the_lines_including_credits(book):
    lines = LINES + [InvoiceLine("Credit for removed seats", 1, Money(-1032))]
    invoice = book.create(ACCOUNT, lines, DETAILS)
    assert invoice.lines[0].amount == Money(10_000)
    assert invoice.total == Money(8968)


def test_an_invoice_needs_a_line_and_one_currency(book):
    with pytest.raises(ValidationError):
        book.create(ACCOUNT, [], DETAILS)
    with pytest.raises(ValidationError):
        book.create(ACCOUNT, LINES + [InvoiceLine("x", 1, Money(100, "EUR"))], DETAILS)


def test_paying_an_invoice_records_amount_and_time(book, clock):
    invoice = book.create(ACCOUNT, LINES, DETAILS)
    assert invoice.status is InvoiceStatus.OPEN and invoice.paid_amount.is_zero
    book.mark_paid(invoice.id)
    assert invoice.status is InvoiceStatus.PAID
    assert (invoice.paid_amount, invoice.paid_at) == (Money(10_000), clock.now())
    with pytest.raises(ConflictError):
        book.mark_paid(invoice.id)


def test_enterprise_invoices_are_due_net_30(book):
    invoice = book.create(ACCOUNT, LINES, DETAILS, net_terms_days=30)
    assert invoice.due_at - invoice.issued_at == timedelta(days=30)


def test_billing_details_apply_to_future_invoices_only(book):
    profile = BillingProfile(ACCOUNT, DETAILS)
    old = book.create(ACCOUNT, LINES, profile.details)
    profile.update_details(company_name="Example Holdings Ltd", vat_id="EU-VAT-EXAMPLE")
    new = book.create(ACCOUNT, LINES, profile.details)
    assert old.billing_details.company_name == "Example Ltd"
    assert new.billing_details.company_name == "Example Holdings Ltd"
    assert new.billing_details.po_number == "PO-17"  # untouched fields are kept


@pytest.mark.parametrize("days_old, allowed", [(0, True), (365, True), (366, False)])
def test_reissue_is_possible_only_for_the_last_12_months(book, clock, days_old, allowed):
    invoice = book.create(ACCOUNT, LINES, DETAILS)
    book.mark_paid(invoice.id)
    clock.advance(days=days_old)
    corrected = BillingDetails(company_name="Example GmbH")
    if not allowed:
        with pytest.raises(ConflictError):
            book.reissue(invoice.id, corrected)
        return
    copy = book.reissue(invoice.id, corrected)
    assert copy.id != invoice.id and copy.reissue_of == invoice.id
    assert copy.billing_details == corrected and copy.total == invoice.total
    assert copy.status is InvoiceStatus.PAID and invoice.status is InvoiceStatus.VOID


def test_invoices_are_kept_for_7_years_then_purged(book, clock):
    invoice = book.create(ACCOUNT, LINES, DETAILS)
    assert book.retention_until(invoice) == datetime(2033, 1, 5, 9, 0, tzinfo=timezone.utc)
    clock.set(datetime(2033, 1, 5, 9, 0, tzinfo=timezone.utc))
    assert book.purge_expired() == 0
    clock.advance(days=1)
    assert book.purge_expired() == 1
    with pytest.raises(NotFoundError):
        book.get(invoice.id)


def test_for_account_lists_only_that_accounts_invoices(book):
    mine = book.create(ACCOUNT, LINES, DETAILS)
    book.create("acc_2B6N8R4V", LINES, DETAILS)
    assert book.for_account(ACCOUNT) == [mine]


def test_five_billing_contacts_are_allowed_and_the_sixth_is_refused():
    profile = BillingProfile(ACCOUNT)
    for number in range(1, 6):
        profile.add_contact(f"billing{number}@example.com")
    assert len(profile.contacts) == 5
    with pytest.raises(LimitExceededError) as error:
        profile.add_contact("billing6@example.com")
    assert error.value.code == "ERR_LIMIT_EXCEEDED"
    profile.remove_contact("billing1@example.com")
    profile.add_contact("billing6@example.com")  # room again after removing one


def test_billing_contacts_must_be_unique_email_addresses():
    profile = BillingProfile(ACCOUNT)
    profile.add_contact("Finance@Example.com")
    assert profile.contacts == ["finance@example.com"]
    with pytest.raises(ConflictError):
        profile.add_contact("finance@example.com")
    with pytest.raises(ValidationError):
        profile.add_contact("not-an-address")
    with pytest.raises(NotFoundError):
        profile.remove_contact("nobody@example.com")

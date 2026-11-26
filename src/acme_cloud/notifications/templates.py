"""Email templates: every email the product sends, who gets it and when.

| Template key         | Sent to                                 | When                              |
|----------------------|-----------------------------------------|-----------------------------------|
| ``trial_ending``     | Owner                                   | 3 days before the trial ends      |
| ``payment_failed``   | Owner, Billing admins, billing contacts | Day 0 and after each failed retry |
| ``account_read_only``| Owner, Billing admins                   | Day 14 of dunning                 |
| ``account_downgraded``| Owner, Billing admins                  | Day 44 of dunning                 |
| ``invoice_ready``    | Owner, Billing admins, billing contacts | Each invoice                      |
| ``storage_warning``  | Owner, Admins                           | Storage at 90%                    |
| ``storage_full``     | Owner, Admins                           | Storage at 100%                   |
| ``invitation``       | Invitee                                 | On invite and resend              |
| ``password_reset``   | User                                    | On request                        |
| ``login_locked``     | User                                    | 1-hour lockout                    |
| ``key_expiring``     | Owner                                   | 14 days before key expiry         |
| ``ownership_transfer``| New Owner                              | On request                        |
| ``account_closed``   | Owner                                   | On closure, with the 30-day restore link |
| ``export_ready``     | Requester                               | Export finished                   |

Subjects and bodies use ``{placeholder}`` fields filled from the send
context. A placeholder with no value is left as written, so a missing value
never stops an email. No template ever contains a password, a full API key
or payment card data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from acme_cloud.common.errors import ValidationError


class RecipientRule(str, Enum):
    """Who a template is addressed to."""

    OWNER = "owner"
    OWNER_BILLING_ADMINS = "owner_billing_admins"
    OWNER_BILLING_ADMINS_CONTACTS = "owner_billing_admins_contacts"
    OWNER_ADMINS = "owner_admins"
    DIRECT = "direct"   # one named person: invitee, user, new Owner, requester


@dataclass(frozen=True)
class EmailTemplate:
    """One email template."""

    key: str
    subject: str
    body: str
    recipients: RecipientRule
    sent_to: str                    # the "Sent to" column, in words
    trigger: str                    # the "When" column
    object_field: str | None = None  # context field that names the object (idempotency)


@dataclass(frozen=True)
class RenderedEmail:
    """Subject and body after the placeholders are filled in."""

    template_key: str
    subject: str
    body: str


def _t(key: str, subject: str, body: str, recipients: RecipientRule, sent_to: str,
       trigger: str, object_field: str | None = None) -> EmailTemplate:
    return EmailTemplate(key, subject, body, recipients, sent_to, trigger, object_field)


_R = RecipientRule
_BILLING = "Owner, Billing admins"
_BILLING_ALL = "Owner, Billing admins, billing contacts"

TEMPLATES: dict[str, EmailTemplate] = {t.key: t for t in (
    _t("trial_ending", "Your Acme Cloud trial ends in 3 days",
       "Add a payment method to keep the Pro plan. Without one the account moves to Free.",
       _R.OWNER, "Owner", "3 days before the trial ends"),
    _t("payment_failed", "Payment failed for your Acme Cloud account",
       "We could not charge your payment method. We retry on days 1, 3, 7 and 14.",
       _R.OWNER_BILLING_ADMINS_CONTACTS, _BILLING_ALL, "Day 0 and after each failed retry"),
    _t("account_read_only", "Your Acme Cloud account is now read-only",
       "The balance is unpaid after 14 days. Users can log in but cannot edit. "
       "Paying restores full access within 5 minutes.",
       _R.OWNER_BILLING_ADMINS, _BILLING, "Day 14"),
    _t("account_downgraded", "Your Acme Cloud account was moved to Free",
       "The balance is unpaid after 44 days. Members over the Free limit are now guests.",
       _R.OWNER_BILLING_ADMINS, _BILLING, "Day 44"),
    _t("invoice_ready", "Invoice {invoice_id} is ready",
       "Download the PDF from Settings > Billing > Invoices. Invoices are kept for 7 years.",
       _R.OWNER_BILLING_ADMINS_CONTACTS, _BILLING_ALL, "Each invoice", "invoice_id"),
    _t("storage_warning", "Storage is 90% full",
       "Uploads are blocked at 100%. Add a storage pack: 100 GB for $10/month.",
       _R.OWNER_ADMINS, "Owner, Admins", "Storage at 90%"),
    _t("storage_full", "Storage is full",
       "New uploads are blocked. Existing files stay editable.",
       _R.OWNER_ADMINS, "Owner, Admins", "Storage at 100%"),
    _t("invitation", "{inviter} invited you to Acme Cloud",
       "Accept within 7 days: {link}", _R.DIRECT, "Invitee", "On invite and resend"),
    _t("password_reset", "Reset your Acme Cloud password",
       "This link works once and for 60 minutes: {link}", _R.DIRECT, "User", "On request"),
    _t("login_locked", "Your Acme Cloud login is locked for 1 hour",
       "There were 10 failed attempts within 1 hour. A password reset unlocks at once.",
       _R.DIRECT, "User", "1-hour lockout"),
    _t("key_expiring", "API key {key_id} expires in 14 days",
       "Rotate the key in Settings > API keys. The old key works for 24 hours after rotation.",
       _R.OWNER, "Owner", "14 days before key expiry", "key_id"),
    _t("ownership_transfer", "You were asked to become Owner of an Acme Cloud account",
       "Accept within 7 days: {link}", _R.DIRECT, "New Owner", "On request"),
    _t("account_closed", "Your Acme Cloud account is closed",
       "You can restore it for 30 days: {link}. On day 31 it is deleted for good.",
       _R.OWNER, "Owner", "On closure, includes the 30-day restore link"),
    _t("export_ready", "Your workspace export is ready",
       "Download the ZIP within 7 days: {link}", _R.DIRECT, "Requester", "Export finished",
       "export_id"),
)}

TEMPLATE_KEYS = tuple(TEMPLATES)


class _KeepMissing(dict):
    """Leaves ``{name}`` in place when the context has no value for it."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def get_template(key: str) -> EmailTemplate:
    """Return the template for ``key`` or raise ``ERR_VALIDATION``."""
    if key not in TEMPLATES:
        raise ValidationError(f"unknown email template: {key}", template=key)
    return TEMPLATES[key]


def render(key: str, **context: object) -> RenderedEmail:
    """Fill the subject and body of template ``key`` from ``context``."""
    template = get_template(key)
    values = _KeepMissing(context)
    return RenderedEmail(key, template.subject.format_map(values), template.body.format_map(values))

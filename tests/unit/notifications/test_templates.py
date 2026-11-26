"""Email templates: the 14 template keys, who they go to and when."""

from __future__ import annotations

import pytest

from acme_cloud.common.errors import ValidationError
from acme_cloud.notifications.templates import (
    TEMPLATE_KEYS,
    TEMPLATES,
    RecipientRule,
    get_template,
    render,
)

R = RecipientRule

#: (template key, recipient rule, "Sent to", "When") from the facts sheet.
EXPECTED = [
    ("trial_ending", R.OWNER, "Owner", "3 days before the trial ends"),
    ("payment_failed", R.OWNER_BILLING_ADMINS_CONTACTS,
     "Owner, Billing admins, billing contacts", "Day 0 and after each failed retry"),
    ("account_read_only", R.OWNER_BILLING_ADMINS, "Owner, Billing admins", "Day 14"),
    ("account_downgraded", R.OWNER_BILLING_ADMINS, "Owner, Billing admins", "Day 44"),
    ("invoice_ready", R.OWNER_BILLING_ADMINS_CONTACTS,
     "Owner, Billing admins, billing contacts", "Each invoice"),
    ("storage_warning", R.OWNER_ADMINS, "Owner, Admins", "Storage at 90%"),
    ("storage_full", R.OWNER_ADMINS, "Owner, Admins", "Storage at 100%"),
    ("invitation", R.DIRECT, "Invitee", "On invite and resend"),
    ("password_reset", R.DIRECT, "User", "On request"),
    ("login_locked", R.DIRECT, "User", "1-hour lockout"),
    ("key_expiring", R.OWNER, "Owner", "14 days before key expiry"),
    ("ownership_transfer", R.DIRECT, "New Owner", "On request"),
    ("account_closed", R.OWNER, "Owner", "On closure, includes the 30-day restore link"),
    ("export_ready", R.DIRECT, "Requester", "Export finished"),
]


def test_there_are_exactly_the_14_templates_of_the_facts_sheet():
    assert list(TEMPLATE_KEYS) == [row[0] for row in EXPECTED]
    assert len(TEMPLATES) == 14


@pytest.mark.parametrize("key, rule, sent_to, trigger", EXPECTED)
def test_each_template_has_its_recipients_and_trigger(key, rule, sent_to, trigger):
    template = get_template(key)
    assert template.key == key
    assert (template.recipients, template.sent_to, template.trigger) == (rule, sent_to, trigger)
    assert template.subject and template.body


def test_unknown_template_is_a_validation_error():
    with pytest.raises(ValidationError) as error:
        get_template("weekly_digest")
    assert error.value.code == "ERR_VALIDATION"
    with pytest.raises(ValidationError):
        render("weekly_digest")


def test_render_fills_placeholders_from_the_context():
    email = render("invoice_ready", invoice_id="INV-2026-004812")
    assert email.template_key == "invoice_ready"
    assert email.subject == "Invoice INV-2026-004812 is ready"
    assert "7 years" in email.body


def test_render_fills_subject_and_body():
    email = render("invitation", inviter="Sam", link="https://app.acme-cloud.example/invite/x")
    assert email.subject == "Sam invited you to Acme Cloud"
    assert email.body == "Accept within 7 days: https://app.acme-cloud.example/invite/x"


def test_missing_placeholder_is_left_as_written_and_extra_context_is_ignored():
    email = render("key_expiring", account_id="acc_7F3K9Q2M")
    assert email.subject == "API key {key_id} expires in 14 days"


@pytest.mark.parametrize(
    "key, text",
    [
        ("payment_failed", "days 1, 3, 7 and 14"),
        ("account_read_only", "within 5 minutes"),
        ("account_downgraded", "44 days"),
        ("storage_warning", "100 GB for $10/month"),
        ("password_reset", "60 minutes"),
        ("login_locked", "10 failed attempts within 1 hour"),
        ("account_closed", "30 days"),
        ("export_ready", "7 days"),
    ],
)
def test_bodies_state_the_business_numbers(key, text):
    assert text in get_template(key).body


@pytest.mark.parametrize(
    "key, field",
    [("invoice_ready", "invoice_id"), ("key_expiring", "key_id"), ("export_ready", "export_id"),
     ("payment_failed", None), ("invitation", None)],
)
def test_object_field_used_for_the_idempotency_key(key, field):
    assert get_template(key).object_field == field

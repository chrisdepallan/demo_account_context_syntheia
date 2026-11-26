"""Recipient rules: Owner, Billing admins, Admins and billing contacts."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from acme_cloud.common.enums import Role
from acme_cloud.common.errors import ValidationError
from acme_cloud.notifications.recipients import (
    admin_emails,
    billing_admin_emails,
    owner_email,
    recipients_for,
    resolve,
)
from acme_cloud.notifications.templates import RecipientRule


@dataclass
class Member:
    """Anything with ``.email`` and ``.role`` works as a member."""

    email: str
    role: object


OWNER, ADMIN, BILLING, MEMBER, GUEST = (
    "owner@example.com", "admin@example.com", "billing.admin@example.com",
    "member@example.com", "guest@example.com")
CONTACTS = ["finance@example.com", "accounts@example.com"]

MEMBERS = [
    Member(MEMBER, Role.MEMBER),
    Member(BILLING, Role.BILLING_ADMIN),
    Member(ADMIN, Role.ADMIN),
    Member(OWNER, Role.OWNER),
    Member(GUEST, Role.GUEST),
]


def test_owner_is_resolved_and_listed_first():
    assert owner_email(MEMBERS) == [OWNER]
    assert billing_admin_emails(MEMBERS) == [OWNER, BILLING]
    assert admin_emails(MEMBERS) == [OWNER, ADMIN]


@pytest.mark.parametrize(
    "template, expected",
    [
        ("trial_ending", [OWNER]),
        ("key_expiring", [OWNER]),
        ("account_closed", [OWNER]),
        ("account_read_only", [OWNER, BILLING]),               # no billing contacts
        ("account_downgraded", [OWNER, BILLING]),
        ("payment_failed", [OWNER, BILLING, *CONTACTS]),
        ("invoice_ready", [OWNER, BILLING, *CONTACTS]),
        ("storage_warning", [OWNER, ADMIN]),
        ("storage_full", [OWNER, ADMIN]),
    ],
)
def test_recipients_for_each_account_level_template(template, expected):
    assert recipients_for(template, MEMBERS, CONTACTS) == expected


@pytest.mark.parametrize(
    "template", ["invitation", "password_reset", "login_locked", "ownership_transfer",
                 "export_ready"])
def test_personal_emails_go_to_the_one_named_address(template):
    assert recipients_for(template, MEMBERS, CONTACTS, direct="Person@Example.com") == [
        "person@example.com"]
    with pytest.raises(ValidationError):
        recipients_for(template, MEMBERS, CONTACTS)


def test_members_and_guests_never_get_billing_or_storage_emails():
    for template in ("payment_failed", "invoice_ready", "storage_full", "account_read_only"):
        addresses = recipients_for(template, MEMBERS, CONTACTS)
        assert MEMBER not in addresses and GUEST not in addresses


def test_roles_may_be_plain_strings():
    members = [Member(OWNER, "owner"), Member(BILLING, "billing_admin"), Member(ADMIN, "admin")]
    assert resolve(RecipientRule.OWNER_BILLING_ADMINS, members) == [OWNER, BILLING]


def test_someone_who_is_billing_admin_and_billing_contact_gets_one_email():
    contacts = ["Billing.Admin@example.com", "finance@example.com"]
    assert recipients_for("invoice_ready", MEMBERS, contacts) == [
        OWNER, BILLING, "finance@example.com"]


def test_several_billing_admins_all_receive_billing_emails():
    members = MEMBERS + [Member("second.billing@example.com", Role.BILLING_ADMIN)]
    assert resolve(RecipientRule.OWNER_BILLING_ADMINS, members) == [
        OWNER, BILLING, "second.billing@example.com"]


def test_billing_contacts_are_ignored_for_rules_that_do_not_include_them():
    assert resolve(RecipientRule.OWNER_ADMINS, MEMBERS, CONTACTS) == [OWNER, ADMIN]


def test_account_without_members_resolves_to_nobody():
    assert resolve(RecipientRule.OWNER, []) == []
    assert resolve(RecipientRule.OWNER_BILLING_ADMINS_CONTACTS, [], CONTACTS) == CONTACTS

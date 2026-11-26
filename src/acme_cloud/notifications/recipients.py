"""Work out who receives an email.

Recipient groups (roles are ``owner``, ``admin``, ``billing_admin``,
``member``, ``guest``; there is exactly one Owner per account):

- Owner: ``trial_ending``, ``key_expiring``, ``account_closed``.
- Owner and Billing admins: ``account_read_only`` (day 14) and
  ``account_downgraded`` (day 44).
- Owner, Billing admins and billing contacts: ``payment_failed`` and
  ``invoice_ready``. Billing contacts are up to 5 extra addresses that get
  invoices and payment alerts but cannot log in.
- Owner and Admins: ``storage_warning`` (90%) and ``storage_full`` (100%).
- One named person (invitee, user, new Owner, export requester): the caller
  supplies the address.

Members are any objects with ``.email`` and ``.role`` (a ``Role`` or its
string value). The Owner is listed first; addresses are lower-cased and
never repeated, so someone who is both Billing admin and billing contact
gets one email.
"""

from __future__ import annotations

from typing import Any, Iterable

from acme_cloud.common.enums import Role
from acme_cloud.common.errors import ValidationError
from acme_cloud.notifications.templates import RecipientRule, get_template

_ROLES_BY_RULE: dict[RecipientRule, tuple[Role, ...]] = {
    RecipientRule.OWNER: (Role.OWNER,),
    RecipientRule.OWNER_BILLING_ADMINS: (Role.OWNER, Role.BILLING_ADMIN),
    RecipientRule.OWNER_BILLING_ADMINS_CONTACTS: (Role.OWNER, Role.BILLING_ADMIN),
    RecipientRule.OWNER_ADMINS: (Role.OWNER, Role.ADMIN),
}


def _unique(addresses: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for address in addresses:
        cleaned = address.strip().lower()
        if cleaned:
            seen.setdefault(cleaned)
    return list(seen)


def emails_with_roles(members: Iterable[Any], *roles: Role) -> list[str]:
    """Addresses of members whose role is one of ``roles``, in the order of ``roles``."""
    members = list(members)
    found: list[str] = []
    for role in roles:
        found.extend(m.email for m in members if Role(m.role) is role)
    return _unique(found)


def owner_email(members: Iterable[Any]) -> list[str]:
    """The Owner's address (a list with one entry, or empty)."""
    return emails_with_roles(members, Role.OWNER)


def billing_admin_emails(members: Iterable[Any]) -> list[str]:
    """Owner and Billing admins."""
    return emails_with_roles(members, Role.OWNER, Role.BILLING_ADMIN)


def admin_emails(members: Iterable[Any]) -> list[str]:
    """Owner and Admins."""
    return emails_with_roles(members, Role.OWNER, Role.ADMIN)


def resolve(rule: RecipientRule, members: Iterable[Any] = (),
            billing_contacts: Iterable[str] = (), direct: str | None = None) -> list[str]:
    """Addresses for a recipient rule.

    ``billing_contacts`` are added only for the rule that includes them.
    ``direct`` is the single address for ``RecipientRule.DIRECT``.
    """
    if rule is RecipientRule.DIRECT:
        if not direct:
            raise ValidationError("this email needs the recipient's address")
        return _unique([direct])
    addresses = emails_with_roles(members, *_ROLES_BY_RULE[rule])
    if rule is RecipientRule.OWNER_BILLING_ADMINS_CONTACTS:
        addresses = _unique([*addresses, *billing_contacts])
    return addresses


def recipients_for(template_key: str, members: Iterable[Any] = (),
                   billing_contacts: Iterable[str] = (), direct: str | None = None) -> list[str]:
    """Addresses that should get ``template_key`` for an account."""
    return resolve(get_template(template_key).recipients, members, billing_contacts, direct)

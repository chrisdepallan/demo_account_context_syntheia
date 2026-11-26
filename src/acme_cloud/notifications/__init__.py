"""Notifications: email templates, recipient rules and an idempotent outbox.

Owned by the Platform team. ``Outbox.send(template_key, to, **context)`` is
the ``notifier`` other packages are given.
"""

from acme_cloud.notifications.outbox import Outbox, OutboxMessage, idempotency_key
from acme_cloud.notifications.recipients import (
    admin_emails,
    billing_admin_emails,
    owner_email,
    recipients_for,
    resolve,
)
from acme_cloud.notifications.templates import (
    TEMPLATE_KEYS,
    TEMPLATES,
    EmailTemplate,
    RecipientRule,
    RenderedEmail,
    get_template,
    render,
)

__all__ = [
    "EmailTemplate",
    "Outbox",
    "OutboxMessage",
    "RecipientRule",
    "RenderedEmail",
    "TEMPLATES",
    "TEMPLATE_KEYS",
    "admin_emails",
    "billing_admin_emails",
    "get_template",
    "idempotency_key",
    "owner_email",
    "recipients_for",
    "resolve",
]

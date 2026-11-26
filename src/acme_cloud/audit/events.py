"""Audit event names and the ``AuditEvent`` record.

The audit log records exactly these 25 event types:

- Login and credentials: ``login.succeeded``, ``login.failed``,
  ``login.locked``, ``password.reset``, ``mfa.enrolled``, ``mfa.reset``.
- Members and ownership: ``member.invited``, ``member.removed``,
  ``member.role_changed``, ``ownership.transfer_requested``,
  ``ownership.transferred``.
- Account and billing: ``account.closed``, ``account.restored``,
  ``plan.changed``, ``seats.changed``, ``payment_method.updated``,
  ``refund.issued``.
- Security settings: ``sso.enabled``, ``sso.enforced``, ``policy.changed``.
- API keys: ``api_key.created``, ``api_key.rotated``, ``api_key.revoked``.
- Exports: ``export.started``, ``export.downloaded``.

Each event stores the actor, the account, the workspace (if any), the time
in UTC and a small metadata object. Event IDs look like ``evt_3G7H2K9M4P6Q``
(``evt_`` plus 12 characters). Events are immutable: the dataclass is frozen
and its metadata is a read-only mapping (ADR 0008, audit log is append-only).
Metadata must never hold secrets such as passwords, full API keys, MFA codes
or card numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

LOGIN_SUCCEEDED = "login.succeeded"
LOGIN_FAILED = "login.failed"
LOGIN_LOCKED = "login.locked"
PASSWORD_RESET = "password.reset"
MFA_ENROLLED = "mfa.enrolled"
MFA_RESET = "mfa.reset"
MEMBER_INVITED = "member.invited"
MEMBER_REMOVED = "member.removed"
MEMBER_ROLE_CHANGED = "member.role_changed"
OWNERSHIP_TRANSFER_REQUESTED = "ownership.transfer_requested"
OWNERSHIP_TRANSFERRED = "ownership.transferred"
ACCOUNT_CLOSED = "account.closed"
ACCOUNT_RESTORED = "account.restored"
PLAN_CHANGED = "plan.changed"
SEATS_CHANGED = "seats.changed"
PAYMENT_METHOD_UPDATED = "payment_method.updated"
REFUND_ISSUED = "refund.issued"
SSO_ENABLED = "sso.enabled"
SSO_ENFORCED = "sso.enforced"
POLICY_CHANGED = "policy.changed"
API_KEY_CREATED = "api_key.created"
API_KEY_ROTATED = "api_key.rotated"
API_KEY_REVOKED = "api_key.revoked"
EXPORT_STARTED = "export.started"
EXPORT_DOWNLOADED = "export.downloaded"

#: Every event type the audit log accepts, in the order of the facts sheet.
ALL_EVENT_TYPES: tuple[str, ...] = (
    LOGIN_SUCCEEDED, LOGIN_FAILED, LOGIN_LOCKED, PASSWORD_RESET, MFA_ENROLLED, MFA_RESET,
    MEMBER_INVITED, MEMBER_REMOVED, MEMBER_ROLE_CHANGED, OWNERSHIP_TRANSFER_REQUESTED,
    OWNERSHIP_TRANSFERRED, ACCOUNT_CLOSED, ACCOUNT_RESTORED, PLAN_CHANGED, SEATS_CHANGED,
    PAYMENT_METHOD_UPDATED, REFUND_ISSUED, SSO_ENABLED, SSO_ENFORCED, POLICY_CHANGED,
    API_KEY_CREATED, API_KEY_ROTATED, API_KEY_REVOKED, EXPORT_STARTED, EXPORT_DOWNLOADED,
)

#: Columns of the CSV download, in order.
CSV_COLUMNS = ("id", "occurred_at", "event_type", "actor_id", "account_id", "workspace_id",
               "metadata")


def is_known_event(event_type: str) -> bool:
    """True when ``event_type`` is one of the recorded audit events."""
    return event_type in ALL_EVENT_TYPES


@dataclass(frozen=True)
class AuditEvent:
    """One immutable audit log entry."""

    id: str                       # evt_ + 12
    event_type: str
    actor_id: str                 # usr_..., or "system" for automatic actions
    account_id: str
    occurred_at: datetime         # UTC
    workspace_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Copy and wrap so later changes to the caller's dict cannot alter the event.
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_row(self) -> list[str]:
        """Values for one CSV row, in ``CSV_COLUMNS`` order."""
        return [
            self.id, self.occurred_at.isoformat(), self.event_type, self.actor_id,
            self.account_id, self.workspace_id or "",
            json.dumps(dict(self.metadata), sort_keys=True, default=str),
        ]

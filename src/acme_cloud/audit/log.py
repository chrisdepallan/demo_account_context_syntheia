"""Append-only audit log with plan-based retention, filters and CSV export.

Rules implemented here:

- Append-only (ADR 0008): the only way to change the log is ``record``. There
  is no update or delete API, and events are immutable. The one exception is
  ``purge_expired``, which removes events after their retention period ends.
- Each event stores the actor, the account, the workspace (if any), the time
  in UTC and a small metadata object (at most 20 keys).
- Only the event types listed in ``acme_cloud.audit.events`` are accepted.
- Retention depends on the account's plan:

  | Plan       | Audit log retention |
  |------------|---------------------|
  | Free       | None (no audit log) |
  | Starter    | None (no audit log) |
  | Pro        | 90 days             |
  | Business   | 1 year (365 days)   |
  | Enterprise | 7 years (2,555 days)|

- Reading the audit log is a Pro feature: below Pro a query with the plan
  raises ``ERR_PLAN_REQUIRED``. With a plan, a query returns only events
  inside that plan's retention period.
- Filters (release 2026.6): actor, event type and time range. The same
  filters apply to the CSV download.

``AuditLog.record`` matches the ``audit.record(event_type, actor_id,
account_id, workspace_id=None, **metadata)`` shape that other packages call.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any, Mapping

from acme_cloud.accounts.plans import limits_for, require_feature
from acme_cloud.audit.events import CSV_COLUMNS, AuditEvent, is_known_event
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import ValidationError
from acme_cloud.common.ids import IdGenerator

#: "A small metadata object": at most this many keys per event.
MAX_METADATA_KEYS = 20


def retention_days(plan: Plan) -> int:
    """Days an audit event is kept on ``plan``: 0, 0, 90, 365 or 2,555."""
    return limits_for(plan).audit_retention_days


def retention_for(plan: Plan) -> timedelta | None:
    """Retention period of ``plan``; None when the plan has no audit log."""
    days = retention_days(plan)
    return timedelta(days=days) if days else None


class AuditLog:
    """In-memory, append-only audit log."""

    def __init__(self, clock: Clock, ids: IdGenerator) -> None:
        self._clock = clock
        self._ids = ids
        self._events: list[AuditEvent] = []

    def record(self, event_type: str, actor_id: str, account_id: str,
               workspace_id: str | None = None, **metadata: Any) -> AuditEvent:
        """Append one event stamped with the current UTC time and return it."""
        if not is_known_event(event_type):
            raise ValidationError(f"unknown audit event type: {event_type}", event_type=event_type)
        if not actor_id or not account_id:
            raise ValidationError("an audit event needs an actor and an account")
        if len(metadata) > MAX_METADATA_KEYS:
            raise ValidationError(f"audit metadata is limited to {MAX_METADATA_KEYS} keys")
        event = AuditEvent(
            id=self._ids.new("evt"), event_type=event_type, actor_id=actor_id,
            account_id=account_id, occurred_at=self._clock.now(),
            workspace_id=workspace_id, metadata=metadata,
        )
        self._events.append(event)
        return event

    def _cutoff(self, plan: Plan) -> datetime | None:
        """Events before this moment are past the plan's retention."""
        period = retention_for(plan)
        return self._clock.now() - period if period else None

    def query(
        self, account_id: str, actor_id: str | None = None, event_type: str | None = None,
        since: datetime | None = None, until: datetime | None = None, plan: Plan | None = None,
    ) -> list[AuditEvent]:
        """Events of one account, oldest first.

        Optional filters: ``actor_id``, ``event_type`` and the time range
        ``since`` (inclusive) to ``until`` (exclusive). With ``plan`` the
        audit-log feature is checked (Pro and above) and events older than
        the plan's retention are left out.
        """
        cutoff = None
        if plan is not None:
            require_feature(plan, "audit_log")
            cutoff = self._cutoff(plan)
        found = []
        for event in self._events:
            if event.account_id != account_id:
                continue
            if actor_id is not None and event.actor_id != actor_id:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if since is not None and event.occurred_at < since:
                continue
            if until is not None and event.occurred_at >= until:
                continue
            if cutoff is not None and event.occurred_at < cutoff:
                continue
            found.append(event)
        return found

    def purge_expired(self, account_plans: Mapping[str, Plan]) -> int:
        """Remove events past their account's retention; return how many.

        ``account_plans`` maps account ID to its current plan. Events of
        plans with no audit log (Free, Starter) are removed entirely. Events
        of accounts missing from the mapping are kept.
        """
        kept = []
        for event in self._events:
            plan = account_plans.get(event.account_id)
            if plan is not None:
                cutoff = self._cutoff(plan)
                if cutoff is None or event.occurred_at < cutoff:
                    continue
            kept.append(event)
        removed = len(self._events) - len(kept)
        self._events = kept
        return removed

    def export_csv(self, account_id: str, **filters: Any) -> str:
        """CSV download of ``query(account_id, **filters)`` with a header row."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for event in self.query(account_id, **filters):
            writer.writerow(event.to_row())
        return buffer.getvalue()

    def __len__(self) -> int:
        return len(self._events)

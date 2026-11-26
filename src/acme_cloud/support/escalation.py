"""Ticket escalation and the P1 status-page rule.

Business rules:

- A customer escalates by replying **"escalate"** on the ticket. A team
  lead reviews the ticket within **1 business day** (10 business hours,
  Monday to Friday 08:00 to 18:00 US Central Time).
- Business and Enterprise customers can also call the support line to
  escalate.
- **P1** incidents are posted on the status page
  (``https://status.acme-cloud.example``) within **15 minutes**, in
  clock time, at any hour.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from acme_cloud.accounts.plans import has_feature
from acme_cloud.common.clock import add_business_days
from acme_cloud.common.enums import Plan
from acme_cloud.support.models import Priority, Ticket, TicketStatus, from_central, to_central

ESCALATION_KEYWORD = "escalate"
ESCALATION_REVIEW_BUSINESS_DAYS = 1
STATUS_PAGE_POST_MINUTES = 15

_ESCALATE_RE = re.compile(r"\bescalate\b", re.IGNORECASE)


def is_escalation_request(message: str) -> bool:
    """True when a customer reply contains the word "escalate" (any case).

    "Please ESCALATE this" counts; "escalated" or "de-escalation" in
    passing does not.
    """
    return bool(_ESCALATE_RE.search(message))


def escalation_review_due(escalated_at: datetime) -> datetime:
    """When the team lead review is due: 1 business day after ``escalated_at`` (UTC)."""
    local = add_business_days(to_central(escalated_at), ESCALATION_REVIEW_BUSINESS_DAYS)
    return from_central(local)


def can_escalate_by_phone(plan: Plan) -> bool:
    """Business and Enterprise customers can also escalate on the support line."""
    return has_feature(plan, "phone_support")


def escalate_ticket(ticket: Ticket, now: datetime) -> Ticket:
    """Mark ``ticket`` escalated and set the team lead review due time.

    Escalating a ticket that is already escalated keeps the first
    escalation time and due time.
    """
    if ticket.escalated_at is None:
        ticket.escalated_at = now
        ticket.escalation_review_due = escalation_review_due(now)
        ticket.status = TicketStatus.ESCALATED
    return ticket


def is_review_overdue(ticket: Ticket, now: datetime) -> bool:
    """True when an escalated ticket has waited more than 1 business day."""
    return ticket.escalation_review_due is not None and now > ticket.escalation_review_due


def status_page_due(priority: Priority, opened_at: datetime) -> datetime | None:
    """When a P1 must be on the status page (15 minutes); ``None`` for P2 to P4."""
    if priority is not Priority.P1:
        return None
    return opened_at + timedelta(minutes=STATUS_PAGE_POST_MINUTES)


def is_status_post_late(ticket: Ticket, posted_at: datetime | None, now: datetime) -> bool:
    """True when a P1 was posted after 15 minutes, or is still not posted after 15."""
    if ticket.status_page_due is None:
        return False
    return (posted_at or now) > ticket.status_page_due

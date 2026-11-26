"""Support ticket model, priorities, statuses and Central Time helpers.

Business rules:

- Ticket IDs look like ``SUP-58213`` (``SUP-`` plus 5 digits).
- Priorities:
  **P1** service down or data at risk;
  **P2** major feature broken, no workaround;
  **P3** minor issue or workaround exists;
  **P4** question or request.
- Support business hours are Monday to Friday, 08:00 to 18:00 US Central
  Time. A business day is 10 business hours.

Tickets store times in UTC. The business-hours helpers in
``acme_cloud.common.clock`` work on naive Central Time values, so this
module converts between the two. To keep the sample free of time-zone
data it uses a fixed offset of UTC-6 (Central Standard Time) all year.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from acme_cloud.common.enums import Plan

#: Central Standard Time. Daylight saving time is ignored in the sample.
CENTRAL_UTC_OFFSET_HOURS = -6


def to_central(moment: datetime) -> datetime:
    """Convert an aware UTC datetime to a naive Central Time datetime."""
    return (moment.astimezone(timezone.utc)
            + timedelta(hours=CENTRAL_UTC_OFFSET_HOURS)).replace(tzinfo=None)


def from_central(moment: datetime) -> datetime:
    """Convert a naive Central Time datetime to an aware UTC datetime."""
    return (moment - timedelta(hours=CENTRAL_UTC_OFFSET_HOURS)).replace(tzinfo=timezone.utc)


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def description(self) -> str:
        return {
            Priority.P1: "Service down or data at risk",
            Priority.P2: "Major feature broken, no workaround",
            Priority.P3: "Minor issue or workaround exists",
            Priority.P4: "Question or request",
        }[self]


class TicketStatus(str, Enum):
    OPEN = "open"                    # waiting for support
    PENDING = "pending"              # support answered, waiting for the customer
    ESCALATED = "escalated"          # waiting for a team lead review
    SOLVED = "solved"
    CLOSED = "closed"


class Channel(str, Enum):
    HELP_CENTER = "help_center"
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"


@dataclass
class TicketMessage:
    """One message on a ticket. ``body`` is stored after secret screening."""

    author: str            # "customer" or "agent"
    body: str
    sent_at: datetime
    flags: tuple[str, ...] = ()


@dataclass
class Ticket:
    """A support ticket. All times are aware UTC datetimes."""

    id: str
    account_id: str
    requester_email: str
    subject: str
    priority: Priority
    channel: Channel
    plan: Plan
    opened_at: datetime
    first_response_due: datetime
    status: TicketStatus = TicketStatus.OPEN
    first_responded_at: datetime | None = None
    escalated_at: datetime | None = None
    escalation_review_due: datetime | None = None
    #: P1 only: when the incident must be on the status page.
    status_page_due: datetime | None = None
    messages: list[TicketMessage] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.status not in (TicketStatus.SOLVED, TicketStatus.CLOSED)

    @property
    def is_escalated(self) -> bool:
        return self.escalated_at is not None

"""Support service: tickets, first responses, escalation and identity checks.

Business rules:

- A ticket can be opened only on a channel the plan includes (help
  center and email on all plans, chat on Pro and above, phone on
  Business and Enterprise).
- The first-response due time comes from the SLA table in ``sla.py``.
- A customer reply containing "escalate" escalates the ticket; a team
  lead reviews it within 1 business day.
- A P1 ticket must be on the status page within 15 minutes.
- Customer messages are screened; passwords, card numbers and MFA codes
  are removed before the message is stored.
- **Owner change when the Owner is unreachable**: needs written
  confirmation from a company officer; takes up to **5 business days**.
- **MFA reset for the only Admin or Owner**: needs identity
  verification beyond email; takes up to **2 business days**.
  (Other members ask their own Admin, who resets MFA in the dashboard.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from acme_cloud.common.clock import Clock, add_business_days
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import ConflictError, NotFoundError, PermissionDeniedError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.support import conduct, escalation, sla
from acme_cloud.support.channels import require_channel
from acme_cloud.support.models import (
    Channel, Priority, Ticket, TicketMessage, TicketStatus, from_central, to_central,
)

OWNER_CHANGE_BUSINESS_DAYS = 5
MFA_RESET_BUSINESS_DAYS = 2

#: Verification steps, in order. Email alone is never enough.
OWNER_CHANGE_STEPS = ("ticket_from_account_email", "officer_written_confirmation")
MFA_RESET_STEPS = ("ticket_from_account_email", "identity_check_beyond_email")

_KINDS = {
    "owner_change": (OWNER_CHANGE_STEPS, OWNER_CHANGE_BUSINESS_DAYS),
    "mfa_reset": (MFA_RESET_STEPS, MFA_RESET_BUSINESS_DAYS),
}


@dataclass
class VerificationRequest:
    """An identity-verification process attached to a ticket."""

    ticket_id: str
    kind: str                       # "owner_change" or "mfa_reset"
    steps: tuple[str, ...]
    started_at: datetime
    #: Latest completion time: 5 business days (Owner change) or 2 (MFA reset).
    due_at: datetime
    completed_steps: list[str] = field(default_factory=list)
    approved_at: datetime | None = None

    @property
    def remaining_steps(self) -> list[str]:
        return [step for step in self.steps if step not in self.completed_steps]


class SupportService:
    """In-memory ticket desk used by the admin console sample."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None, *,
                 notifier: object | None = None, audit: object | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._notifier = notifier
        self._audit = audit
        self._tickets: dict[str, Ticket] = {}
        self._verifications: dict[str, VerificationRequest] = {}

    def get(self, ticket_id: str) -> Ticket:
        if ticket_id not in self._tickets:
            raise NotFoundError("Ticket not found", ticket_id=ticket_id)
        return self._tickets[ticket_id]

    def _add_message(self, ticket: Ticket, author: str, body: str) -> TicketMessage:
        screened = conduct.screen_message(body)
        message = TicketMessage(author, screened.redacted_text, self._clock.now(), screened.flags)
        ticket.messages.append(message)
        return message

    def open_ticket(self, account_id: str, requester_email: str, subject: str, message: str,
                    priority: Priority, channel: Channel, plan: Plan) -> Ticket:
        """Open a ticket and set its first-response (and P1 status page) due times."""
        require_channel(plan, channel)
        now = self._clock.now()
        ticket = Ticket(
            id=self._ids.new_ticket_id(), account_id=account_id,
            requester_email=requester_email, subject=subject, priority=priority,
            channel=channel, plan=plan, opened_at=now,
            first_response_due=sla.first_response_due(plan, priority, now),
            status_page_due=escalation.status_page_due(priority, now),
        )
        self._add_message(ticket, "customer", message)
        self._tickets[ticket.id] = ticket
        return ticket

    def record_first_response(self, ticket_id: str, message: str) -> bool:
        """Store the agent's first reply; return True when it met the SLA."""
        ticket = self.get(ticket_id)
        if ticket.first_responded_at is not None:
            raise ConflictError("Ticket already has a first response")
        ticket.first_responded_at = self._clock.now()
        if ticket.status is TicketStatus.OPEN:
            ticket.status = TicketStatus.PENDING
        self._add_message(ticket, "agent", message)
        return not sla.is_breached(ticket.first_response_due, self._clock.now(),
                                   ticket.first_responded_at)

    def is_sla_breached(self, ticket_id: str) -> bool:
        ticket = self.get(ticket_id)
        return sla.is_breached(ticket.first_response_due, self._clock.now(),
                               ticket.first_responded_at)

    def customer_reply(self, ticket_id: str, message: str) -> Ticket:
        """Add a customer reply; a reply containing "escalate" escalates the ticket."""
        ticket = self.get(ticket_id)
        self._add_message(ticket, "customer", message)
        if escalation.is_escalation_request(message):
            return self.escalate(ticket_id)
        if ticket.status is TicketStatus.PENDING:
            ticket.status = TicketStatus.OPEN
        return ticket

    def escalate(self, ticket_id: str) -> Ticket:
        """Escalate to a team lead, who reviews within 1 business day."""
        ticket = self.get(ticket_id)
        if not ticket.is_open:
            raise ConflictError("A solved or closed ticket cannot be escalated")
        return escalation.escalate_ticket(ticket, self._clock.now())

    # -- identity verification ------------------------------------------

    def _start_verification(self, ticket_id: str, kind: str) -> VerificationRequest:
        self.get(ticket_id)
        steps, days = _KINDS[kind]
        now = self._clock.now()
        request = VerificationRequest(
            ticket_id=ticket_id, kind=kind, steps=steps, started_at=now,
            due_at=from_central(add_business_days(to_central(now), days)),
        )
        self._verifications[ticket_id] = request
        return request

    def start_owner_change(self, ticket_id: str) -> VerificationRequest:
        """Start the unreachable-Owner process (up to 5 business days)."""
        return self._start_verification(ticket_id, "owner_change")

    def start_mfa_reset(self, ticket_id: str, is_only_admin_or_owner: bool) -> VerificationRequest:
        """Start a support MFA reset (up to 2 business days).

        Only for the only Admin or Owner of an account; anyone else is
        sent to their own Admin.
        """
        if not is_only_admin_or_owner:
            raise PermissionDeniedError(
                "Ask an Admin of your workspace to reset your MFA in Settings -> Members")
        return self._start_verification(ticket_id, "mfa_reset")

    def complete_step(self, ticket_id: str, step: str) -> VerificationRequest:
        """Tick off one verification step."""
        request = self._verifications.get(ticket_id)
        if request is None or step not in request.steps:
            raise NotFoundError("No such verification step", ticket_id=ticket_id, step=step)
        if step not in request.completed_steps:
            request.completed_steps.append(step)
        return request

    def approve_verification(self, ticket_id: str, agent_id: str) -> VerificationRequest:
        """Approve the Owner change or MFA reset once every step is complete.

        Refused (PermissionDeniedError) while a step is missing, so the
        action can never rest on email alone.
        """
        request = self._verifications.get(ticket_id)
        if request is None:
            raise NotFoundError("No verification in progress", ticket_id=ticket_id)
        evidence = ["email" if s == "ticket_from_account_email" else s
                    for s in request.completed_steps]
        conduct.require_verification_beyond_email(request.kind, evidence)
        if request.remaining_steps:
            raise PermissionDeniedError("Identity verification is not complete",
                                        remaining=request.remaining_steps)
        request.approved_at = self._clock.now()
        if self._audit is not None and request.kind == "mfa_reset":
            ticket = self.get(ticket_id)
            self._audit.record("mfa.reset", agent_id, ticket.account_id, None,
                               ticket_id=ticket_id, via="support")
        return request

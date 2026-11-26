"""Customer support: tickets, channels, first-response SLA, escalation and conduct rules.

Owned by the Support Tools team. Business hours are Monday to Friday,
08:00 to 18:00 US Central Time; a business day is 10 business hours.
The SLA table and every other number come from
``docs/reference/constants-and-glossary.md``.
"""

from acme_cloud.support.channels import channels_for, is_live_chat_open, require_channel
from acme_cloud.support.conduct import SUPPORT_MUST_NEVER, ScreenResult, screen_message
from acme_cloud.support.escalation import (
    escalation_review_due, is_escalation_request, status_page_due,
)
from acme_cloud.support.models import Channel, Priority, Ticket, TicketStatus
from acme_cloud.support.service import SupportService, VerificationRequest
from acme_cloud.support.sla import (
    FIRST_RESPONSE_TARGETS, SlaTarget, SlaUnit, first_response_due, first_response_target,
    is_breached,
)

__all__ = [
    "Channel", "FIRST_RESPONSE_TARGETS", "Priority", "SUPPORT_MUST_NEVER", "ScreenResult",
    "SlaTarget", "SlaUnit", "SupportService", "Ticket", "TicketStatus",
    "VerificationRequest", "channels_for", "escalation_review_due", "first_response_due",
    "first_response_target", "is_breached", "is_escalation_request", "is_live_chat_open",
    "require_channel", "screen_message", "status_page_due",
]

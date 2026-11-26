"""Ticket model: SUP IDs, priorities P1 to P4, statuses and Central Time conversion."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from acme_cloud.common.enums import Plan
from acme_cloud.common.ids import is_valid_id
from acme_cloud.support.models import (
    CENTRAL_UTC_OFFSET_HOURS, Channel, Priority, Ticket, TicketStatus, from_central, to_central,
)


def make_ticket(ids, **overrides) -> Ticket:
    opened = datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc)
    values = dict(
        id=ids.new_ticket_id(), account_id="acc_TEST0001", requester_email="dana@example.com",
        subject="Cannot upload files", priority=Priority.P3, channel=Channel.EMAIL,
        plan=Plan.PRO, opened_at=opened, first_response_due=opened,
    )
    values.update(overrides)
    return Ticket(**values)


def test_ticket_ids_are_sup_plus_5_digits(ids):
    ticket = make_ticket(ids)
    assert ticket.id == "SUP-10001"
    assert is_valid_id(ticket.id, "ticket")
    assert make_ticket(ids).id == "SUP-10002"


@pytest.mark.parametrize("priority, description", [
    (Priority.P1, "Service down or data at risk"),
    (Priority.P2, "Major feature broken, no workaround"),
    (Priority.P3, "Minor issue or workaround exists"),
    (Priority.P4, "Question or request"),
])
def test_priority_definitions(priority, description):
    assert priority.description == description
    assert priority.value == priority.name


def test_there_are_four_priorities_and_four_channels():
    assert [p.value for p in Priority] == ["P1", "P2", "P3", "P4"]
    assert [c.value for c in Channel] == ["help_center", "email", "chat", "phone"]


def test_new_ticket_is_open_and_not_escalated(ids):
    ticket = make_ticket(ids)
    assert ticket.status is TicketStatus.OPEN
    assert ticket.is_open and not ticket.is_escalated
    assert ticket.first_responded_at is None and ticket.status_page_due is None
    assert ticket.messages == []


@pytest.mark.parametrize("status, is_open", [
    (TicketStatus.OPEN, True), (TicketStatus.PENDING, True), (TicketStatus.ESCALATED, True),
    (TicketStatus.SOLVED, False), (TicketStatus.CLOSED, False),
])
def test_solved_and_closed_tickets_are_not_open(ids, status, is_open):
    assert make_ticket(ids, status=status).is_open is is_open


def test_central_time_is_utc_minus_6_in_the_sample():
    assert CENTRAL_UTC_OFFSET_HOURS == -6
    utc = datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)
    local = to_central(utc)
    assert local == datetime(2026, 1, 5, 8, 0) and local.tzinfo is None  # 08:00 Central
    assert from_central(local) == utc


def test_conversion_crosses_midnight_correctly():
    utc = datetime(2026, 1, 10, 2, 30, tzinfo=timezone.utc)   # Saturday in UTC
    assert to_central(utc) == datetime(2026, 1, 9, 20, 30)     # still Friday evening in Central

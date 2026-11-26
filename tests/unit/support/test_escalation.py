"""Escalation: "escalate" reply -> team lead review in 1 business day; P1 status page in 15 minutes."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.common.enums import Plan
from acme_cloud.support import escalation
from acme_cloud.support.escalation import (
    can_escalate_by_phone, escalate_ticket, escalation_review_due, is_escalation_request,
    is_review_overdue, is_status_post_late, status_page_due,
)
from acme_cloud.support.models import Channel, Priority, Ticket, TicketStatus


def make_ticket(opened_at, priority=Priority.P2) -> Ticket:
    return Ticket(
        id="SUP-10001", account_id="acc_TEST0001", requester_email="dana@example.com",
        subject="Exports fail", priority=priority, channel=Channel.EMAIL, plan=Plan.PRO,
        opened_at=opened_at, first_response_due=opened_at + timedelta(hours=8),
        status_page_due=status_page_due(priority, opened_at),
    )


def test_constants_match_the_facts_sheet():
    assert escalation.ESCALATION_KEYWORD == "escalate"
    assert escalation.ESCALATION_REVIEW_BUSINESS_DAYS == 1
    assert escalation.STATUS_PAGE_POST_MINUTES == 15


@pytest.mark.parametrize("message, expected", [
    ("escalate", True),
    ("Escalate", True),
    ("Please ESCALATE this, we have waited two days.", True),
    ("escalate.", True),
    ("Thanks, that fixed it.", False),
    ("Has this been escalated?", False),
    ("No need for escalation.", False),
    ("", False),
])
def test_a_reply_containing_the_word_escalate_is_an_escalation_request(message, expected):
    assert is_escalation_request(message) is expected


@pytest.mark.parametrize("escalated, due", [
    ((5, 9, 0), (6, 9, 0)),      # Monday 09:00 -> Tuesday 09:00
    ((9, 17, 0), (12, 17, 0)),   # Friday 17:00 -> Monday 17:00
    ((10, 12, 0), (12, 18, 0)),  # Saturday -> counted from Monday 08:00, due Monday 18:00
    ((8, 20, 0), (9, 18, 0)),    # Thursday evening -> Friday 18:00
])
def test_team_lead_review_is_due_within_1_business_day(at_central, escalated, due):
    assert escalation_review_due(at_central(*escalated)) == at_central(*due)


def test_escalating_sets_status_time_and_review_due(at_central):
    ticket = make_ticket(at_central(5, 9))
    now = at_central(5, 14)
    escalate_ticket(ticket, now)
    assert ticket.status is TicketStatus.ESCALATED
    assert ticket.is_escalated and ticket.escalated_at == now
    assert ticket.escalation_review_due == at_central(6, 14)


def test_escalating_twice_keeps_the_first_due_time(at_central):
    ticket = make_ticket(at_central(5, 9))
    escalate_ticket(ticket, at_central(5, 14))
    escalate_ticket(ticket, at_central(5, 16))
    assert ticket.escalated_at == at_central(5, 14)
    assert ticket.escalation_review_due == at_central(6, 14)


def test_review_is_overdue_after_the_due_time(at_central):
    ticket = make_ticket(at_central(5, 9))
    assert not is_review_overdue(ticket, at_central(8, 9))  # not escalated at all
    escalate_ticket(ticket, at_central(5, 14))
    assert not is_review_overdue(ticket, at_central(6, 14))
    assert is_review_overdue(ticket, at_central(6, 14, 1))


@pytest.mark.parametrize("plan, by_phone", [
    (Plan.FREE, False), (Plan.STARTER, False), (Plan.PRO, False),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_business_and_enterprise_can_also_escalate_by_phone(plan, by_phone):
    assert can_escalate_by_phone(plan) is by_phone


def test_p1_must_be_on_the_status_page_within_15_minutes_at_any_hour(at_central):
    saturday_night = at_central(10, 23, 50)
    assert status_page_due(Priority.P1, saturday_night) == saturday_night + timedelta(minutes=15)


@pytest.mark.parametrize("priority", [Priority.P2, Priority.P3, Priority.P4])
def test_only_p1_has_a_status_page_deadline(at_central, priority):
    assert status_page_due(priority, at_central(5, 9)) is None
    assert not is_status_post_late(make_ticket(at_central(5, 9), priority), None, at_central(9, 9))


@pytest.mark.parametrize("posted_after_minutes, late", [(14, False), (15, False), (16, True)])
def test_status_page_post_is_late_after_15_minutes(at_central, posted_after_minutes, late):
    opened = at_central(5, 9)
    ticket = make_ticket(opened, Priority.P1)
    posted = opened + timedelta(minutes=posted_after_minutes)
    assert is_status_post_late(ticket, posted, now=opened + timedelta(hours=1)) is late


def test_unposted_p1_is_late_once_15_minutes_have_passed(at_central):
    opened = at_central(5, 9)
    ticket = make_ticket(opened, Priority.P1)
    assert not is_status_post_late(ticket, None, now=opened + timedelta(minutes=15))
    assert is_status_post_late(ticket, None, now=opened + timedelta(minutes=15, seconds=1))

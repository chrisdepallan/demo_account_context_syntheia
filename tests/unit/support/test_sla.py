"""First-response SLA table and due-time calculation in business hours."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.common.enums import Plan
from acme_cloud.support.models import Priority
from acme_cloud.support.sla import (
    FIRST_RESPONSE_TARGETS, SlaUnit, first_response_due, first_response_target, is_breached,
    time_remaining,
)

P1, P2, P3, P4 = Priority.P1, Priority.P2, Priority.P3, Priority.P4

#: The table from docs/reference/constants-and-glossary.md, cell by cell.
SLA_TABLE = [
    (P1, Plan.FREE, "3 business days"), (P1, Plan.STARTER, "2 business days"),
    (P1, Plan.PRO, "4 business hours"), (P1, Plan.BUSINESS, "1 business hour"),
    (P1, Plan.ENTERPRISE, "30 minutes, 24/7"),
    (P2, Plan.FREE, "3 business days"), (P2, Plan.STARTER, "2 business days"),
    (P2, Plan.PRO, "8 business hours"), (P2, Plan.BUSINESS, "4 business hours"),
    (P2, Plan.ENTERPRISE, "2 hours, 24/7"),
    (P3, Plan.FREE, "3 business days"), (P3, Plan.STARTER, "2 business days"),
    (P3, Plan.PRO, "2 business days"), (P3, Plan.BUSINESS, "1 business day"),
    (P3, Plan.ENTERPRISE, "1 business day"),
    (P4, Plan.FREE, "3 business days"), (P4, Plan.STARTER, "3 business days"),
    (P4, Plan.PRO, "3 business days"), (P4, Plan.BUSINESS, "3 business days"),
    (P4, Plan.ENTERPRISE, "3 business days"),
]


@pytest.mark.parametrize("priority, plan, text", SLA_TABLE)
def test_first_response_target_table(priority, plan, text):
    assert first_response_target(plan, priority).describe() == text


def test_the_table_covers_every_priority_and_plan():
    assert len(SLA_TABLE) == 20
    assert all(set(row) == set(Plan) for row in FIRST_RESPONSE_TARGETS.values())
    assert set(FIRST_RESPONSE_TARGETS) == set(Priority)


def test_only_enterprise_p1_and_p2_are_counted_24x7():
    clock_time = {(priority, plan) for priority, row in FIRST_RESPONSE_TARGETS.items()
                  for plan, target in row.items() if target.unit is SlaUnit.CLOCK_MINUTES}
    assert clock_time == {(P1, Plan.ENTERPRISE), (P2, Plan.ENTERPRISE)}


# Tickets opened on Friday 2026-01-09 at 17:00 Central, one business hour before closing.
@pytest.mark.parametrize("plan, priority, due_day, due_hour, due_minute", [
    (Plan.PRO, P1, 12, 11, 0),         # 4 business hours: 1 on Friday + 3 on Monday
    (Plan.PRO, P2, 12, 15, 0),         # 8 business hours: 1 + 7
    (Plan.BUSINESS, P1, 9, 18, 0),     # 1 business hour: Friday 18:00
    (Plan.BUSINESS, P2, 12, 11, 0),    # 4 business hours
    (Plan.BUSINESS, P3, 12, 17, 0),    # 1 business day = 10 business hours
    (Plan.STARTER, P1, 13, 17, 0),     # 2 business days: Tuesday 17:00
    (Plan.FREE, P4, 14, 17, 0),        # 3 business days: Wednesday 17:00
    (Plan.ENTERPRISE, P1, 9, 17, 30),  # 30 minutes of clock time
    (Plan.ENTERPRISE, P2, 9, 19, 0),   # 2 hours of clock time, past closing
    (Plan.ENTERPRISE, P3, 12, 17, 0),  # P3 is business time even on Enterprise
])
def test_ticket_opened_friday_1700_central(at_central, plan, priority, due_day, due_hour,
                                           due_minute):
    due = first_response_due(plan, priority, at_central(9, 17))
    assert due == at_central(due_day, due_hour, due_minute)


@pytest.mark.parametrize("plan, priority, due_day, due_hour, due_minute", [
    (Plan.ENTERPRISE, P1, 10, 3, 30),   # 24/7: answered in the night
    (Plan.ENTERPRISE, P2, 10, 5, 0),
    (Plan.BUSINESS, P1, 12, 9, 0),      # clock starts Monday 08:00
    (Plan.PRO, P1, 12, 12, 0),
    (Plan.PRO, P3, 13, 18, 0),          # 2 business days: Monday and Tuesday
])
def test_ticket_opened_saturday_0300_central(at_central, plan, priority, due_day, due_hour,
                                             due_minute):
    due = first_response_due(plan, priority, at_central(10, 3))
    assert due == at_central(due_day, due_hour, due_minute)


def test_ticket_opened_inside_business_hours_counts_from_that_moment(at_central):
    opened = at_central(5, 9, 15)  # Monday 09:15
    assert first_response_due(Plan.PRO, P1, opened) == at_central(5, 13, 15)
    assert first_response_due(Plan.BUSINESS, P1, opened) == at_central(5, 10, 15)
    assert first_response_due(Plan.STARTER, P3, opened) == at_central(7, 9, 15)


def test_due_time_is_an_aware_utc_datetime(at_central):
    due = first_response_due(Plan.PRO, P1, at_central(5, 9))
    assert due.utcoffset() == timedelta(0)


def test_response_at_the_due_time_is_on_time_and_one_minute_later_is_a_breach(at_central):
    due = at_central(5, 13)
    now = at_central(6, 9)
    assert not is_breached(due, now, responded_at=due)
    assert not is_breached(due, now, responded_at=due - timedelta(minutes=1))
    assert is_breached(due, now, responded_at=due + timedelta(minutes=1))


def test_unanswered_ticket_is_breached_once_the_due_time_has_passed(at_central):
    due = at_central(5, 13)
    assert not is_breached(due, now=due)
    assert is_breached(due, now=due + timedelta(seconds=1))
    assert time_remaining(due, due - timedelta(minutes=20)) == timedelta(minutes=20)
    assert time_remaining(due, due + timedelta(minutes=5)) < timedelta(0)

"""Dunning: day 0 past_due, retries on days 1/3/7/14, read_only day 14, Free day 44."""

from __future__ import annotations

import pytest

from acme_cloud.billing.dunning import (
    DOWNGRADE_DAY,
    DUNNING_RETRY_DAYS,
    READ_ONLY_DAY,
    RESTORE_ACCESS_WITHIN_MINUTES,
    DunningAction,
    DunningProcess,
    DunningSchedule,
)
from acme_cloud.billing.models import ChargeOutcome
from acme_cloud.common.enums import AccountState, Plan
from acme_cloud.common.errors import ConflictError

DECLINED, SUCCEEDED, DOWN = (
    ChargeOutcome.DECLINED, ChargeOutcome.SUCCEEDED, ChargeOutcome.UNAVAILABLE)


@pytest.fixture
def process(clock):
    return DunningProcess(clock.now())


def decline_through(process, last_day):
    """Decline every retry up to and including ``last_day``."""
    for day in [d for d in DUNNING_RETRY_DAYS if d <= last_day]:
        assert process.due(day).retry
        process.record_retry(day, DECLINED)


def test_constants_match_the_dunning_timeline():
    assert DUNNING_RETRY_DAYS == (1, 3, 7, 14)
    assert (READ_ONLY_DAY, DOWNGRADE_DAY, RESTORE_ACCESS_WITHIN_MINUTES) == (14, 44, 5)


def test_day_0_sets_past_due_and_sends_payment_failed(process):
    action = process.start()
    assert (action.day, action.new_state) == (0, AccountState.PAST_DUE)
    assert action.emails == ("payment_failed",)
    assert process.failed_attempts == 1 and not process.finished


@pytest.mark.parametrize(
    "day, state",
    [
        (0, AccountState.PAST_DUE),
        (13, AccountState.PAST_DUE),
        (14, AccountState.READ_ONLY),
        (43, AccountState.READ_ONLY),
        (44, AccountState.ACTIVE),   # downgraded to Free
    ],
)
def test_schedule_state_by_day_when_every_retry_fails(day, state):
    assert DunningSchedule().expected_state(day) is state


@pytest.mark.parametrize("day, is_retry", [(0, False), (1, True), (2, False), (3, True),
                                           (7, True), (13, False), (14, True), (15, False)])
def test_retries_are_due_only_on_days_1_3_7_and_14(process, day, is_retry):
    decline_through(process, day - 1)
    assert process.due(day).retry is is_retry
    assert DunningSchedule().is_retry_day(day) is is_retry


def test_next_retry_day():
    schedule = DunningSchedule()
    assert [schedule.next_retry_day(d) for d in (0, 1, 3, 7, 14)] == [1, 3, 7, 14, None]


def test_a_failed_retry_before_day_14_keeps_past_due_and_emails_again(process):
    action = process.record_retry(7, DECLINED)
    assert action.new_state is None and action.counted_as_failure
    assert action.emails == ("payment_failed",)
    assert process.state is AccountState.PAST_DUE


def test_day_13_is_still_past_due_and_day_14_failure_sets_read_only(process):
    decline_through(process, 7)
    assert process.due(13).retry is False and process.state is AccountState.PAST_DUE
    action = process.record_retry(14, DECLINED)
    assert action.new_state is AccountState.READ_ONLY
    assert action.emails == ("payment_failed", "account_read_only")
    assert process.failed_attempts == 5  # the first charge plus four retries


def test_day_44_downgrades_to_free_and_the_account_is_active_again(process):
    decline_through(process, 14)
    assert process.due(43) == DunningAction(day=43)  # nothing to do on day 43
    action = process.due(44)
    assert (action.new_plan, action.new_state) == (Plan.FREE, AccountState.ACTIVE)
    assert action.emails == ("account_downgraded",) and action.finished
    with pytest.raises(ConflictError):
        process.due(45)


def test_successful_retry_makes_the_account_active_and_ends_dunning(process):
    process.record_retry(1, DECLINED)
    action = process.record_retry(3, SUCCEEDED)
    assert action.new_state is AccountState.ACTIVE and action.finished
    assert action.emails == () and not action.counted_as_failure
    assert process.failed_attempts == 2


def test_paying_the_balance_from_read_only_restores_active(process):
    decline_through(process, 14)
    assert process.state is AccountState.READ_ONLY
    action = process.payment_cleared(day=20)
    assert action.new_state is AccountState.ACTIVE and process.finished


def test_processor_outage_is_not_counted_as_a_failure(process):
    """INC-2026-002: an outage sends no email, changes no state, and the retry stays due."""
    action = process.record_retry(1, DOWN)
    assert not action.counted_as_failure and action.emails == () and action.new_state is None
    assert action.retry is True
    assert (process.failed_attempts, process.outages) == (1, 1)
    assert process.due(2).retry is True          # made again on the next run
    process.record_retry(2, DECLINED)
    assert process.failed_attempts == 2 and process.due(2).retry is False


def test_outage_on_day_14_does_not_set_read_only(process):
    decline_through(process, 7)
    process.record_retry(14, DOWN)
    assert process.state is AccountState.PAST_DUE
    action = process.record_retry(15, DECLINED)   # the processor is back and declines
    assert action.new_state is AccountState.READ_ONLY


def test_downgrade_waits_for_a_real_answer_to_the_pending_retry(process):
    decline_through(process, 7)
    process.record_retry(14, DOWN)
    action = process.due(44)
    assert action.retry is True and action.new_plan is None
    process.record_retry(44, DECLINED)
    assert process.due(44).new_plan is Plan.FREE


def test_day_number_counts_whole_days_since_the_first_failure(process, clock):
    clock.advance(hours=23)
    assert process.day_number(clock.now()) == 0
    clock.advance(hours=1)
    assert process.day_number(clock.now()) == 1
    clock.advance(days=13)
    assert process.day_number(clock.now()) == 14

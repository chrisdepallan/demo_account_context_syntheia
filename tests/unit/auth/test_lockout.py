"""Lockout: 5 failures in 15 minutes -> 15 minutes; 10 in 1 hour -> 1 hour plus email."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.auth import lockout
from acme_cloud.auth.lockout import LockoutTracker
from acme_cloud.common.errors import LockedOutError

USER = "usr_TEST0001"
EMAIL = "dana@example.com"


def fail(tracker: LockoutTracker, times: int) -> None:
    for _ in range(times):
        tracker.record_failure(USER, EMAIL, "acc_TEST0001")


def reach_ten_failures_in_one_hour(tracker: LockoutTracker, clock) -> None:
    """5 failures (short lock), 4 more after it ends, then the tenth."""
    fail(tracker, 5)
    clock.advance(minutes=16)
    fail(tracker, 4)
    clock.advance(minutes=16)
    fail(tracker, 1)


def test_constants_match_the_facts_sheet():
    assert lockout.SHORT_LOCK_THRESHOLD == 5
    assert lockout.SHORT_LOCK_WINDOW == timedelta(minutes=15)
    assert lockout.SHORT_LOCK_DURATION == timedelta(minutes=15)
    assert lockout.LONG_LOCK_THRESHOLD == 10
    assert lockout.LONG_LOCK_WINDOW == timedelta(hours=1)
    assert lockout.LONG_LOCK_DURATION == timedelta(hours=1)


def test_four_failures_do_not_lock(clock):
    tracker = LockoutTracker(clock)
    fail(tracker, 4)
    assert not tracker.is_locked(USER)
    tracker.check(USER)  # does not raise


def test_fifth_failure_within_15_minutes_locks_for_15_minutes(clock):
    tracker = LockoutTracker(clock)
    fail(tracker, 4)
    clock.advance(minutes=14)
    until = tracker.record_failure(USER, EMAIL)
    assert until == clock.now() + timedelta(minutes=15)
    with pytest.raises(LockedOutError) as error:
        tracker.check(USER)
    assert error.value.code == "ERR_LOCKED_OUT"
    assert error.value.http_status == 423
    assert error.value.details["retry_after"] == 15 * 60


def test_five_failures_spread_over_more_than_15_minutes_do_not_lock(clock):
    tracker = LockoutTracker(clock)
    fail(tracker, 4)
    clock.advance(minutes=15, seconds=1)
    assert tracker.record_failure(USER, EMAIL) is None
    assert not tracker.is_locked(USER)


@pytest.mark.parametrize("minutes, locked", [(14, True), (15, False), (16, False)])
def test_short_lock_ends_after_15_minutes(clock, minutes, locked):
    tracker = LockoutTracker(clock)
    fail(tracker, 5)
    clock.advance(minutes=minutes)
    assert tracker.is_locked(USER) is locked


def test_short_lock_does_not_email_the_user(clock, notifier):
    tracker = LockoutTracker(clock, notifier)
    fail(tracker, 5)
    assert notifier.sent == []


def test_ten_failures_within_1_hour_lock_for_1_hour_and_email_the_user(clock, notifier):
    tracker = LockoutTracker(clock, notifier)
    reach_ten_failures_in_one_hour(tracker, clock)
    assert tracker.locked_until(USER) == clock.now() + timedelta(hours=1)
    assert notifier.templates() == ["login_locked"]
    assert notifier.sent[0][1] == [EMAIL]


@pytest.mark.parametrize("minutes, locked", [(59, True), (61, False)])
def test_long_lock_ends_after_1_hour(clock, minutes, locked):
    tracker = LockoutTracker(clock)
    reach_ten_failures_in_one_hour(tracker, clock)
    clock.advance(minutes=minutes)
    assert tracker.is_locked(USER) is locked


def test_ten_failures_spread_over_more_than_1_hour_give_only_the_short_lock(clock, notifier):
    tracker = LockoutTracker(clock, notifier)
    fail(tracker, 5)
    clock.advance(minutes=61)
    fail(tracker, 5)
    assert tracker.locked_until(USER) == clock.now() + timedelta(minutes=15)
    assert notifier.sent == []


def test_password_reset_unlocks_at_once_and_clears_the_counters(clock):
    tracker = LockoutTracker(clock)
    fail(tracker, 5)
    tracker.reset(USER)
    assert not tracker.is_locked(USER)
    assert tracker.failures_within(USER, timedelta(hours=1)) == 0


def test_each_lock_writes_a_login_locked_audit_event(clock, audit):
    tracker = LockoutTracker(clock, audit=audit)
    fail(tracker, 5)
    assert audit.types() == ["login.locked"]
    event_type, actor, account, _, metadata = audit.events[0]
    assert (actor, account, metadata["lock_minutes"]) == (USER, "acc_TEST0001", 15)


def test_lockout_is_per_user(clock):
    tracker = LockoutTracker(clock)
    fail(tracker, 5)
    assert not tracker.is_locked("usr_TEST0002")

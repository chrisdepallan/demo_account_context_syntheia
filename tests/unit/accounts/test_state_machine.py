"""Account lifecycle: allowed transitions, close, restore (30 days), delete (day 31)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.accounts import state_machine as sm
from acme_cloud.common.enums import AccountState as S
from acme_cloud.common.errors import AccountReadOnlyError, ConflictError

ALLOWED = [
    (S.TRIALING, S.ACTIVE),     # first charge succeeds, or trial ends -> Free
    (S.ACTIVE, S.PAST_DUE),     # a charge fails (day 0)
    (S.PAST_DUE, S.ACTIVE),     # balance paid
    (S.PAST_DUE, S.READ_ONLY),  # day 14
    (S.READ_ONLY, S.ACTIVE),    # balance paid, or day-44 downgrade to Free
    (S.TRIALING, S.CLOSED), (S.ACTIVE, S.CLOSED), (S.PAST_DUE, S.CLOSED),
    (S.READ_ONLY, S.CLOSED),    # the Owner closes the account
    (S.CLOSED, S.DELETED),      # day 31
]


@pytest.mark.parametrize(("current", "new"), ALLOWED)
def test_allowed_transitions(current, new):
    assert sm.can_transition(current, new)


def test_no_other_transition_is_allowed():
    for current in S:
        for new in S:
            if (current, new) not in ALLOWED:
                assert not sm.can_transition(current, new), (current, new)


def test_nothing_leaves_deleted():
    assert sm.ALLOWED_TRANSITIONS[S.DELETED] == frozenset()
    assert not sm.can_transition(S.DELETED, S.CLOSED)


@pytest.mark.parametrize("previous", [S.TRIALING, S.ACTIVE, S.PAST_DUE, S.READ_ONLY])
def test_closed_can_only_return_to_its_previous_state(previous):
    for target in (S.TRIALING, S.ACTIVE, S.PAST_DUE, S.READ_ONLY):
        assert sm.can_transition(S.CLOSED, target, previous) is (target is previous)


def test_transition_changes_state_and_timestamp(make_account, clock):
    account = make_account(state=S.ACTIVE)
    clock.advance(days=2)
    sm.transition(account, S.PAST_DUE, clock)
    assert account.state is S.PAST_DUE
    assert account.state_changed_at == clock.now()


def test_disallowed_transition_raises_conflict(make_account, clock):
    account = make_account(state=S.TRIALING)
    with pytest.raises(ConflictError) as caught:
        sm.transition(account, S.READ_ONLY, clock)
    assert caught.value.code == "ERR_CONFLICT"
    assert account.state is S.TRIALING


@pytest.mark.parametrize("state", [S.TRIALING, S.ACTIVE, S.PAST_DUE, S.READ_ONLY])
def test_close_remembers_when_and_from_which_state(make_account, clock, state):
    account = make_account(state=state)
    sm.close(account, clock)
    assert account.state is S.CLOSED
    assert account.closed_at == clock.now()
    assert account.state_before_close is state


@pytest.mark.parametrize("state", [S.CLOSED, S.DELETED])
def test_closed_and_deleted_accounts_cannot_be_closed(make_account, clock, state):
    account = make_account(state=state)
    with pytest.raises(ConflictError):
        sm.close(account, clock)


def test_restore_on_day_30_returns_to_the_previous_state(make_account, clock):
    account = make_account(state=S.PAST_DUE)
    sm.close(account, clock)
    clock.advance(days=30, hours=23)   # still day 30
    assert sm.can_restore(account, clock.now())
    sm.restore(account, clock)
    assert account.state is S.PAST_DUE
    assert account.closed_at is None
    assert account.state_before_close is None


def test_restore_on_day_31_is_too_late(make_account, clock):
    account = make_account(state=S.ACTIVE)
    sm.close(account, clock)
    clock.advance(days=31)
    assert not sm.can_restore(account, clock.now())
    with pytest.raises(ConflictError):
        sm.restore(account, clock)
    assert account.state is S.CLOSED


def test_only_a_closed_account_can_be_restored(make_account, clock):
    with pytest.raises(ConflictError):
        sm.restore(make_account(state=S.ACTIVE), clock)


def test_restore_deadline_is_the_start_of_day_31(make_account, clock):
    account = make_account()
    sm.close(account, clock)
    assert sm.restore_deadline(account) == account.closed_at + timedelta(days=31)
    assert sm.RESTORE_WINDOW_DAYS == 30
    assert sm.DELETE_ON_DAY == 31


@pytest.mark.parametrize(("days", "deleted"), [(1, False), (30, False), (31, True), (45, True)])
def test_closed_account_is_deleted_on_day_31(make_account, clock, days, deleted):
    account = make_account()
    sm.close(account, clock)
    clock.advance(days=days)
    assert sm.delete_if_due(account, clock) is deleted
    assert account.state is (S.DELETED if deleted else S.CLOSED)


def test_deletion_cannot_be_forced_before_day_31(make_account, clock):
    account = make_account()
    sm.close(account, clock)
    clock.advance(days=30)
    with pytest.raises(ConflictError):
        sm.transition(account, S.DELETED, clock)


def test_deleted_account_cannot_be_restored(make_account, clock):
    """Deletion cannot be undone."""
    account = make_account()
    sm.close(account, clock)
    clock.advance(days=31)
    sm.delete_if_due(account, clock)
    with pytest.raises(ConflictError):
        sm.restore(account, clock)
    with pytest.raises(ConflictError):
        sm.transition(account, S.ACTIVE, clock)


@pytest.mark.parametrize("state", [S.TRIALING, S.ACTIVE, S.PAST_DUE])
def test_editable_states(make_account, state):
    sm.require_editable(make_account(state=state))  # no error


@pytest.mark.parametrize("state", [S.READ_ONLY, S.CLOSED, S.DELETED])
def test_read_only_closed_and_deleted_cannot_be_edited(make_account, state):
    with pytest.raises(AccountReadOnlyError) as caught:
        sm.require_editable(make_account(state=state))
    assert caught.value.code == "ERR_ACCOUNT_READ_ONLY"
    assert caught.value.http_status == 423

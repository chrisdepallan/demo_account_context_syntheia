"""Account lifecycle state machine.

States: ``trialing``, ``active``, ``past_due``, ``read_only``, ``closed``,
``deleted``. Allowed transitions:

- ``trialing`` -> ``active``: the first charge succeeds, or the 14-day trial
  ends with no payment method (the account moves to Free and is active).
- ``active`` -> ``past_due``: a renewal or seat charge fails (dunning day 0).
- ``past_due`` -> ``active``: the balance is paid (access back within 5 minutes).
- ``past_due`` -> ``read_only``: day 14 after the first failed charge.
- ``read_only`` -> ``active``: the balance is paid, or the day-44 downgrade to Free.
- any state except ``deleted`` -> ``closed``: the Owner closes the account.
- ``closed`` -> the previous state: the Owner restores within 30 days.
- ``closed`` -> ``deleted``: day 31 after closure. This cannot be undone.

Nothing leaves ``deleted``. Content can be edited only in ``trialing``,
``active`` and ``past_due``; in ``read_only``, ``closed`` and ``deleted``
every write fails with ``ERR_ACCOUNT_READ_ONLY`` (HTTP 423).

Days are counted in whole days since the moment of closure: the account can
be restored through the whole of day 30 and is deleted from day 31 on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from acme_cloud.accounts.models import Account
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import AccountState
from acme_cloud.common.errors import AccountReadOnlyError, ConflictError

#: A closed account can be restored for this many days.
RESTORE_WINDOW_DAYS = 30
#: A closed account becomes ``deleted`` on this day after closure.
DELETE_ON_DAY = 31

_S = AccountState

#: State -> states it may move to. Restoring a closed account to its previous
#: state is handled separately because the target depends on the account.
ALLOWED_TRANSITIONS: dict[AccountState, frozenset[AccountState]] = {
    _S.TRIALING: frozenset({_S.ACTIVE, _S.CLOSED}),
    _S.ACTIVE: frozenset({_S.PAST_DUE, _S.CLOSED}),
    _S.PAST_DUE: frozenset({_S.ACTIVE, _S.READ_ONLY, _S.CLOSED}),
    _S.READ_ONLY: frozenset({_S.ACTIVE, _S.CLOSED}),
    _S.CLOSED: frozenset({_S.DELETED}),
    _S.DELETED: frozenset(),
}


def can_transition(
    current: AccountState,
    new: AccountState,
    state_before_close: AccountState | None = None,
) -> bool:
    """True when an account may move from ``current`` to ``new``.

    From ``closed`` the only targets are ``deleted`` and the state the account
    had before it was closed (``state_before_close``).
    """
    if new in ALLOWED_TRANSITIONS[current]:
        return True
    return current is _S.CLOSED and state_before_close is not None and new is state_before_close


def days_since_closure(account: Account, now: datetime) -> int:
    """Whole days since the account was closed. Raises ConflictError if it is not closed."""
    if account.closed_at is None:
        raise ConflictError(f"account {account.id} is not closed", state=account.state.value)
    return (now - account.closed_at).days


def restore_deadline(account: Account) -> datetime:
    """Last moment (exclusive) at which a closed account can still be restored."""
    if account.closed_at is None:
        raise ConflictError(f"account {account.id} is not closed", state=account.state.value)
    return account.closed_at + timedelta(days=DELETE_ON_DAY)


def can_restore(account: Account, now: datetime) -> bool:
    """True while a closed account is inside the 30-day restore window."""
    return account.state is _S.CLOSED and days_since_closure(account, now) <= RESTORE_WINDOW_DAYS


def is_due_for_deletion(account: Account, now: datetime) -> bool:
    """True when a closed account has reached day 31 and must become ``deleted``."""
    return account.state is _S.CLOSED and days_since_closure(account, now) >= DELETE_ON_DAY


def transition(account: Account, new_state: AccountState, clock: Clock) -> Account:
    """Move ``account`` to ``new_state`` or raise ConflictError.

    Closing records ``closed_at`` and ``state_before_close``. Leaving
    ``closed`` enforces the calendar: restore only within 30 days, delete
    only from day 31.
    """
    current = account.state
    if not can_transition(current, new_state, account.state_before_close):
        raise ConflictError(
            f"account cannot move from {current.value} to {new_state.value}",
            current_state=current.value, requested_state=new_state.value,
        )
    now = clock.now()
    if current is _S.CLOSED and new_state is _S.DELETED:
        if not is_due_for_deletion(account, now):
            raise ConflictError(
                f"a closed account is deleted on day {DELETE_ON_DAY}, not before",
                days_since_closure=days_since_closure(account, now),
            )
    elif current is _S.CLOSED:
        if not can_restore(account, now):
            raise ConflictError(
                f"the {RESTORE_WINDOW_DAYS}-day restore window has passed",
                days_since_closure=days_since_closure(account, now),
            )
        account.closed_at = None
        account.state_before_close = None
    if new_state is _S.CLOSED:
        account.closed_at = now
        account.state_before_close = current
    account.state = new_state
    account.state_changed_at = now
    return account


def close(account: Account, clock: Clock) -> Account:
    """Close the account. Allowed from every state except ``deleted`` (and ``closed``)."""
    return transition(account, _S.CLOSED, clock)


def restore(account: Account, clock: Clock) -> Account:
    """Restore a closed account to the state it had before, within 30 days."""
    if account.state is not _S.CLOSED or account.state_before_close is None:
        raise ConflictError("only a closed account can be restored", state=account.state.value)
    return transition(account, account.state_before_close, clock)


def delete_if_due(account: Account, clock: Clock) -> bool:
    """Move a closed account to ``deleted`` when day 31 is reached. Returns True if it did."""
    if not is_due_for_deletion(account, clock.now()):
        return False
    transition(account, _S.DELETED, clock)
    return True


def require_editable(account: Account) -> None:
    """Raise AccountReadOnlyError unless the account is trialing, active or past_due."""
    if not account.state.can_edit:
        raise AccountReadOnlyError(
            f"account is {account.state.value} and cannot be edited",
            account_id=account.id, state=account.state.value,
        )

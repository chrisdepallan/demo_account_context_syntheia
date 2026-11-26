"""Ownership transfer: Admin target, 7-day window, previous Owner becomes Admin."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.accounts import ownership
from acme_cloud.accounts.models import (
    TRANSFER_ACCEPTED, TRANSFER_CANCELLED, TRANSFER_EXPIRED, TRANSFER_PENDING,
)
from acme_cloud.common.enums import AccountState, Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, NotFoundError, PermissionDeniedError, ValidationError,
)
from acme_cloud.common.ids import is_valid_id


@pytest.fixture
def account(make_account):
    return make_account(admins=2, billing_admins=1, members=1, guests=1)


def request(account, clock, ids, uid, target="admin1", actor=None):
    return ownership.request_transfer(
        account, actor or account.owner_id, uid(account, target), clock, ids,
    )


def test_owner_requests_a_transfer_to_an_admin(account, clock, ids, uid):
    transfer = request(account, clock, ids, uid)
    assert is_valid_id(transfer.id, "tr")
    assert transfer.status == TRANSFER_PENDING
    assert transfer.from_user_id == account.owner_id
    assert transfer.to_user_id == uid(account, "admin1")
    assert transfer.expires_at == clock.now() + timedelta(days=7)
    assert account.pending_transfer is transfer
    assert ownership.OWNERSHIP_TRANSFER_TTL_DAYS == 7


@pytest.mark.parametrize("target", ["billing1", "member1", "guest1"])
def test_target_must_be_an_existing_admin(account, clock, ids, uid, target):
    with pytest.raises(ValidationError):
        request(account, clock, ids, uid, target=target)
    assert account.pending_transfer is None


def test_target_must_be_a_member_of_the_account(account, clock, ids):
    with pytest.raises(NotFoundError):
        ownership.request_transfer(account, account.owner_id, "usr_ZZZZZZZZ", clock, ids)


@pytest.mark.parametrize("actor", ["admin1", "billing1", "member1"])
def test_only_the_owner_can_start_a_transfer(account, clock, ids, uid, actor):
    with pytest.raises(PermissionDeniedError):
        request(account, clock, ids, uid, target="admin2", actor=uid(account, actor))


def test_only_one_request_can_be_pending(account, clock, ids, uid):
    request(account, clock, ids, uid, target="admin1")
    with pytest.raises(ConflictError):
        request(account, clock, ids, uid, target="admin2")


def test_accepting_makes_the_admin_owner_and_the_previous_owner_admin(account, clock, ids, uid):
    old_owner, new_owner = account.owner_id, uid(account, "admin1")
    seats = account.seats
    request(account, clock, ids, uid)
    clock.advance(days=2)

    transfer = ownership.accept_transfer(account, new_owner, clock)

    assert transfer.status == TRANSFER_ACCEPTED
    assert transfer.completed_at == clock.now()
    assert account.owner_id == new_owner
    assert account.member(new_owner).role is Role.OWNER
    assert account.member(old_owner).role is Role.ADMIN
    assert [m for m in account.members.values() if m.role is Role.OWNER] == [account.owner]
    assert account.seats == seats            # no seat is added or freed
    assert account.pending_transfer is None


def test_accept_just_before_the_seventh_day(account, clock, ids, uid):
    request(account, clock, ids, uid)
    clock.advance(days=7, seconds=-1)
    ownership.accept_transfer(account, uid(account, "admin1"), clock)
    assert account.owner.email == "admin1@example.com"


def test_request_expires_after_seven_days_and_nothing_changes(account, clock, ids, uid):
    old_owner = account.owner_id
    transfer = request(account, clock, ids, uid)
    clock.advance(days=7)
    with pytest.raises(ConflictError):
        ownership.accept_transfer(account, uid(account, "admin1"), clock)
    assert transfer.status == TRANSFER_EXPIRED
    assert account.owner_id == old_owner
    assert account.member(uid(account, "admin1")).role is Role.ADMIN


def test_a_new_request_is_possible_after_expiry(account, clock, ids, uid):
    request(account, clock, ids, uid, target="admin1")
    clock.advance(days=8)
    second = request(account, clock, ids, uid, target="admin2")
    assert account.pending_transfer is second


def test_only_the_chosen_admin_can_accept(account, clock, ids, uid):
    request(account, clock, ids, uid, target="admin1")
    with pytest.raises(PermissionDeniedError):
        ownership.accept_transfer(account, uid(account, "admin2"), clock)
    assert account.pending_transfer is not None


def test_accept_without_a_request_is_not_found(account, clock, uid):
    with pytest.raises(NotFoundError):
        ownership.accept_transfer(account, uid(account, "admin1"), clock)


def test_target_demoted_before_accepting_cannot_accept(account, clock, ids, uid):
    transfer = request(account, clock, ids, uid)
    account.member(uid(account, "admin1")).role = Role.MEMBER
    with pytest.raises(ConflictError):
        ownership.accept_transfer(account, uid(account, "admin1"), clock)
    assert transfer.status == TRANSFER_CANCELLED
    assert account.owner.email == "owner@example.com"


def test_owner_can_cancel_the_request(account, clock, ids, uid):
    transfer = request(account, clock, ids, uid)
    with pytest.raises(PermissionDeniedError):
        ownership.cancel_transfer(account, uid(account, "admin1"))
    ownership.cancel_transfer(account, account.owner_id)
    assert transfer.status == TRANSFER_CANCELLED
    assert account.pending_transfer is None
    with pytest.raises(NotFoundError):
        ownership.cancel_transfer(account, account.owner_id)


def test_expire_if_stale_reports_whether_it_expired_something(account, clock, ids, uid):
    assert ownership.expire_if_stale(account, clock) is False
    request(account, clock, ids, uid)
    clock.advance(days=6)
    assert ownership.expire_if_stale(account, clock) is False
    clock.advance(days=1)
    assert ownership.expire_if_stale(account, clock) is True
    assert account.pending_transfer is None


@pytest.mark.parametrize("state", [AccountState.CLOSED, AccountState.DELETED])
def test_closed_account_cannot_be_transferred(make_account, clock, ids, uid, state):
    closed = make_account(admins=1, state=state)
    with pytest.raises(AccountReadOnlyError):
        request(closed, clock, ids, uid)


def test_read_only_account_can_still_be_transferred(make_account, clock, ids, uid):
    account = make_account(admins=1, state=AccountState.READ_ONLY)
    request(account, clock, ids, uid)
    ownership.accept_transfer(account, uid(account, "admin1"), clock)
    assert account.owner.email == "admin1@example.com"

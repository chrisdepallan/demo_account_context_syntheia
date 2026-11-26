"""Adding, removing and changing members: limits, seats and the single Owner."""

from __future__ import annotations

from datetime import date

import pytest

from acme_cloud.accounts import members
from acme_cloud.common.enums import AccountState, Plan, Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, LimitExceededError, NotFoundError,
    PermissionDeniedError, ValidationError,
)
from acme_cloud.common.money import Money


def add(account, clock, ids, email="new@example.com", role=Role.MEMBER):
    return members.add_member(account, ids.new("usr"), email, role, clock)


@pytest.mark.parametrize(
    ("plan", "limit"),
    [(Plan.FREE, 3), (Plan.STARTER, 10), (Plan.PRO, 100), (Plan.BUSINESS, 500),
     (Plan.ENTERPRISE, None)],
)
def test_member_limit_per_plan(plan, limit):
    assert members.member_limit(plan) == limit


@pytest.mark.parametrize(("plan", "limit"), [(Plan.FREE, 3), (Plan.STARTER, 10), (Plan.PRO, 100)])
def test_adding_a_member_over_the_plan_limit_fails(make_account, clock, ids, plan, limit):
    account = make_account(plan=plan, members=limit - 2)   # owner + members = limit - 1
    add(account, clock, ids, "last@example.com")           # reaches the limit
    assert account.seat_member_count == limit
    with pytest.raises(LimitExceededError) as caught:
        add(account, clock, ids, "over@example.com")
    assert caught.value.code == "ERR_LIMIT_EXCEEDED"
    assert caught.value.details["limit"] == limit


def test_enterprise_has_no_member_limit(make_account):
    account = make_account(plan=Plan.ENTERPRISE, members=600)
    members.check_member_capacity(account, extra=1000)  # no error


def test_new_member_takes_a_seat(make_account, clock, ids):
    """When no paid seat is free the seat count grows (billing charges it, prorated)."""
    account = make_account(plan=Plan.PRO)
    member = add(account, clock, ids, " New@Example.com ")
    assert member.email == "new@example.com"
    assert member.joined_at == clock.now()
    assert account.seats == 2


def test_a_spare_seat_is_used_before_adding_one(make_account, clock, ids):
    account = make_account(plan=Plan.PRO, seats=3)
    add(account, clock, ids)
    assert account.seats == 3


@pytest.mark.parametrize(("plan", "seats", "limit"), [(Plan.PRO, 1, 5), (Plan.PRO, 2, 10), (Plan.FREE, 1, 5)])
def test_guest_limit_is_five_per_paid_seat(make_account, clock, ids, plan, seats, limit):
    """Free accounts allow 5 guests in total. Guests never use a seat."""
    account = make_account(plan=plan, seats=seats, guests=limit - 1)
    add(account, clock, ids, "lastguest@example.com", Role.GUEST)
    assert account.guest_count == limit
    assert account.seats == seats
    with pytest.raises(LimitExceededError):
        add(account, clock, ids, "overguest@example.com", Role.GUEST)


def test_duplicate_member_is_a_conflict(make_account, clock, ids):
    account = make_account(members=1)
    with pytest.raises(ConflictError):
        add(account, clock, ids, "MEMBER1@example.com")


def test_a_second_owner_cannot_be_added(make_account, clock, ids):
    with pytest.raises(ValidationError):
        add(make_account(), clock, ids, role=Role.OWNER)


@pytest.mark.parametrize("state", [AccountState.READ_ONLY, AccountState.CLOSED, AccountState.DELETED])
def test_members_cannot_be_added_to_a_read_only_account(make_account, clock, ids, state):
    with pytest.raises(AccountReadOnlyError):
        add(make_account(state=state), clock, ids)


def test_removing_a_member_reassigns_content_and_frees_the_seat(make_account, clock, uid):
    account = make_account(admins=1, members=1)
    admin, member = uid(account, "admin1"), uid(account, "member1")
    account.content_owners = {"doc_1": member, "doc_2": account.owner_id, "doc_3": member}

    result = members.remove_member(account, admin, member, clock)

    assert member not in account.members            # access ends immediately
    assert account.content_owners == {"doc_1": admin, "doc_2": account.owner_id, "doc_3": admin}
    assert result.content_reassigned_to == admin
    assert result.reassigned_content_ids == ("doc_1", "doc_3")
    assert result.seats_freed == 1
    assert account.seats == 2
    assert result.removed_at == clock.now()


def test_removing_a_guest_frees_no_seat(make_account, clock, uid):
    account = make_account(guests=1, seats=1)
    result = members.remove_member(account, account.owner_id, uid(account, "guest1"), clock)
    assert result.seats_freed == 0
    assert account.seats == 1


def test_the_owner_cannot_be_removed(make_account, clock, uid):
    account = make_account(admins=1)
    with pytest.raises(ConflictError):
        members.remove_member(account, uid(account, "admin1"), account.owner_id, clock)
    assert account.owner_id in account.members


def test_nobody_can_remove_themselves(make_account, clock, uid):
    account = make_account(admins=1)
    admin = uid(account, "admin1")
    with pytest.raises(ValidationError):
        members.remove_member(account, admin, admin, clock)


@pytest.mark.parametrize("actor", ["billing1", "member1", "guest1"])
def test_only_owner_and_admin_can_remove_members(make_account, clock, uid, actor):
    account = make_account(billing_admins=1, members=2, guests=1)
    with pytest.raises(PermissionDeniedError):
        members.remove_member(account, uid(account, actor), uid(account, "member2"), clock)


def test_removal_works_in_read_only_but_not_when_closed(make_account, clock, uid):
    account = make_account(members=1, state=AccountState.READ_ONLY)
    members.remove_member(account, account.owner_id, uid(account, "member1"), clock)
    closed = make_account(members=1, state=AccountState.CLOSED)
    with pytest.raises(AccountReadOnlyError):
        members.remove_member(closed, closed.owner_id, uid(closed, "member1"), clock)


def test_removing_an_unknown_member_is_not_found(make_account, clock):
    account = make_account()
    with pytest.raises(NotFoundError):
        members.remove_member(account, account.owner_id, "usr_ZZZZZZZZ", clock)


def test_role_change_between_seat_roles_keeps_the_seat_count(make_account, uid):
    account = make_account(members=1)
    change = members.change_role(account, account.owner_id, uid(account, "member1"), Role.ADMIN)
    assert (change.old_role, change.new_role, change.seats_delta) == (Role.MEMBER, Role.ADMIN, 0)
    assert account.seats == 2


def test_the_owner_cannot_be_demoted(make_account, uid):
    account = make_account(admins=1)
    for actor in (account.owner_id, uid(account, "admin1")):
        with pytest.raises(ConflictError):
            members.change_role(account, actor, account.owner_id, Role.ADMIN)
    assert account.owner.role is Role.OWNER


def test_nobody_is_promoted_to_owner_by_a_role_change(make_account, uid):
    account = make_account(admins=1)
    with pytest.raises(ValidationError):
        members.change_role(account, account.owner_id, uid(account, "admin1"), Role.OWNER)


def test_guest_to_member_takes_a_seat_and_member_to_guest_frees_it(make_account, uid):
    account = make_account(members=1, guests=1)
    up = members.change_role(account, account.owner_id, uid(account, "guest1"), Role.MEMBER)
    assert up.seats_delta == 1 and account.seats == 3
    down = members.change_role(account, account.owner_id, uid(account, "member1"), Role.GUEST)
    assert down.seats_delta == -1 and account.seats == 2


def test_guest_cannot_become_member_when_the_plan_is_full(make_account, uid):
    account = make_account(plan=Plan.FREE, members=2, guests=1)
    with pytest.raises(LimitExceededError):
        members.change_role(account, account.owner_id, uid(account, "guest1"), Role.MEMBER)


def test_members_cannot_change_roles(make_account, uid):
    account = make_account(members=2)
    with pytest.raises(PermissionDeniedError):
        members.change_role(account, uid(account, "member1"), uid(account, "member2"), Role.ADMIN)


@pytest.mark.parametrize(
    ("plan", "annual", "removed_on", "days_remaining", "cents"),
    [(Plan.PRO, False, date(2026, 1, 16), 16, 1032),      # $20 * 16/31 = 10.3226
     (Plan.PRO, False, date(2026, 1, 1), 31, 2000),       # removed on the first day
     (Plan.PRO, False, date(2026, 2, 1), 0, 0),           # period already over
     (Plan.STARTER, False, date(2026, 1, 17), 15, 387),   # $8 * 15/31 = 3.871
     (Plan.BUSINESS, False, date(2026, 1, 30), 2, 290)],  # $45 * 2/31 = 2.903
)
def test_seat_credit_is_prorated_by_whole_days(plan, annual, removed_on, days_remaining, cents):
    credit = members.seat_credit(plan, 1, removed_on, date(2026, 1, 1), date(2026, 2, 1), annual)
    assert credit.days_remaining == days_remaining
    assert credit.days_in_period == 31
    assert credit.amount == Money(cents)


def test_seat_credit_on_an_annual_plan_covers_several_seats():
    credit = members.seat_credit(Plan.PRO, 2, date(2026, 7, 2), date(2026, 1, 1),
                                 date(2027, 1, 1), annual=True)
    assert (credit.days_remaining, credit.days_in_period) == (183, 365)
    assert credit.amount == Money(20055)   # 2 * $200 * 183/365 = 200.5479


def test_seat_credit_on_enterprise_has_no_list_price_amount():
    credit = members.seat_credit(Plan.ENTERPRISE, 1, date(2026, 1, 16), date(2026, 1, 1),
                                 date(2026, 2, 1))
    assert credit.amount is None
    assert credit.days_remaining == 16

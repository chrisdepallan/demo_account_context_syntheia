"""Invitations: batches of up to 50, 7-day expiry, resend and accept."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.accounts import invitations
from acme_cloud.accounts.invitations import INVITATION_TTL_DAYS, MAX_INVITATIONS_PER_BATCH
from acme_cloud.common.enums import AccountState, Plan, Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, LimitExceededError, NotFoundError,
    PermissionDeniedError, ValidationError,
)
from acme_cloud.common.ids import is_valid_id


def emails(count: int, label: str = "invitee") -> list[str]:
    return [f"{label}{n}@example.com" for n in range(1, count + 1)]


def invite(account, clock, ids, addresses, role=Role.MEMBER, actor=None):
    return invitations.invite_batch(account, actor or account.owner_id, addresses, role, clock, ids)


def test_constants():
    assert MAX_INVITATIONS_PER_BATCH == 50
    assert INVITATION_TTL_DAYS == 7


def test_a_batch_of_50_is_accepted(make_account, clock, ids):
    account = make_account(plan=Plan.PRO)
    created = invite(account, clock, ids, emails(50))
    assert len(created) == 50
    assert len(account.invitations) == 50
    assert all(is_valid_id(inv.id, "inv") for inv in created)


def test_a_batch_of_51_is_rejected_and_nothing_is_created(make_account, clock, ids):
    account = make_account(plan=Plan.PRO)
    with pytest.raises(ValidationError) as caught:
        invite(account, clock, ids, emails(51))
    assert caught.value.details == {"maximum": 50, "received": 51}
    assert account.invitations == {}


def test_an_empty_batch_is_rejected(make_account, clock, ids):
    with pytest.raises(ValidationError):
        invite(make_account(), clock, ids, [])


def test_invitation_expires_seven_days_after_it_is_sent(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, ["  New.Person@Example.com "], Role.ADMIN)
    assert invitation.email == "new.person@example.com"
    assert invitation.role is Role.ADMIN
    assert invitation.invited_by == account.owner_id
    assert invitation.expires_at == clock.now() + timedelta(days=7)


def test_accept_just_before_the_seventh_day(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, emails(1), Role.BILLING_ADMIN)
    clock.advance(days=7, seconds=-1)
    member = invitations.accept(account, invitation.id, ids.new("usr"), clock)
    assert member.role is Role.BILLING_ADMIN
    assert member.email == "invitee1@example.com"
    assert member.invited_by == account.owner_id
    assert invitation.accepted_at == clock.now()
    assert account.seats == 2


def test_accept_after_seven_days_fails(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, emails(1))
    clock.advance(days=7)
    with pytest.raises(ConflictError):
        invitations.accept(account, invitation.id, ids.new("usr"), clock)
    assert account.seat_member_count == 1


def test_resend_starts_a_new_seven_day_window(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, emails(1))
    clock.advance(days=5)
    invitations.resend(account, account.owner_id, invitation.id, clock)
    assert invitation.resend_count == 1
    assert invitation.last_sent_at == clock.now()
    assert invitation.expires_at == clock.now() + timedelta(days=7)
    clock.advance(days=6)    # day 11 after the first send, day 6 after the resend
    invitations.accept(account, invitation.id, ids.new("usr"), clock)


def test_an_expired_invitation_can_be_resent(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, emails(1))
    clock.advance(days=20)
    assert invitation.is_expired(clock.now())
    invitations.resend(account, account.owner_id, invitation.id, clock)
    assert invitation.is_pending(clock.now())


def test_an_accepted_invitation_cannot_be_resent_or_accepted_again(make_account, clock, ids):
    account = make_account()
    (invitation,) = invite(account, clock, ids, emails(1))
    invitations.accept(account, invitation.id, ids.new("usr"), clock)
    with pytest.raises(ConflictError):
        invitations.resend(account, account.owner_id, invitation.id, clock)
    with pytest.raises(ConflictError):
        invitations.accept(account, invitation.id, ids.new("usr"), clock)


def test_unknown_invitation_is_not_found(make_account, clock, ids):
    with pytest.raises(NotFoundError):
        invitations.accept(make_account(), "inv_ZZZZZZZZ", ids.new("usr"), clock)


def test_admin_can_invite(make_account, clock, ids, uid):
    account = make_account(admins=1)
    assert invite(account, clock, ids, emails(2), actor=uid(account, "admin1"))


@pytest.mark.parametrize("actor", ["billing1", "member1", "guest1"])
def test_only_owner_and_admin_can_invite(make_account, clock, ids, uid, actor):
    account = make_account(billing_admins=1, members=1, guests=1)
    with pytest.raises(PermissionDeniedError):
        invite(account, clock, ids, emails(1), actor=uid(account, actor))


def test_nobody_can_be_invited_as_owner(make_account, clock, ids):
    with pytest.raises(ValidationError):
        invite(make_account(), clock, ids, emails(1), Role.OWNER)


@pytest.mark.parametrize("bad", ["not-an-email", "@example.com", "person@", "a b@example.com"])
def test_invalid_address_rejects_the_whole_batch(make_account, clock, ids, bad):
    account = make_account()
    with pytest.raises(ValidationError):
        invite(account, clock, ids, ["good@example.com", bad])
    assert account.invitations == {}


def test_existing_member_or_pending_invitee_is_a_conflict(make_account, clock, ids):
    account = make_account(members=1)
    with pytest.raises(ConflictError):
        invite(account, clock, ids, ["member1@example.com"])
    invite(account, clock, ids, ["pending@example.com"])
    with pytest.raises(ConflictError):
        invite(account, clock, ids, ["Pending@example.com"])


def test_duplicates_inside_a_batch_are_sent_once(make_account, clock, ids):
    created = invite(make_account(), clock, ids, ["a@example.com", "A@example.com", "b@example.com"])
    assert [inv.email for inv in created] == ["a@example.com", "b@example.com"]


def test_pending_invitations_count_toward_the_member_limit(make_account, clock, ids):
    """Free allows 3 members: the Owner plus two pending invitations fill it."""
    account = make_account(plan=Plan.FREE)
    invite(account, clock, ids, emails(2))
    with pytest.raises(LimitExceededError):
        invite(account, clock, ids, ["third@example.com"])
    clock.advance(days=7)     # the two invitations expire and release their places
    assert invitations.pending_invitations(account, clock.now()) == []
    invite(account, clock, ids, ["third@example.com"])


def test_guest_invitations_respect_five_guests_per_seat(make_account, clock, ids):
    account = make_account(plan=Plan.PRO, seats=1)
    invite(account, clock, ids, emails(5, "guest"), Role.GUEST)
    with pytest.raises(LimitExceededError):
        invite(account, clock, ids, ["sixth@example.com"], Role.GUEST)
    invite(account, clock, ids, emails(3))   # members are counted separately


def test_read_only_account_cannot_invite(make_account, clock, ids):
    with pytest.raises(AccountReadOnlyError):
        invite(make_account(state=AccountState.READ_ONLY), clock, ids, emails(1))

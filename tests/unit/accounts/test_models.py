"""Account, Member, Invitation and OwnershipTransfer data models."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.accounts.models import (
    TRANSFER_ACCEPTED, TRANSFER_PENDING, Invitation, Member, OwnershipTransfer,
)
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import NotFoundError


@pytest.mark.parametrize(
    ("role", "uses_seat"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.BILLING_ADMIN, True),
     (Role.MEMBER, True), (Role.GUEST, False)],
)
def test_every_role_except_guest_uses_a_seat(clock, role, uses_seat):
    member = Member("usr_2B6N8R4V", "person@example.com", role, clock.now())
    assert member.uses_seat is uses_seat
    assert member.mfa_enrolled is False


def make_invitation(now) -> Invitation:
    return Invitation(
        id="inv_ABCDEFGH", account_id="acc_7F3K9Q2M", email="new@example.com",
        role=Role.MEMBER, invited_by="usr_2B6N8R4V", created_at=now,
        expires_at=now + timedelta(days=7), last_sent_at=now,
    )


def test_invitation_is_pending_until_the_seventh_day(clock):
    invitation = make_invitation(clock.now())
    just_before = clock.now() + timedelta(days=7, seconds=-1)
    assert invitation.is_pending(just_before)
    assert not invitation.is_expired(just_before)


def test_invitation_expires_after_exactly_seven_days(clock):
    invitation = make_invitation(clock.now())
    seven_days = clock.now() + timedelta(days=7)
    assert invitation.is_expired(seven_days)
    assert not invitation.is_pending(seven_days)


def test_accepted_invitation_is_neither_pending_nor_expired(clock):
    invitation = make_invitation(clock.now())
    invitation.accepted_at = clock.now() + timedelta(days=1)
    later = clock.now() + timedelta(days=30)
    assert not invitation.is_pending(later)
    assert not invitation.is_expired(later)


def test_ownership_transfer_expires_after_its_window(clock):
    now = clock.now()
    transfer = OwnershipTransfer(
        id="tr_ABCDEFGH", account_id="acc_7F3K9Q2M", from_user_id="usr_AAAAAAAA",
        to_user_id="usr_BBBBBBBB", requested_at=now, expires_at=now + timedelta(days=7),
    )
    assert transfer.status == TRANSFER_PENDING
    assert not transfer.is_expired(now + timedelta(days=6, hours=23))
    assert transfer.is_expired(now + timedelta(days=7))
    transfer.status = TRANSFER_ACCEPTED
    assert not transfer.is_expired(now + timedelta(days=8))


def test_account_defaults(make_account):
    account = make_account()
    assert account.seats == 1
    assert account.storage_packs == 0
    assert account.closed_at is None
    assert account.state_before_close is None
    assert account.pending_transfer is None
    assert account.invitations == {}


def test_account_has_exactly_one_owner(make_account):
    account = make_account(admins=2, members=3)
    owners = [m for m in account.members.values() if m.role is Role.OWNER]
    assert owners == [account.owner]
    assert account.owner.user_id == account.owner_id
    assert account.owner.email == "owner@example.com"


def test_member_lookup(make_account, uid):
    account = make_account(members=1)
    member_id = uid(account, "member1")
    assert account.member(member_id).email == "member1@example.com"
    with pytest.raises(NotFoundError) as caught:
        account.member("usr_ZZZZZZZZ")
    assert caught.value.code == "ERR_NOT_FOUND"


def test_find_member_by_email_ignores_case_and_spaces(make_account):
    account = make_account(admins=1)
    assert account.find_member_by_email("  Admin1@Example.com ").role is Role.ADMIN
    assert account.find_member_by_email("nobody@example.com") is None


def test_guests_are_counted_apart_from_seat_members(make_account):
    """Guests do not use seats."""
    account = make_account(admins=1, billing_admins=1, members=2, guests=3)
    assert account.seat_member_count == 5   # owner + admin + billing admin + 2 members
    assert account.guest_count == 3
    assert account.seats == 5


def test_emails_for_roles_picks_notification_recipients(make_account):
    account = make_account(admins=2, billing_admins=1, members=1)
    assert account.emails_for_roles(Role.OWNER, Role.ADMIN) == [
        "owner@example.com", "admin1@example.com", "admin2@example.com",
    ]
    assert account.emails_for_roles(Role.OWNER, Role.BILLING_ADMIN) == [
        "owner@example.com", "billing1@example.com",
    ]
    assert account.emails_for_roles(Role.GUEST) == []

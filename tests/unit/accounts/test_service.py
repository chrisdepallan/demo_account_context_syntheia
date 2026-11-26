"""AccountService: sign-up, trial, downgrade to Free, close, restore and purge."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.accounts import members, state_machine
from acme_cloud.accounts.service import AccountService
from acme_cloud.common.enums import AccountState, Plan, Role
from acme_cloud.common.errors import (
    ConflictError, NotFoundError, PermissionDeniedError, ValidationError,
)
from acme_cloud.common.ids import is_valid_id


@pytest.fixture
def service(clock, ids, notifier, audit) -> AccountService:
    return AccountService(clock, ids, notifier=notifier, audit=audit)


@pytest.fixture
def account(service):
    return service.create_account("Example Team", "Owner@Example.com")


def add(service, account, email, role):
    return members.add_member(account, service.ids.new("usr"), email, role, service.clock).user_id


def test_new_account_trials_pro_for_14_days(service, account, clock):
    assert is_valid_id(account.id, "acc") and is_valid_id(account.owner_id, "usr")
    assert account.state is AccountState.TRIALING
    assert account.plan is Plan.PRO
    assert account.trial_ends_at == clock.now() + timedelta(days=14)
    assert account.seats == 1
    assert account.owner.role is Role.OWNER and account.owner.email == "owner@example.com"
    assert service.get(account.id) is account


def test_account_needs_a_name_and_a_valid_owner_email(service):
    with pytest.raises(ValidationError):
        service.create_account("   ", "owner@example.com")
    with pytest.raises(ValidationError):
        service.create_account("Example Team", "not-an-email")


def test_unknown_account_is_not_found(service):
    with pytest.raises(NotFoundError):
        service.get("acc_ZZZZZZZZ")


def test_first_successful_charge_makes_the_trial_active(service, account, audit):
    service.convert_trial(account.id)
    assert (account.state, account.plan) == (AccountState.ACTIVE, Plan.PRO)
    assert audit.types() == []            # same plan: no plan.changed event
    other = service.create_account("Second Team", "second@example.com")
    service.convert_trial(other.id, Plan.BUSINESS)
    assert other.plan is Plan.BUSINESS and audit.types() == ["plan.changed"]


def test_trial_cannot_be_ended_before_day_14(service, account, clock):
    clock.advance(days=14, seconds=-1)
    with pytest.raises(ConflictError):
        service.end_trial(account.id)
    assert service.expire_trials() == []
    assert account.state is AccountState.TRIALING


def test_trial_ending_without_payment_moves_to_free_and_active(service, account, clock):
    clock.advance(days=14)
    assert service.expire_trials() == [account.id]
    assert (account.state, account.plan) == (AccountState.ACTIVE, Plan.FREE)
    assert service.expire_trials() == []


def test_trial_ending_email_goes_to_the_owner_three_days_before(service, account, clock, notifier):
    clock.advance(days=10)                      # four days left
    assert service.send_trial_reminders() == []
    clock.advance(days=1)                       # three days left
    assert service.send_trial_reminders() == [account.id]
    assert service.send_trial_reminders() == []     # only once
    assert [(t, to) for t, to, _ in notifier.sent] == [("trial_ending", ["owner@example.com"])]


def test_downgrade_to_free_turns_members_over_the_limit_into_guests(service, account):
    """Free allows 3 members: the Owner and the two Admins keep their roles."""
    for email, role in [("member1@example.com", Role.MEMBER), ("admin1@example.com", Role.ADMIN),
                        ("billing1@example.com", Role.BILLING_ADMIN),
                        ("admin2@example.com", Role.ADMIN), ("member2@example.com", Role.MEMBER)]:
        add(service, account, email, role)
    service.convert_trial(account.id)
    account.storage_packs = 2

    demoted = service.downgrade_to_free(account.id)

    assert [m.email for m in demoted] == [
        "billing1@example.com", "member1@example.com", "member2@example.com"]
    assert all(m.role is Role.GUEST for m in demoted)
    assert account.find_member_by_email("admin2@example.com").role is Role.ADMIN
    assert (account.plan, account.seats, account.seat_member_count) == (Plan.FREE, 3, 3)
    assert account.storage_packs == 0
    assert account.state is AccountState.ACTIVE
    with pytest.raises(ConflictError):
        service.downgrade_to_free(account.id)        # already on Free


def test_day_44_downgrade_reactivates_a_read_only_account(service, account, clock, notifier, audit):
    add(service, account, "billing1@example.com", Role.BILLING_ADMIN)
    service.convert_trial(account.id)
    state_machine.transition(account, AccountState.PAST_DUE, clock)
    state_machine.transition(account, AccountState.READ_ONLY, clock)

    service.downgrade_to_free(account.id, reason="dunning_day_44")

    assert (account.state, account.plan) == (AccountState.ACTIVE, Plan.FREE)
    assert notifier.sent[-1][:2] == (
        "account_downgraded", ["owner@example.com", "billing1@example.com"])
    event_type, actor, account_id, metadata = audit.events[-1]
    assert (event_type, actor, account_id) == ("plan.changed", "system", account.id)
    assert metadata == {"old_plan": "pro", "new_plan": "free", "reason": "dunning_day_44"}


def test_only_the_owner_can_close_and_must_type_the_name(service, account):
    admin = add(service, account, "admin1@example.com", Role.ADMIN)
    with pytest.raises(PermissionDeniedError):
        service.close_account(account.id, admin, "Example Team")
    with pytest.raises(ValidationError):
        service.close_account(account.id, account.owner_id, "example team")
    assert account.state is AccountState.TRIALING


def test_close_emails_the_owner_the_30_day_restore_link(service, account, notifier, audit):
    service.close_account(account.id, account.owner_id, "Example Team")
    assert account.state is AccountState.CLOSED
    template, to, context = notifier.sent[-1]
    assert (template, to) == ("account_closed", ["owner@example.com"])
    assert context["restore_days"] == 30 and account.id in context["restore_url"]
    assert audit.types() == ["account.closed"]


def test_restore_on_day_30_but_not_on_day_31(service, account, clock, audit):
    service.convert_trial(account.id)
    service.close_account(account.id, account.owner_id, "Example Team")
    clock.advance(days=30)
    service.restore_account(account.id, account.owner_id)
    assert account.state is AccountState.ACTIVE
    assert audit.types() == ["account.closed", "account.restored"]

    service.close_account(account.id, account.owner_id, "Example Team")
    clock.advance(days=31)
    with pytest.raises(ConflictError):
        service.restore_account(account.id, account.owner_id)


def test_purge_deletes_closed_accounts_on_day_31(service, account, clock):
    service.close_account(account.id, account.owner_id, "Example Team")
    clock.advance(days=30)
    assert service.purge_deleted() == []
    clock.advance(days=1)
    assert service.purge_deleted() == [account.id]
    assert account.state is AccountState.DELETED
    assert service.purge_deleted() == []
    with pytest.raises(ConflictError):
        service.restore_account(account.id, account.owner_id)


def test_invite_resend_and_accept(service, account, notifier, audit):
    invited = service.invite_members(account.id, account.owner_id,
                                     ["a@example.com", "b@example.com"])
    service.resend_invitation(account.id, account.owner_id, invited[0].id)
    assert [(t, to) for t, to, _ in notifier.sent] == [
        ("invitation", ["a@example.com"]), ("invitation", ["b@example.com"]),
        ("invitation", ["a@example.com"])]
    assert audit.types() == ["member.invited", "member.invited"]
    member = service.accept_invitation(account.id, invited[1].id)
    assert is_valid_id(member.user_id, "usr") and member.role is Role.MEMBER
    assert account.seats == 2


def test_remove_and_role_change_are_audited(service, account, audit):
    member = add(service, account, "member1@example.com", Role.MEMBER)
    other = add(service, account, "member2@example.com", Role.MEMBER)
    service.change_member_role(account.id, account.owner_id, member, Role.ADMIN)
    result = service.remove_member(account.id, member, other)
    assert result.content_reassigned_to == member and account.seats == 2
    assert audit.types() == ["member.role_changed", "member.removed", "seats.changed"]
    assert audit.events[0][3] == {"user_id": member, "old_role": "member", "new_role": "admin"}


def test_ownership_transfer_flow(service, account, notifier, audit):
    admin = add(service, account, "admin1@example.com", Role.ADMIN)
    old_owner = account.owner_id
    service.request_ownership_transfer(account.id, old_owner, admin)
    assert notifier.sent[-1][:2] == ("ownership_transfer", ["admin1@example.com"])
    service.accept_ownership_transfer(account.id, admin)
    assert account.owner_id == admin and account.member(old_owner).role is Role.ADMIN
    assert audit.types() == ["ownership.transfer_requested", "ownership.transferred"]


def test_service_works_without_notifier_and_audit(clock, ids):
    service = AccountService(clock, ids)
    account = service.create_account("Quiet Team", "owner@example.com")
    service.invite_members(account.id, account.owner_id, ["a@example.com"])
    service.close_account(account.id, account.owner_id, "Quiet Team")
    assert account.state is AccountState.CLOSED

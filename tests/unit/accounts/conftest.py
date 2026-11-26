"""Fixtures for the accounts tests: an account factory and fake collaborators."""

from __future__ import annotations

import pytest

from acme_cloud.accounts.models import Account, Member
from acme_cloud.common.enums import AccountState, Plan, Role


class FakeNotifier:
    """Records every ``send`` call as ``(template_key, to, context)``."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, list[str], dict]] = []

    def send(self, template_key: str, to: list[str], **context) -> None:
        self.sent.append((template_key, list(to), context))

    def templates(self) -> list[str]:
        return [template for template, _, _ in self.sent]


class FakeAudit:
    """Records every ``record`` call as ``(event_type, actor_id, account_id, metadata)``."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, dict]] = []

    def record(self, event_type, actor_id, account_id, workspace_id=None, **metadata) -> None:
        self.events.append((event_type, actor_id, account_id, metadata))

    def types(self) -> list[str]:
        return [event_type for event_type, *_ in self.events]


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def audit() -> FakeAudit:
    return FakeAudit()


@pytest.fixture
def make_account(clock, ids):
    """Build an account with an Owner (``owner@example.com``) and extra people.

    Extra people get addresses such as ``admin1@example.com``,
    ``billing1@example.com``, ``member2@example.com`` and ``guest1@example.com``.
    ``seats`` defaults to the number of seat-using members.
    """

    def _make(plan=Plan.PRO, state=AccountState.ACTIVE, admins=0, billing_admins=0,
              members=0, guests=0, seats=None) -> Account:
        now = clock.now()
        owner = Member(ids.new("usr"), "owner@example.com", Role.OWNER, now)
        account = Account(
            id=ids.new("acc"), name="Example Team", owner_id=owner.user_id, plan=plan,
            state=state, created_at=now, members={owner.user_id: owner},
        )
        groups = [(Role.ADMIN, admins, "admin"), (Role.BILLING_ADMIN, billing_admins, "billing"),
                  (Role.MEMBER, members, "member"), (Role.GUEST, guests, "guest")]
        for role, count, label in groups:
            for number in range(1, count + 1):
                person = Member(ids.new("usr"), f"{label}{number}@example.com", role, now)
                account.members[person.user_id] = person
        account.seats = seats if seats is not None else account.seat_member_count
        return account

    return _make


@pytest.fixture
def uid():
    """Look up a member's user ID by the local part of the address: ``uid(account, "admin1")``."""

    def _uid(account: Account, name: str) -> str:
        member = account.find_member_by_email(f"{name}@example.com")
        assert member is not None, name
        return member.user_id

    return _uid

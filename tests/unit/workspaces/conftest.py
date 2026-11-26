"""Fixtures for the workspaces tests: an account factory and fake collaborators."""

from __future__ import annotations

import pytest

from acme_cloud.accounts.models import Account, Member
from acme_cloud.common.enums import AccountState, Plan, Region, Role
from acme_cloud.workspaces.models import Workspace

ROLE_LABELS = {Role.ADMIN: "admin", Role.BILLING_ADMIN: "billing", Role.MEMBER: "member",
               Role.GUEST: "guest"}


class FakeNotifier:
    """Records every ``send`` call as ``(template_key, to, context)``."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, list[str], dict]] = []

    def send(self, template_key: str, to: list[str], **context) -> None:
        self.sent.append((template_key, list(to), context))


class FakeAudit:
    """Records every ``record`` call as ``(event_type, actor_id, account_id, workspace_id, metadata)``."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, str | None, dict]] = []

    def record(self, event_type, actor_id, account_id, workspace_id=None, **metadata) -> None:
        self.events.append((event_type, actor_id, account_id, workspace_id, metadata))


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def audit() -> FakeAudit:
    return FakeAudit()


@pytest.fixture
def make_account(clock, ids):
    """Build an account with an Owner plus one Admin, Billing admin, Member and Guest.

    Addresses are ``owner@example.com``, ``admin@example.com``,
    ``billing@example.com``, ``member@example.com`` and ``guest@example.com``.
    """

    def _make(plan=Plan.PRO, state=AccountState.ACTIVE, seats=1, storage_packs=0) -> Account:
        now = clock.now()
        owner = Member(ids.new("usr"), "owner@example.com", Role.OWNER, now)
        account = Account(
            id=ids.new("acc"), name="Example Team", owner_id=owner.user_id, plan=plan,
            state=state, created_at=now, seats=seats, storage_packs=storage_packs,
            members={owner.user_id: owner},
        )
        for role, label in ROLE_LABELS.items():
            person = Member(ids.new("usr"), f"{label}@example.com", role, now)
            account.members[person.user_id] = person
        return account

    return _make


@pytest.fixture
def uid():
    """Look up a user ID by role label: ``uid(account, "admin")``."""

    def _uid(account: Account, name: str) -> str:
        member = account.find_member_by_email(f"{name}@example.com")
        assert member is not None, name
        return member.user_id

    return _uid


@pytest.fixture
def make_workspace(clock, ids):
    """Build a workspace of ``account`` directly, without the service."""

    def _make(account: Account, used_mb: int = 0, region: Region = Region.US_EAST) -> Workspace:
        return Workspace(
            id=ids.new("ws"), account_id=account.id, name="Main", region=region,
            created_at=clock.now(), created_by=account.owner_id, storage_used_mb=used_mb,
        )

    return _make

"""Fixtures for the API key tests: fake notifier and audit, and a key service."""

from __future__ import annotations

import pytest

from acme_cloud.api_keys.service import ApiKeyService


class FakeNotifier:
    """Records ``send(template_key, to, **context)`` calls."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, list[str], dict]] = []

    def send(self, template_key: str, to: list[str], **context: object) -> None:
        self.sent.append((template_key, to, context))


class FakeAudit:
    """Records ``record(event_type, actor_id, account_id, workspace_id, **metadata)`` calls."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, str | None, dict]] = []

    def record(self, event_type: str, actor_id: str, account_id: str,
               workspace_id: str | None = None, **metadata: object) -> None:
        self.events.append((event_type, actor_id, account_id, workspace_id, metadata))

    def types(self) -> list[str]:
        return [event[0] for event in self.events]


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def audit() -> FakeAudit:
    return FakeAudit()


@pytest.fixture
def service(clock, ids, notifier, audit) -> ApiKeyService:
    return ApiKeyService(clock, ids, notifier=notifier, audit=audit)


@pytest.fixture
def create(service):
    """Create a key in workspace ``ws_TEST01`` as an Owner on Pro, with overridable arguments."""
    from acme_cloud.common.enums import Plan, Role

    def _create(**overrides):
        arguments = dict(
            workspace_id="ws_TEST01", account_id="acc_TEST0001", plan=Plan.PRO,
            actor_id="usr_OWNER001", actor_role=Role.OWNER, name="CI pipeline",
            scopes=["projects:read"], expires_in_days=90,
        )
        arguments.update(overrides)
        return service.create_key(**arguments)

    return _create

"""Fixtures for the auth tests: fake notifier and audit collaborators."""

from __future__ import annotations

import pytest


class FakeNotifier:
    """Records ``send(template_key, to, **context)`` calls."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, list[str], dict]] = []

    def send(self, template_key: str, to: list[str], **context: object) -> None:
        self.sent.append((template_key, to, context))

    def templates(self) -> list[str]:
        return [template for template, _, _ in self.sent]


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

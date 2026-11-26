"""Audit events: the 25 recorded event names and the immutable AuditEvent record."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest

from acme_cloud.audit import events
from acme_cloud.audit.events import ALL_EVENT_TYPES, CSV_COLUMNS, AuditEvent, is_known_event

#: The list from the facts sheet, in its order.
FACTS_SHEET_EVENTS = [
    "login.succeeded", "login.failed", "login.locked", "password.reset", "mfa.enrolled",
    "mfa.reset", "member.invited", "member.removed", "member.role_changed",
    "ownership.transfer_requested", "ownership.transferred", "account.closed",
    "account.restored", "plan.changed", "seats.changed", "payment_method.updated",
    "refund.issued", "sso.enabled", "sso.enforced", "policy.changed", "api_key.created",
    "api_key.rotated", "api_key.revoked", "export.started", "export.downloaded",
]


def make_event(**overrides):
    values = dict(
        id="evt_3G7H2K9M4P6Q", event_type=events.PLAN_CHANGED, actor_id="usr_2B6N8R4V",
        account_id="acc_7F3K9Q2M", occurred_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
        workspace_id=None, metadata={"old": "pro", "new": "business"},
    )
    values.update(overrides)
    return AuditEvent(**values)


def test_all_25_event_types_match_the_facts_sheet():
    assert list(ALL_EVENT_TYPES) == FACTS_SHEET_EVENTS
    assert len(set(ALL_EVENT_TYPES)) == 25


@pytest.mark.parametrize("name", FACTS_SHEET_EVENTS)
def test_every_event_has_a_named_constant(name):
    constant = name.replace(".", "_").upper()   # plan.changed -> PLAN_CHANGED
    assert getattr(events, constant) == name
    assert is_known_event(name)


@pytest.mark.parametrize("name", ["invoice.paid", "plan.change", "", "PLAN.CHANGED"])
def test_other_names_are_not_audit_events(name):
    assert not is_known_event(name)


def test_event_stores_actor_account_workspace_time_and_metadata():
    event = make_event(workspace_id="ws_4H8P2L")
    assert (event.actor_id, event.account_id, event.workspace_id) == (
        "usr_2B6N8R4V", "acc_7F3K9Q2M", "ws_4H8P2L")
    assert event.occurred_at.tzinfo is timezone.utc
    assert event.metadata["new"] == "business"


def test_event_fields_cannot_be_changed():
    event = make_event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.event_type = events.SEATS_CHANGED
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.metadata = {}


def test_metadata_is_read_only_and_detached_from_the_callers_dict():
    source = {"old": "pro"}
    event = make_event(metadata=source)
    source["old"] = "tampered"
    assert event.metadata["old"] == "pro"
    with pytest.raises(TypeError):
        event.metadata["old"] = "tampered"


def test_metadata_defaults_to_empty():
    event = AuditEvent("evt_3G7H2K9M4P6Q", events.LOGIN_FAILED, "usr_2B6N8R4V", "acc_7F3K9Q2M",
                       datetime(2026, 1, 5, tzinfo=timezone.utc))
    assert dict(event.metadata) == {} and event.workspace_id is None


def test_to_row_follows_the_csv_columns():
    row = make_event(workspace_id="ws_4H8P2L").to_row()
    assert len(row) == len(CSV_COLUMNS)
    as_dict = dict(zip(CSV_COLUMNS, row))
    assert as_dict["id"] == "evt_3G7H2K9M4P6Q"
    assert as_dict["occurred_at"] == "2026-01-05T09:00:00+00:00"
    assert as_dict["event_type"] == "plan.changed"
    assert as_dict["workspace_id"] == "ws_4H8P2L"
    assert json.loads(as_dict["metadata"]) == {"old": "pro", "new": "business"}


def test_to_row_uses_an_empty_string_when_there_is_no_workspace():
    assert dict(zip(CSV_COLUMNS, make_event().to_row()))["workspace_id"] == ""

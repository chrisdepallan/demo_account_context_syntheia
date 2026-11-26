"""Audit log: append-only, filters, retention by plan, purge and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import timedelta

import pytest

from acme_cloud.audit.log import MAX_METADATA_KEYS, AuditLog, retention_days, retention_for
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError, ValidationError
from acme_cloud.common.ids import is_valid_id

ACCOUNT, OTHER = "acc_7F3K9Q2M", "acc_5T9W3E7Y"
OWNER, ADMIN = "usr_2B6N8R4V", "usr_8C2V6B4N"


@pytest.fixture
def log(clock, ids):
    return AuditLog(clock, ids)


def test_record_stores_actor_account_workspace_time_and_metadata(log, clock):
    event = log.record("member.role_changed", OWNER, ACCOUNT, "ws_4H8P2L", old="member", new="admin")
    assert is_valid_id(event.id, "evt")
    assert (event.actor_id, event.account_id, event.workspace_id) == (OWNER, ACCOUNT, "ws_4H8P2L")
    assert event.occurred_at == clock.now()
    assert dict(event.metadata) == {"old": "member", "new": "admin"}
    assert log.record("login.succeeded", OWNER, ACCOUNT).workspace_id is None


def test_only_known_event_types_with_actor_and_account_are_accepted(log):
    with pytest.raises(ValidationError):
        log.record("invoice.paid", OWNER, ACCOUNT)
    with pytest.raises(ValidationError):
        log.record("login.failed", "", ACCOUNT)
    with pytest.raises(ValidationError):
        log.record("login.failed", OWNER, ACCOUNT,
                   **{f"k{i}": i for i in range(MAX_METADATA_KEYS + 1)})
    assert len(log) == 0


def test_log_is_append_only():
    """ADR 0008: no update or delete API; purge_expired is the only removal."""
    public = {name for name in dir(AuditLog) if not name.startswith("_")}
    assert public == {"record", "query", "purge_expired", "export_csv"}


def test_query_returns_one_accounts_events_oldest_first(log, clock):
    first = log.record("login.succeeded", OWNER, ACCOUNT)
    log.record("login.succeeded", ADMIN, OTHER)
    clock.advance(minutes=5)
    second = log.record("plan.changed", OWNER, ACCOUNT)
    assert log.query(ACCOUNT) == [first, second]
    log.query(ACCOUNT).clear()  # the returned list is a copy
    assert len(log.query(ACCOUNT)) == 2


def test_query_filters_by_actor_event_type_and_time_range(log, clock):
    start = clock.now()
    login = log.record("login.succeeded", OWNER, ACCOUNT)
    clock.advance(hours=1)
    invite = log.record("member.invited", ADMIN, ACCOUNT)
    clock.advance(hours=1)
    key = log.record("api_key.created", ADMIN, ACCOUNT)
    assert log.query(ACCOUNT, actor_id=ADMIN) == [invite, key]
    assert log.query(ACCOUNT, event_type="login.succeeded") == [login]
    assert log.query(ACCOUNT, actor_id=OWNER, event_type="member.invited") == []
    # since is inclusive, until is exclusive
    assert log.query(ACCOUNT, since=start + timedelta(hours=1)) == [invite, key]
    assert log.query(ACCOUNT, until=start + timedelta(hours=2)) == [login, invite]
    assert log.query(ACCOUNT, since=start, until=start + timedelta(hours=1)) == [login]


@pytest.mark.parametrize(
    "plan, days",
    [(Plan.FREE, 0), (Plan.STARTER, 0), (Plan.PRO, 90), (Plan.BUSINESS, 365),
     (Plan.ENTERPRISE, 7 * 365)],
)
def test_retention_by_plan(plan, days):
    assert retention_days(plan) == days
    assert retention_for(plan) == (timedelta(days=days) if days else None)


@pytest.mark.parametrize("plan", [Plan.FREE, Plan.STARTER])
def test_reading_the_audit_log_needs_pro_or_higher(log, plan):
    log.record("login.succeeded", OWNER, ACCOUNT)
    with pytest.raises(PlanRequiredError) as error:
        log.query(ACCOUNT, plan=plan)
    assert error.value.code == "ERR_PLAN_REQUIRED"


@pytest.mark.parametrize(
    "plan, age_days, visible",
    [
        (Plan.PRO, 90, True), (Plan.PRO, 91, False),
        (Plan.BUSINESS, 365, True), (Plan.BUSINESS, 366, False),
        (Plan.ENTERPRISE, 2555, True), (Plan.ENTERPRISE, 2556, False),
    ],
)
def test_events_are_kept_for_the_plans_retention_then_purged(log, clock, plan, age_days, visible):
    log.record("login.succeeded", OWNER, ACCOUNT)
    clock.advance(days=age_days)
    assert len(log.query(ACCOUNT, plan=plan)) == (1 if visible else 0)
    assert log.purge_expired({ACCOUNT: plan}) == (0 if visible else 1)
    assert len(log) == (1 if visible else 0)


def test_purge_removes_everything_for_plans_without_an_audit_log(log):
    log.record("login.succeeded", OWNER, ACCOUNT)
    log.record("login.succeeded", ADMIN, OTHER)
    assert log.purge_expired({ACCOUNT: Plan.STARTER}) == 1
    assert log.query(ACCOUNT) == [] and len(log.query(OTHER)) == 1  # unknown accounts are kept


def test_purge_uses_each_accounts_own_plan(log, clock):
    log.record("login.succeeded", OWNER, ACCOUNT)
    log.record("login.succeeded", ADMIN, OTHER)
    clock.advance(days=100)
    assert log.purge_expired({ACCOUNT: Plan.PRO, OTHER: Plan.BUSINESS}) == 1
    assert log.query(ACCOUNT) == [] and len(log.query(OTHER)) == 1


def test_csv_export_has_a_header_and_one_row_per_event(log, clock):
    log.record("plan.changed", OWNER, ACCOUNT, old="pro", new="business")
    clock.advance(minutes=1)
    log.record("export.started", ADMIN, ACCOUNT, "ws_4H8P2L")
    rows = list(csv.reader(io.StringIO(log.export_csv(ACCOUNT))))
    assert rows[0] == ["id", "occurred_at", "event_type", "actor_id", "account_id",
                       "workspace_id", "metadata"]
    assert [row[2] for row in rows[1:]] == ["plan.changed", "export.started"]
    assert rows[1][6] == '{"new": "business", "old": "pro"}'
    assert rows[2][5] == "ws_4H8P2L"


def test_csv_export_applies_the_same_filters_as_query(log):
    log.record("plan.changed", OWNER, ACCOUNT)
    log.record("member.invited", ADMIN, ACCOUNT)
    rows = list(csv.reader(io.StringIO(log.export_csv(ACCOUNT, actor_id=ADMIN, plan=Plan.PRO))))
    assert len(rows) == 2 and rows[1][3] == ADMIN
    with pytest.raises(PlanRequiredError):
        log.export_csv(ACCOUNT, plan=Plan.FREE)

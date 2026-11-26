"""Export: statuses, one running export per workspace, 7-day link, 24-hour timeout."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.common.enums import Role
from acme_cloud.common.errors import ConflictError, PermissionDeniedError
from acme_cloud.common.ids import is_valid_id
from acme_cloud.workspaces import export as rules
from acme_cloud.workspaces.models import ExportStatus


@pytest.fixture
def workspace(make_account, make_workspace):
    return make_workspace(make_account())


@pytest.fixture
def new_export(workspace, clock, ids):
    """Request an export of ``workspace`` as the Owner, given the existing exports."""

    def _new(existing=(), target=None, role=Role.OWNER):
        return rules.request_export(target or workspace, existing, "usr_2B6N8R4V", role, clock, ids)

    return _new


def test_constants():
    assert rules.EXPORT_LINK_TTL_DAYS == 7
    assert rules.EXPORT_TIMEOUT_HOURS == 24


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN])
def test_owner_and_admin_can_request_an_export(new_export, workspace, clock, role):
    export = new_export(role=role)
    assert is_valid_id(export.id, "exp")
    assert export.status is ExportStatus.QUEUED
    assert export.workspace_id == workspace.id
    assert export.account_id == workspace.account_id
    assert export.requested_at == clock.now()


@pytest.mark.parametrize("role", [Role.BILLING_ADMIN, Role.MEMBER, Role.GUEST])
def test_other_roles_cannot_export(new_export, role):
    with pytest.raises(PermissionDeniedError):
        new_export(role=role)


def test_second_export_while_one_is_queued_is_a_conflict(new_export):
    first = new_export()
    with pytest.raises(ConflictError) as caught:
        new_export(existing=[first])
    assert caught.value.code == "ERR_CONFLICT"
    assert caught.value.details["export_id"] == first.id


def test_second_export_while_one_is_running_is_a_conflict(new_export, clock):
    first = rules.start(new_export(), clock)
    assert first.status is ExportStatus.RUNNING and first.started_at == clock.now()
    with pytest.raises(ConflictError):
        new_export(existing=[first])


def test_a_new_export_is_allowed_once_the_first_has_finished(new_export, clock):
    first = rules.complete(rules.start(new_export(), clock), clock)
    second = new_export(existing=[first])
    assert second.status is ExportStatus.QUEUED


def test_the_limit_is_per_workspace(new_export, make_account, make_workspace, clock):
    first = rules.start(new_export(), clock)
    other_workspace = make_workspace(make_account())
    assert new_export(existing=[first], target=other_workspace).workspace_id == other_workspace.id


def test_ready_export_has_a_link_valid_for_seven_days(new_export, clock):
    export = rules.start(new_export(), clock)
    clock.advance(hours=2)
    rules.complete(export, clock)
    assert export.status is ExportStatus.READY
    assert export.finished_at == clock.now()
    assert export.expires_at == clock.now() + timedelta(days=7)
    assert export.download_url == f"https://app.acme-cloud.example/exports/{export.id}/download"
    assert rules.download_link(export, clock) == export.download_url


def test_link_works_just_before_day_7_and_expires_at_day_7(new_export, clock):
    export = rules.complete(rules.start(new_export(), clock), clock)
    clock.advance(days=7, seconds=-1)
    assert rules.download_link(export, clock)
    clock.advance(seconds=1)
    with pytest.raises(ConflictError):
        rules.download_link(export, clock)
    assert export.status is ExportStatus.EXPIRED
    assert export.download_url is None


def test_export_running_exactly_24_hours_is_still_running(new_export, clock):
    export = rules.start(new_export(), clock)
    clock.advance(hours=24)
    assert rules.refresh(export, clock).status is ExportStatus.RUNNING
    rules.complete(export, clock)
    assert export.status is ExportStatus.READY


def test_export_running_longer_than_24_hours_is_failed(new_export, clock):
    export = rules.start(new_export(), clock)
    clock.advance(hours=24, seconds=1)
    rules.refresh(export, clock)
    assert export.status is ExportStatus.FAILED
    assert export.failure_reason == "timeout"
    with pytest.raises(ConflictError):
        rules.complete(export, clock)      # a late worker cannot revive it


def test_a_timed_out_export_no_longer_blocks_a_new_one(new_export, clock):
    stuck = rules.start(new_export(), clock)
    clock.advance(hours=25)
    retry = new_export(existing=[stuck])
    assert stuck.status is ExportStatus.FAILED
    assert retry.status is ExportStatus.QUEUED


def test_a_queued_export_does_not_time_out(new_export, clock):
    """The 24 hours count from the moment the export starts running."""
    export = new_export()
    clock.advance(hours=48)
    assert rules.refresh(export, clock).status is ExportStatus.QUEUED


def test_worker_can_fail_a_queued_or_running_export(new_export, clock):
    queued = rules.fail(new_export(), clock, "storage unavailable")
    assert (queued.status, queued.failure_reason) == (ExportStatus.FAILED, "storage unavailable")
    running = rules.fail(rules.start(new_export(), clock), clock, "worker crashed")
    assert running.status is ExportStatus.FAILED and running.finished_at == clock.now()


def test_invalid_status_changes_are_conflicts(new_export, clock):
    export = new_export()
    with pytest.raises(ConflictError):
        rules.complete(export, clock)          # not started yet
    with pytest.raises(ConflictError):
        rules.download_link(export, clock)     # not ready yet
    rules.start(export, clock)
    with pytest.raises(ConflictError):
        rules.start(export, clock)             # already running
    rules.complete(export, clock)
    with pytest.raises(ConflictError):
        rules.fail(export, clock, "too late")  # already ready
    assert export.status is ExportStatus.READY

"""Workspace and Export data models."""

from __future__ import annotations

import pytest

from acme_cloud.common.enums import Region
from acme_cloud.common.ids import is_valid_id
from acme_cloud.workspaces.models import Export, ExportStatus, Workspace


def test_export_statuses_match_the_facts_sheet():
    assert [status.value for status in ExportStatus] == [
        "queued", "running", "ready", "expired", "failed",
    ]


@pytest.mark.parametrize(
    ("status", "active"),
    [(ExportStatus.QUEUED, True), (ExportStatus.RUNNING, True), (ExportStatus.READY, False),
     (ExportStatus.EXPIRED, False), (ExportStatus.FAILED, False)],
)
def test_queued_and_running_exports_are_active(status, active):
    """Only an active export blocks a new export of the same workspace."""
    assert status.is_active is active


def test_export_status_accepts_plain_strings():
    assert ExportStatus("ready") is ExportStatus.READY
    assert ExportStatus.FAILED == "failed"


def test_new_workspace_uses_no_storage(make_account, make_workspace):
    account = make_account()
    workspace = make_workspace(account)
    assert workspace.storage_used_mb == 0
    assert workspace.account_id == account.id
    assert workspace.region is Region.US_EAST
    assert workspace.created_by == account.owner_id
    assert is_valid_id(workspace.id, "ws")


def test_workspace_keeps_the_region_it_was_created_in(make_account, make_workspace):
    workspace = make_workspace(make_account(), region=Region.EU_CENTRAL)
    assert workspace.region.value == "eu-central"
    assert workspace.region.location == "Frankfurt, Germany"


def test_new_export_is_queued_without_a_link(clock):
    export = Export(
        id="exp_6J4D8S2A", workspace_id="ws_4H8P2L", account_id="acc_7F3K9Q2M",
        requested_by="usr_2B6N8R4V", requested_at=clock.now(),
    )
    assert export.status is ExportStatus.QUEUED
    assert export.is_active
    assert export.started_at is None
    assert export.finished_at is None
    assert export.expires_at is None
    assert export.download_url is None
    assert export.failure_reason is None


def test_export_is_active_follows_its_status(clock):
    export = Export(
        id="exp_6J4D8S2A", workspace_id="ws_4H8P2L", account_id="acc_7F3K9Q2M",
        requested_by="usr_2B6N8R4V", requested_at=clock.now(), status=ExportStatus.READY,
    )
    assert not export.is_active
    export.status = ExportStatus.RUNNING
    assert export.is_active


def test_workspaces_are_independent_records(make_account, make_workspace):
    account = make_account()
    first, second = make_workspace(account, used_mb=10), make_workspace(account, used_mb=20)
    assert first.id != second.id
    assert isinstance(first, Workspace)
    assert (first.storage_used_mb, second.storage_used_mb) == (10, 20)

"""WorkspaceService: workspace count per plan, regions, storage emails and exports."""

from __future__ import annotations

import pytest

from acme_cloud.accounts.plans import GB
from acme_cloud.common.enums import AccountState, Plan, Region
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, LimitExceededError, NotFoundError,
    PermissionDeniedError, PlanRequiredError, ValidationError,
)
from acme_cloud.common.ids import is_valid_id
from acme_cloud.workspaces.models import ExportStatus
from acme_cloud.workspaces.service import WorkspaceService
from acme_cloud.workspaces.storage import StorageLevel


@pytest.fixture
def service(clock, ids, notifier, audit) -> WorkspaceService:
    return WorkspaceService(clock, ids, notifier=notifier, audit=audit)


def create(service, account, name="Main", region=None, actor=None):
    return service.create_workspace(account, actor or account.owner_id, name, region)


def test_workspace_is_created_in_us_east_by_default(service, make_account, clock):
    account = make_account()
    workspace = create(service, account, "  Design  ")
    assert is_valid_id(workspace.id, "ws")
    assert (workspace.name, workspace.region) == ("Design", Region.US_EAST)
    assert workspace.created_at == clock.now()
    assert service.get(workspace.id) is workspace
    assert service.list_for_account(account.id) == [workspace]


@pytest.mark.parametrize(
    ("plan", "limit"), [(Plan.FREE, 1), (Plan.STARTER, 1), (Plan.PRO, 3), (Plan.BUSINESS, 10)])
def test_workspace_count_limit_per_plan(service, make_account, plan, limit):
    account = make_account(plan=plan)
    for number in range(limit):
        create(service, account, f"Workspace {number + 1}")
    with pytest.raises(LimitExceededError) as caught:
        create(service, account, "One too many")
    assert caught.value.details["limit"] == limit
    assert len(service.list_for_account(account.id)) == limit


def test_enterprise_has_no_workspace_limit_and_limits_are_per_account(service, make_account):
    enterprise, free = make_account(plan=Plan.ENTERPRISE), make_account(plan=Plan.FREE)
    for number in range(12):
        create(service, enterprise, f"Workspace {number + 1}")
    create(service, free)            # the other account's workspaces do not count
    assert len(service.list_for_account(enterprise.id)) == 12


def test_only_owner_and_admin_create_workspaces(service, make_account, uid):
    account = make_account()
    create(service, account, actor=uid(account, "admin"))
    for name in ("billing", "member", "guest"):
        with pytest.raises(PermissionDeniedError):
            create(service, account, actor=uid(account, name))


def test_name_is_required_and_account_must_be_editable(service, make_account):
    with pytest.raises(ValidationError):
        create(service, make_account(), "   ")
    with pytest.raises(AccountReadOnlyError):
        create(service, make_account(state=AccountState.READ_ONLY))


def test_region_depends_on_the_plan_and_is_fixed(service, make_account):
    with pytest.raises(PlanRequiredError):
        create(service, make_account(plan=Plan.PRO), region="eu-central")
    with pytest.raises(PlanRequiredError):
        create(service, make_account(plan=Plan.BUSINESS), region="ap-south")
    frankfurt = create(service, make_account(plan=Plan.BUSINESS), region="eu-central")
    mumbai = create(service, make_account(plan=Plan.ENTERPRISE), region=Region.AP_SOUTH)
    assert (frankfurt.region, mumbai.region) == (Region.EU_CENTRAL, Region.AP_SOUTH)
    with pytest.raises(ConflictError):
        service.change_region(frankfurt.id, "us-east")
    assert service.change_region(frankfurt.id, "eu-central").region is Region.EU_CENTRAL


def test_storage_emails_at_90_and_100_percent_then_uploads_are_blocked(
        service, make_account, uid, notifier):
    """Free has 2 GB (2,048 MB) and accepts files up to 250 MB."""
    account = make_account(plan=Plan.FREE)
    workspace, member = create(service, account), uid(account, "member")
    for _ in range(7):                                              # 1,750 MB = 85.4%
        service.upload_file(account, workspace.id, member, 250)
    assert notifier.sent == []

    warned = service.upload_file(account, workspace.id, member, 100)    # 1,850 MB = 90.3%
    full = service.upload_file(account, workspace.id, member, 198)      # 2,048 MB = 100%

    assert (warned.after, full.after) == (StorageLevel.WARNING, StorageLevel.FULL)
    recipients = ["owner@example.com", "admin@example.com"]
    assert [(t, to) for t, to, _ in notifier.sent] == [
        ("storage_warning", recipients), ("storage_full", recipients)]
    with pytest.raises(LimitExceededError):
        service.upload_file(account, workspace.id, member, 1)
    service.delete_file(account, workspace.id, member, 250)             # frees space
    service.upload_file(account, workspace.id, member, 1)


def test_usage_is_summed_over_all_workspaces_of_the_account(service, make_account):
    account = make_account(plan=Plan.PRO, seats=1)                      # 50 GB
    first, second = create(service, account, "One"), create(service, account, "Two")
    first.storage_used_mb = 30 * GB
    second.storage_used_mb = 19 * GB
    assert service.storage_used_mb(account.id) == 49 * GB
    with pytest.raises(LimitExceededError):
        service.upload_file(account, second.id, account.owner_id, 2 * GB)


def test_upload_needs_projects_edit_and_an_own_workspace(service, make_account, uid):
    account, other = make_account(), make_account()
    workspace = create(service, account)
    for name in ("guest", "billing"):
        with pytest.raises(PermissionDeniedError):
            service.upload_file(account, workspace.id, uid(account, name), 10)
    with pytest.raises(NotFoundError):
        service.upload_file(other, workspace.id, other.owner_id, 10)
    with pytest.raises(NotFoundError):
        service.get("ws_ZZZZZZ")


def test_storage_packs_are_a_billing_action(service, make_account, uid):
    account = make_account(plan=Plan.PRO, seats=1)
    with pytest.raises(PermissionDeniedError):
        service.add_storage_packs(account, uid(account, "admin"))
    assert service.add_storage_packs(account, uid(account, "billing")) == 150 * GB


def test_export_flow_emails_the_requester_and_writes_audit_events(
        service, make_account, uid, notifier, audit):
    account = make_account()
    workspace, admin = create(service, account), uid(account, "admin")

    export = service.start_export(account, workspace.id, admin)
    with pytest.raises(ConflictError):
        service.start_export(account, workspace.id, account.owner_id)   # one at a time
    service.run_export(export.id)
    service.complete_export(account, export.id)
    url = service.download_export(account, export.id, account.owner_id)

    assert export.status is ExportStatus.READY and url == export.download_url
    template, to, context = notifier.sent[-1]
    assert (template, to) == ("export_ready", ["admin@example.com"])
    assert context["export_id"] == export.id and context["download_url"] == url
    assert audit.events == [
        ("export.started", admin, account.id, workspace.id, {"export_id": export.id}),
        ("export.downloaded", account.owner_id, account.id, workspace.id,
         {"export_id": export.id}),
    ]


def test_members_cannot_export_or_download(service, make_account, uid):
    account = make_account()
    workspace = create(service, account)
    with pytest.raises(PermissionDeniedError):
        service.start_export(account, workspace.id, uid(account, "member"))
    export = service.start_export(account, workspace.id, account.owner_id)
    with pytest.raises(PermissionDeniedError):
        service.download_export(account, export.id, uid(account, "member"))
    with pytest.raises(NotFoundError):
        service.get_export("exp_ZZZZZZZZ")


def test_read_only_accounts_can_export_but_closed_ones_cannot(service, make_account):
    account = make_account()
    workspace = create(service, account)
    account.state = AccountState.READ_ONLY
    assert service.start_export(account, workspace.id, account.owner_id).is_active
    account.state = AccountState.CLOSED
    with pytest.raises(AccountReadOnlyError):
        service.start_export(account, workspace.id, account.owner_id)


def test_refresh_job_times_out_long_exports_and_expires_old_links(service, make_account, clock):
    account = make_account(plan=Plan.BUSINESS)
    first, second = create(service, account, "One"), create(service, account, "Two")
    ready = service.start_export(account, first.id, account.owner_id)
    service.run_export(ready.id)
    service.complete_export(account, ready.id)
    stuck = service.start_export(account, second.id, account.owner_id)
    service.run_export(stuck.id)

    clock.advance(hours=24)
    assert service.refresh_exports() == []
    clock.advance(hours=1)
    assert service.refresh_exports() == [stuck] and stuck.status is ExportStatus.FAILED
    clock.advance(days=6, hours=23)                                     # day 7 for the link
    assert service.refresh_exports() == [ready] and ready.status is ExportStatus.EXPIRED
    with pytest.raises(ConflictError):
        service.download_export(account, ready.id, account.owner_id)

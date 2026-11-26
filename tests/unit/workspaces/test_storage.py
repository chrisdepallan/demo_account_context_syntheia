"""Storage: limits, 90% warning, 100% upload block, max upload size, storage packs."""

from __future__ import annotations

import pytest

from acme_cloud.accounts.plans import GB, TB
from acme_cloud.common.enums import AccountState, Plan
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, LimitExceededError, PlanRequiredError, ValidationError,
)
from acme_cloud.workspaces import storage
from acme_cloud.workspaces.storage import StorageLevel

FREE_LIMIT = 2 * GB   # 2,048 MB


@pytest.mark.parametrize(
    ("used", "limit", "level"),
    [(0, 1000, StorageLevel.OK),
     (890, 1000, StorageLevel.OK),        # 89%
     (899, 1000, StorageLevel.OK),
     (900, 1000, StorageLevel.WARNING),   # exactly 90%
     (999, 1000, StorageLevel.WARNING),
     (1000, 1000, StorageLevel.FULL),     # exactly 100%
     (1200, 1000, StorageLevel.FULL),     # over, for example after a downgrade
     (1843, FREE_LIMIT, StorageLevel.OK),         # 89.99% of 2 GB
     (1844, FREE_LIMIT, StorageLevel.WARNING)],   # 90.04% of 2 GB
)
def test_storage_level_thresholds(used, limit, level):
    assert storage.storage_level(used, limit) is level


def test_usage_ratio():
    assert storage.usage_ratio(512, FREE_LIMIT) == 0.25
    with pytest.raises(ValidationError):
        storage.usage_ratio(1, 0)


@pytest.mark.parametrize(
    ("plan", "seats", "packs", "limit_mb"),
    [(Plan.FREE, 1, 0, 2 * GB), (Plan.STARTER, 2, 0, 20 * GB), (Plan.PRO, 2, 0, 100 * GB),
     (Plan.PRO, 2, 1, 200 * GB), (Plan.BUSINESS, 3, 0, 600 * GB), (Plan.ENTERPRISE, 1, 0, TB)],
)
def test_account_storage_limit(make_account, plan, seats, packs, limit_mb):
    """Per-seat storage times seats, plus 100 GB per storage pack."""
    account = make_account(plan=plan, seats=seats, storage_packs=packs)
    assert storage.account_storage_limit_mb(account) == limit_mb


@pytest.mark.parametrize(
    ("plan", "max_mb"),
    [(Plan.FREE, 250), (Plan.STARTER, 250), (Plan.PRO, 5120), (Plan.BUSINESS, 5120),
     (Plan.ENTERPRISE, 5120)],
)
def test_max_upload_size_per_plan(plan, max_mb):
    """250 MB on Free and Starter, 5 GB on Pro and above; one MB more is refused."""
    assert storage.max_upload_mb(plan) == max_mb
    storage.check_upload(plan, max_mb, used_mb=0, limit_mb=TB)
    with pytest.raises(LimitExceededError) as caught:
        storage.check_upload(plan, max_mb + 1, used_mb=0, limit_mb=TB)
    assert caught.value.details["max_upload_mb"] == max_mb


def test_uploads_are_blocked_at_100_percent():
    with pytest.raises(LimitExceededError) as caught:
        storage.check_upload(Plan.FREE, 1, used_mb=FREE_LIMIT, limit_mb=FREE_LIMIT)
    assert caught.value.code == "ERR_LIMIT_EXCEEDED"


def test_uploads_still_work_in_the_warning_zone():
    storage.check_upload(Plan.FREE, 10, used_mb=1900, limit_mb=FREE_LIMIT)  # 92.8%


def test_a_file_may_fill_storage_exactly_but_not_exceed_it():
    storage.check_upload(Plan.FREE, 148, used_mb=1900, limit_mb=FREE_LIMIT)
    with pytest.raises(LimitExceededError):
        storage.check_upload(Plan.FREE, 149, used_mb=1900, limit_mb=FREE_LIMIT)


@pytest.mark.parametrize("size", [0, -5])
def test_file_size_must_be_positive(size):
    with pytest.raises(ValidationError):
        storage.check_upload(Plan.PRO, size, used_mb=0, limit_mb=50 * GB)


@pytest.mark.parametrize(
    ("used_before", "file_mb", "after", "template"),
    [(1000, 100, StorageLevel.OK, None),                   # 53.7%
     (1800, 44, StorageLevel.WARNING, "storage_warning"),  # crosses 90%
     (1900, 50, StorageLevel.WARNING, None),               # already warned
     (1900, 148, StorageLevel.FULL, "storage_full"),       # reaches 100%
     (1800, 248, StorageLevel.FULL, "storage_full")],      # jumps from ok to full
)
def test_upload_reports_the_email_to_send(make_account, make_workspace, used_before, file_mb,
                                          after, template):
    account = make_account(plan=Plan.FREE)
    workspace = make_workspace(account, used_mb=used_before)
    change = storage.record_upload(account, workspace, file_mb, account_used_mb=used_before)
    assert change.after is after
    assert change.notification == template
    assert change.used_mb == workspace.storage_used_mb == used_before + file_mb
    assert change.limit_mb == FREE_LIMIT


def test_refused_upload_changes_nothing(make_account, make_workspace):
    account = make_account(plan=Plan.FREE)
    workspace = make_workspace(account, used_mb=FREE_LIMIT)
    with pytest.raises(LimitExceededError):
        storage.record_upload(account, workspace, 1, account_used_mb=FREE_LIMIT)
    assert workspace.storage_used_mb == FREE_LIMIT


def test_files_can_be_deleted_when_storage_is_full(make_account, make_workspace):
    """At 100% uploads are blocked but existing files stay editable."""
    account = make_account(plan=Plan.FREE)
    workspace = make_workspace(account, used_mb=FREE_LIMIT)
    change = storage.record_delete(account, workspace, 300, account_used_mb=FREE_LIMIT)
    assert (change.before, change.after) == (StorageLevel.FULL, StorageLevel.OK)
    assert change.notification is None
    assert workspace.storage_used_mb == FREE_LIMIT - 300
    with pytest.raises(ValidationError):
        storage.record_delete(account, workspace, 5000, account_used_mb=workspace.storage_used_mb)


def test_read_only_account_cannot_upload(make_account, make_workspace):
    account = make_account(state=AccountState.READ_ONLY)
    with pytest.raises(AccountReadOnlyError):
        storage.record_upload(account, make_workspace(account), 10, account_used_mb=0)


def test_storage_pack_adds_100_gb_on_paid_plans(make_account):
    account = make_account(plan=Plan.STARTER, seats=1)
    assert storage.add_storage_packs(account) == 110 * GB
    assert storage.add_storage_packs(account, 2) == 310 * GB
    assert account.storage_packs == 3
    with pytest.raises(ValidationError):
        storage.add_storage_packs(account, 0)


def test_free_accounts_cannot_buy_storage_packs(make_account):
    account = make_account(plan=Plan.FREE)
    with pytest.raises(PlanRequiredError):
        storage.add_storage_packs(account)
    assert account.storage_packs == 0


def test_pack_cannot_be_removed_while_usage_needs_it(make_account):
    account = make_account(plan=Plan.PRO, seats=1, storage_packs=1)   # 150 GB
    with pytest.raises(ConflictError):
        storage.remove_storage_packs(account, 1, account_used_mb=60 * GB)
    assert storage.remove_storage_packs(account, 1, account_used_mb=50 * GB) == 50 * GB
    assert account.storage_packs == 0
    with pytest.raises(ValidationError):
        storage.remove_storage_packs(account, 1, account_used_mb=0)

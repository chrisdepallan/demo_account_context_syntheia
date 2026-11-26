"""Storage usage, limits and upload checks. All sizes are whole MB.

Rules (1 GB = 1,024 MB, 1 TB = 1,024 GB):

- **Storage limit** of an account: Free 2 GB in total; Starter 10 GB,
  Pro 50 GB, Business 200 GB and Enterprise 1 TB **per seat**; plus 100 GB
  for every storage pack. Usage is the sum over all workspaces of the account.
- **Warning at 90%**: when usage reaches 90% of the limit, the Owner and
  Admins get the ``storage_warning`` email.
- **Block at 100%**: when usage reaches 100%, new uploads fail with
  ``ERR_LIMIT_EXCEEDED`` and the Owner and Admins get ``storage_full``.
  Existing files stay editable and can be deleted to free space. An upload
  that would push usage past 100% is refused as well.
- **Max file upload**: 250 MB on Free and Starter, 5 GB on Pro, Business and
  Enterprise.
- **Storage packs**: 100 GB for $10/month each, any paid plan, any number of
  packs. Free accounts cannot buy packs (``ERR_PLAN_REQUIRED``). A pack
  cannot be removed while usage would exceed the smaller limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from acme_cloud.accounts import plans
from acme_cloud.accounts.models import Account
from acme_cloud.accounts.state_machine import require_editable
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import ConflictError, LimitExceededError, PlanRequiredError, ValidationError
from acme_cloud.workspaces.models import Workspace


class StorageLevel(str, Enum):
    """How full an account's storage is."""

    OK = "ok"            # below 90%
    WARNING = "warning"  # 90% up to, not including, 100%
    FULL = "full"        # 100% or more: uploads blocked

    @property
    def severity(self) -> int:
        return (StorageLevel.OK, StorageLevel.WARNING, StorageLevel.FULL).index(self)


#: Email template sent when an upload lifts the account into a level.
LEVEL_TEMPLATES = {StorageLevel.WARNING: "storage_warning", StorageLevel.FULL: "storage_full"}


@dataclass(frozen=True)
class StorageChange:
    """Account storage before and after an upload or delete."""

    before: StorageLevel
    after: StorageLevel
    used_mb: int
    limit_mb: int

    @property
    def notification(self) -> str | None:
        """``storage_warning`` or ``storage_full`` when the level rose, else ``None``."""
        if self.after.severity > self.before.severity:
            return LEVEL_TEMPLATES[self.after]
        return None


def account_storage_limit_mb(account: Account) -> int:
    """Total storage of the account in MB: plan storage plus storage packs."""
    return plans.storage_limit_mb(account.plan, account.seats, account.storage_packs)


def max_upload_mb(plan: Plan) -> int:
    """Largest single file ``plan`` accepts: 250 MB or 5 GB (5,120 MB)."""
    return plans.limits_for(plan).max_upload_mb


def usage_ratio(used_mb: int, limit_mb: int) -> float:
    """Used storage as a fraction of the limit (1.0 = 100%)."""
    if limit_mb <= 0:
        raise ValidationError("the storage limit must be positive")
    return used_mb / limit_mb


def storage_level(used_mb: int, limit_mb: int) -> StorageLevel:
    """``warning`` from 90%, ``full`` from 100%, otherwise ``ok``."""
    ratio = usage_ratio(used_mb, limit_mb)
    if ratio >= plans.STORAGE_BLOCK_RATIO:
        return StorageLevel.FULL
    if ratio >= plans.STORAGE_WARNING_RATIO:
        return StorageLevel.WARNING
    return StorageLevel.OK


def check_upload(plan: Plan, file_mb: int, used_mb: int, limit_mb: int) -> None:
    """Raise unless a file of ``file_mb`` may be uploaded.

    ValidationError for a non-positive size; LimitExceededError when the file
    is over the plan's max upload size, storage is already at 100%, or the
    file does not fit in the space that is left.
    """
    if file_mb <= 0:
        raise ValidationError("the file size must be positive")
    biggest = max_upload_mb(plan)
    if file_mb > biggest:
        raise LimitExceededError(
            f"the {plan.value} plan accepts files up to {biggest} MB",
            max_upload_mb=biggest, file_mb=file_mb,
        )
    if storage_level(used_mb, limit_mb) is StorageLevel.FULL:
        raise LimitExceededError(
            "storage is full; uploads are blocked until space is freed or added",
            used_mb=used_mb, limit_mb=limit_mb,
        )
    if used_mb + file_mb > limit_mb:
        raise LimitExceededError(
            "the file does not fit in the remaining storage",
            used_mb=used_mb, limit_mb=limit_mb, file_mb=file_mb,
        )


def record_upload(account: Account, workspace: Workspace, file_mb: int,
                  account_used_mb: int) -> StorageChange:
    """Check and book an upload. ``account_used_mb`` is usage over all workspaces."""
    require_editable(account)
    limit = account_storage_limit_mb(account)
    check_upload(account.plan, file_mb, account_used_mb, limit)
    workspace.storage_used_mb += file_mb
    used = account_used_mb + file_mb
    return StorageChange(storage_level(account_used_mb, limit), storage_level(used, limit),
                         used, limit)


def record_delete(account: Account, workspace: Workspace, file_mb: int,
                  account_used_mb: int) -> StorageChange:
    """Book a deleted file. Allowed even when storage is full."""
    require_editable(account)
    if file_mb <= 0 or file_mb > workspace.storage_used_mb:
        raise ValidationError("the file size does not match the workspace's usage")
    limit = account_storage_limit_mb(account)
    workspace.storage_used_mb -= file_mb
    used = account_used_mb - file_mb
    return StorageChange(storage_level(account_used_mb, limit), storage_level(used, limit),
                         used, limit)


def add_storage_packs(account: Account, count: int = 1) -> int:
    """Add 100 GB packs (paid plans only). Returns the new limit in MB."""
    if count < 1:
        raise ValidationError("add at least one storage pack")
    if not account.plan.is_paid:
        raise PlanRequiredError("storage packs need a paid plan",
                                minimum_plan=Plan.STARTER.value, current_plan=account.plan.value)
    account.storage_packs += count
    return account_storage_limit_mb(account)


def remove_storage_packs(account: Account, count: int, account_used_mb: int) -> int:
    """Remove packs unless usage would exceed the smaller limit. Returns the new limit."""
    if count < 1 or count > account.storage_packs:
        raise ValidationError("the account does not have that many storage packs")
    new_limit = plans.storage_limit_mb(account.plan, account.seats, account.storage_packs - count)
    if account_used_mb > new_limit:
        raise ConflictError("free up storage before removing the pack",
                            used_mb=account_used_mb, limit_mb=new_limit)
    account.storage_packs -= count
    return new_limit

"""``WorkspaceService``: in-memory facade over the workspace rules.

- **Workspace count per plan**: Free 1, Starter 1, Pro 3, Business 10,
  Enterprise unlimited. One more raises ``ERR_LIMIT_EXCEEDED``.
- Only the **Owner or an Admin** creates workspaces, and only while the
  account is editable (``trialing``, ``active``, ``past_due``).
- **Region**: ``us-east`` by default; ``eu-central`` needs Business,
  ``ap-south`` needs Enterprise; fixed at creation.
- **Storage**: usage is summed over the account's workspaces. Uploading
  needs ``projects.edit``. Crossing 90% emails ``storage_warning`` and
  reaching 100% emails ``storage_full`` to the Owner and Admins; at 100%
  uploads are blocked. Storage packs (100 GB each) need ``billing.manage``.
- **Export**: Owner or Admin; one running export per workspace; the
  requester gets ``export_ready``; the link is valid 7 days; an export
  running longer than 24 hours is ``failed``. Exports also work on a
  ``read_only`` account, but not on a ``closed`` or ``deleted`` one.

Audit events written: ``export.started`` and ``export.downloaded``. The
optional ``notifier`` and ``audit`` collaborators are duck-typed, as in
``AccountService``.
"""

from __future__ import annotations

from typing import Any

from acme_cloud.accounts import permissions
from acme_cloud.accounts.models import Account
from acme_cloud.accounts.plans import limits_for
from acme_cloud.accounts.state_machine import require_editable
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Region, Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, LimitExceededError, NotFoundError, PermissionDeniedError,
    ValidationError,
)
from acme_cloud.common.ids import IdGenerator
from acme_cloud.workspaces import export as export_rules
from acme_cloud.workspaces import regions, storage
from acme_cloud.workspaces.models import Export, Workspace

#: Roles that may create a workspace.
WORKSPACE_CREATOR_ROLES = (Role.OWNER, Role.ADMIN)


class WorkspaceService:
    """Creates workspaces and applies region, storage and export rules."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None,
                 notifier: Any = None, audit: Any = None) -> None:
        self.clock = clock
        self.ids = ids or IdGenerator()
        self.notifier = notifier
        self.audit = audit
        self.workspaces: dict[str, Workspace] = {}
        self.exports: dict[str, Export] = {}

    # -- workspaces ------------------------------------------------------
    def get(self, workspace_id: str) -> Workspace:
        """Return the workspace or raise NotFoundError."""
        if workspace_id not in self.workspaces:
            raise NotFoundError(f"workspace {workspace_id} not found", workspace_id=workspace_id)
        return self.workspaces[workspace_id]

    def _owned(self, account: Account, workspace_id: str) -> Workspace:
        workspace = self.get(workspace_id)
        if workspace.account_id != account.id:
            raise NotFoundError(f"workspace {workspace_id} not found", workspace_id=workspace_id)
        return workspace

    def list_for_account(self, account_id: str) -> list[Workspace]:
        """Workspaces of one account, oldest first."""
        return [w for w in self.workspaces.values() if w.account_id == account_id]

    def create_workspace(self, account: Account, actor_id: str, name: str,
                         region: str | Region | None = None) -> Workspace:
        """Create a workspace, within the plan's workspace count and regions."""
        require_editable(account)
        role = account.member(actor_id).role
        if role not in WORKSPACE_CREATOR_ROLES:
            raise PermissionDeniedError("only the Owner or an Admin can create a workspace",
                                        role=role.value)
        if not name.strip():
            raise ValidationError("the workspace name is required")
        chosen = regions.parse_region(region)
        regions.require_region(account.plan, chosen)
        limit = limits_for(account.plan).max_workspaces
        current = len(self.list_for_account(account.id))
        if limit is not None and current >= limit:
            raise LimitExceededError(
                f"the {account.plan.value} plan allows {limit} workspace(s)",
                limit=limit, current=current, plan=account.plan.value,
            )
        workspace = Workspace(id=self.ids.new("ws"), account_id=account.id, name=name.strip(),
                              region=chosen, created_at=self.clock.now(), created_by=actor_id)
        self.workspaces[workspace.id] = workspace
        return workspace

    def change_region(self, workspace_id: str, region: str | Region) -> Workspace:
        """Always refused (ConflictError) unless ``region`` is the current one."""
        workspace = self.get(workspace_id)
        regions.assert_region_unchanged(workspace, region)
        return workspace

    # -- storage ---------------------------------------------------------
    def storage_used_mb(self, account_id: str) -> int:
        """Storage used by all workspaces of the account, in MB."""
        return sum(w.storage_used_mb for w in self.list_for_account(account_id))

    def upload_file(self, account: Account, workspace_id: str, actor_id: str,
                    file_mb: int) -> storage.StorageChange:
        """Book an upload; emails the Owner and Admins at 90% and at 100%."""
        permissions.require(account.member(actor_id).role, permissions.PROJECTS_EDIT)
        workspace = self._owned(account, workspace_id)
        change = storage.record_upload(account, workspace, file_mb,
                                       self.storage_used_mb(account.id))
        if change.notification and self.notifier is not None:
            self.notifier.send(change.notification,
                               account.emails_for_roles(Role.OWNER, Role.ADMIN),
                               account_id=account.id, used_mb=change.used_mb,
                               limit_mb=change.limit_mb)
        return change

    def delete_file(self, account: Account, workspace_id: str, actor_id: str,
                    file_mb: int) -> storage.StorageChange:
        """Book a deleted file; works even when storage is full."""
        permissions.require(account.member(actor_id).role, permissions.PROJECTS_EDIT)
        workspace = self._owned(account, workspace_id)
        return storage.record_delete(account, workspace, file_mb,
                                     self.storage_used_mb(account.id))

    def add_storage_packs(self, account: Account, actor_id: str, count: int = 1) -> int:
        """Owner or Billing admin adds 100 GB packs. Returns the new limit in MB."""
        permissions.require(account.member(actor_id).role, permissions.BILLING_MANAGE)
        require_editable(account)
        return storage.add_storage_packs(account, count)

    # -- exports ---------------------------------------------------------
    def get_export(self, export_id: str) -> Export:
        """Return the export (with clock rules applied) or raise NotFoundError."""
        if export_id not in self.exports:
            raise NotFoundError(f"export {export_id} not found", export_id=export_id)
        return export_rules.refresh(self.exports[export_id], self.clock)

    def start_export(self, account: Account, workspace_id: str, actor_id: str) -> Export:
        """Queue an export; ConflictError if one is already queued or running."""
        if not account.state.can_log_in:
            raise AccountReadOnlyError(f"account is {account.state.value}",
                                       state=account.state.value)
        workspace = self._owned(account, workspace_id)
        export = export_rules.request_export(
            workspace, self.exports.values(), actor_id, account.member(actor_id).role,
            self.clock, self.ids,
        )
        self.exports[export.id] = export
        if self.audit is not None:
            self.audit.record("export.started", actor_id, account.id, workspace.id,
                              export_id=export.id)
        return export

    def run_export(self, export_id: str) -> Export:
        """Worker hook: ``queued`` -> ``running``."""
        return export_rules.start(self.get_export(export_id), self.clock)

    def complete_export(self, account: Account, export_id: str) -> Export:
        """Worker hook: ``running`` -> ``ready``; emails ``export_ready`` to the requester."""
        export = export_rules.complete(self.get_export(export_id), self.clock)
        requester = account.members.get(export.requested_by)
        if self.notifier is not None and requester is not None:
            self.notifier.send("export_ready", [requester.email], account_id=account.id,
                               export_id=export.id, download_url=export.download_url,
                               expires_at=export.expires_at.isoformat())
        return export

    def download_export(self, account: Account, export_id: str, actor_id: str) -> str:
        """Return the download URL of a ready export and audit the download."""
        permissions.require(account.member(actor_id).role, permissions.WORKSPACE_EXPORT)
        export = self.get_export(export_id)
        if export.account_id != account.id:
            raise NotFoundError(f"export {export_id} not found", export_id=export_id)
        url = export_rules.download_link(export, self.clock)
        if self.audit is not None:
            self.audit.record("export.downloaded", actor_id, account.id, export.workspace_id,
                              export_id=export.id)
        return url

    def refresh_exports(self) -> list[Export]:
        """Periodic job: time out exports over 24 hours and expire 7-day-old links."""
        changed = []
        for export in self.exports.values():
            before = export.status
            if export_rules.refresh(export, self.clock).status is not before:
                changed.append(export)
        return changed

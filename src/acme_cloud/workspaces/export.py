"""Workspace export.

The Owner or an Admin (permission ``workspace.export``) starts an export from
Settings -> Workspace -> Export. The result is a ZIP with JSON and the
original files.

Rules:

- Statuses: ``queued`` -> ``running`` -> ``ready`` -> ``expired``, or
  ``failed`` from ``queued``/``running``.
- **One running export per workspace.** Asking for a second export while one
  is queued or running raises ``ERR_CONFLICT`` (HTTP 409).
- The download **link is valid for 7 days** after the export is ready; after
  that the export is ``expired`` and a new one must be started.
- An export that runs **longer than 24 hours** is marked ``failed`` (reason
  ``timeout``). At exactly 24 hours it is still running.

``refresh`` applies the two clock rules (timeout and link expiry); every
other function calls it first, so a stale status is never acted on.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from acme_cloud.accounts import permissions
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import ConflictError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.workspaces.models import Export, ExportStatus, Workspace

#: Days the download link of a ready export stays valid.
EXPORT_LINK_TTL_DAYS = 7
#: An export running longer than this many hours is marked failed.
EXPORT_TIMEOUT_HOURS = 24
TIMEOUT_REASON = "timeout"
DOWNLOAD_URL = "https://app.acme-cloud.example/exports/{export_id}/download"


def refresh(export: Export, clock: Clock) -> Export:
    """Apply the 24-hour timeout and the 7-day link expiry to ``export``."""
    now = clock.now()
    if (export.status is ExportStatus.RUNNING and export.started_at is not None
            and now - export.started_at > timedelta(hours=EXPORT_TIMEOUT_HOURS)):
        export.status = ExportStatus.FAILED
        export.failure_reason = TIMEOUT_REASON
        export.finished_at = now
    elif (export.status is ExportStatus.READY and export.expires_at is not None
            and now >= export.expires_at):
        export.status = ExportStatus.EXPIRED
        export.download_url = None
    return export


def request_export(
    workspace: Workspace, existing: Iterable[Export], requested_by: str, role: Role,
    clock: Clock, ids: IdGenerator,
) -> Export:
    """Queue a new export of ``workspace``.

    ``existing`` are the exports already known. PermissionDeniedError unless
    ``role`` is Owner or Admin; ConflictError while another export of the
    same workspace is queued or running.
    """
    permissions.require(role, permissions.WORKSPACE_EXPORT)
    for other in existing:
        if other.workspace_id == workspace.id and refresh(other, clock).is_active:
            raise ConflictError(
                "an export of this workspace is already running",
                workspace_id=workspace.id, export_id=other.id,
            )
    return Export(
        id=ids.new("exp"), workspace_id=workspace.id, account_id=workspace.account_id,
        requested_by=requested_by, requested_at=clock.now(),
    )


def _require_status(export: Export, expected: ExportStatus, action: str) -> None:
    if export.status is not expected:
        raise ConflictError(
            f"cannot {action} an export that is {export.status.value}",
            export_id=export.id, status=export.status.value,
        )


def start(export: Export, clock: Clock) -> Export:
    """A worker picks the export up: ``queued`` -> ``running``."""
    _require_status(export, ExportStatus.QUEUED, "start")
    export.status = ExportStatus.RUNNING
    export.started_at = clock.now()
    return export


def complete(export: Export, clock: Clock) -> Export:
    """The ZIP is built: ``running`` -> ``ready`` with a 7-day download link."""
    _require_status(refresh(export, clock), ExportStatus.RUNNING, "complete")
    now = clock.now()
    export.status = ExportStatus.READY
    export.finished_at = now
    export.expires_at = now + timedelta(days=EXPORT_LINK_TTL_DAYS)
    export.download_url = DOWNLOAD_URL.format(export_id=export.id)
    return export


def fail(export: Export, clock: Clock, reason: str) -> Export:
    """The worker gave up: ``queued`` or ``running`` -> ``failed``."""
    if not refresh(export, clock).is_active:
        _require_status(export, ExportStatus.RUNNING, "fail")
    export.status = ExportStatus.FAILED
    export.failure_reason = reason
    export.finished_at = clock.now()
    return export


def download_link(export: Export, clock: Clock) -> str:
    """Return the download URL of a ready export; ConflictError otherwise."""
    _require_status(refresh(export, clock), ExportStatus.READY, "download")
    assert export.download_url is not None
    return export.download_url

"""Data models of the workspaces package.

A **workspace** belongs to one account and lives in one data region
(``us-east``, ``eu-central`` or ``ap-south``). The region is chosen when the
workspace is created and never changes. Each workspace tracks how much
storage its files use, in MB (1 GB = 1,024 MB); the storage *limit* belongs
to the account (plan storage per seat plus storage packs).

An **export** is a ZIP with JSON and the original files of one workspace.
Export statuses:

- ``queued``: requested, waiting for a worker.
- ``running``: being built. Only one export per workspace can be queued or
  running at a time.
- ``ready``: finished; the download link is valid for 7 days.
- ``expired``: the 7-day link has passed.
- ``failed``: the worker reported an error, or the export ran longer than
  24 hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from acme_cloud.common.enums import Region


class ExportStatus(str, Enum):
    """Lifecycle of a workspace export."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"

    @property
    def is_active(self) -> bool:
        """Queued and running exports block a new export of the same workspace."""
        return self in (ExportStatus.QUEUED, ExportStatus.RUNNING)


@dataclass
class Workspace:
    """A workspace of an account, pinned to one region."""

    id: str
    account_id: str
    name: str
    region: Region
    created_at: datetime
    created_by: str
    storage_used_mb: int = 0


@dataclass
class Export:
    """One export job of a workspace."""

    id: str
    workspace_id: str
    account_id: str
    requested_by: str
    requested_at: datetime
    status: ExportStatus = ExportStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None
    download_url: str | None = None
    failure_reason: str | None = None

    @property
    def is_active(self) -> bool:
        """True while the export is queued or running."""
        return self.status.is_active

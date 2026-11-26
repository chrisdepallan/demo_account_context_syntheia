"""Ownership transfer.

An account has exactly one Owner. The Owner hands the account over from
Settings -> Account -> Transfer ownership:

1. Only the Owner can start a transfer (permission ``account.transfer``).
2. The target must be an **existing Admin** of the same account. Members,
   Billing admins and guests must be made Admin first.
3. The new Owner must **accept within 7 days**; after that the request
   expires and nothing changes.
4. On acceptance the target becomes Owner and the **previous Owner becomes
   an Admin**. No seat is added or freed.

Only one request can be pending at a time; the Owner can cancel it. If the
target stops being an Admin (or is removed) before accepting, the request can
no longer be accepted. A closed or deleted account cannot be transferred.

When the Owner cannot be reached at all, support runs a manual process that
takes up to 5 business days; that process is outside this module.
"""

from __future__ import annotations

from datetime import timedelta

from acme_cloud.accounts import permissions
from acme_cloud.accounts.models import (
    TRANSFER_ACCEPTED, TRANSFER_CANCELLED, TRANSFER_EXPIRED, TRANSFER_PENDING,
    Account, OwnershipTransfer,
)
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, NotFoundError, PermissionDeniedError, ValidationError,
)
from acme_cloud.common.ids import IdGenerator

#: Days the chosen Admin has to accept an ownership transfer.
OWNERSHIP_TRANSFER_TTL_DAYS = 7


def _require_open(account: Account) -> None:
    if not account.state.can_log_in:
        raise AccountReadOnlyError(
            f"account is {account.state.value}; ownership cannot be transferred",
            state=account.state.value,
        )


def expire_if_stale(account: Account, clock: Clock) -> bool:
    """Mark the pending request ``expired`` once 7 days have passed. True if it did."""
    transfer = account.pending_transfer
    if transfer is None or transfer.status != TRANSFER_PENDING or not transfer.is_expired(clock.now()):
        return False
    transfer.status = TRANSFER_EXPIRED
    account.pending_transfer = None
    return True


def request_transfer(
    account: Account, actor_id: str, target_user_id: str, clock: Clock, ids: IdGenerator,
) -> OwnershipTransfer:
    """Ask an existing Admin to take over the account. Valid for 7 days."""
    _require_open(account)
    permissions.require(account.member(actor_id).role, permissions.ACCOUNT_TRANSFER)
    target = account.member(target_user_id)
    if target.role is not Role.ADMIN:
        raise ValidationError(
            "ownership can only be transferred to an existing Admin",
            target_role=target.role.value,
        )
    expire_if_stale(account, clock)
    if account.pending_transfer is not None:
        raise ConflictError(
            "an ownership transfer is already pending; cancel it first",
            transfer_id=account.pending_transfer.id,
        )
    now = clock.now()
    transfer = OwnershipTransfer(
        id=ids.new("tr"), account_id=account.id, from_user_id=actor_id,
        to_user_id=target_user_id, requested_at=now,
        expires_at=now + timedelta(days=OWNERSHIP_TRANSFER_TTL_DAYS),
    )
    account.pending_transfer = transfer
    return transfer


def accept_transfer(account: Account, user_id: str, clock: Clock) -> OwnershipTransfer:
    """The chosen Admin accepts: they become Owner, the previous Owner becomes Admin."""
    _require_open(account)
    transfer = account.pending_transfer
    if transfer is None:
        raise NotFoundError("there is no pending ownership transfer")
    if user_id != transfer.to_user_id:
        raise PermissionDeniedError("only the chosen Admin can accept this transfer")
    if expire_if_stale(account, clock):
        raise ConflictError(
            f"the transfer request expired after {OWNERSHIP_TRANSFER_TTL_DAYS} days",
            expired_at=transfer.expires_at.isoformat(),
        )
    target = account.members.get(user_id)
    if target is None or target.role is not Role.ADMIN:
        transfer.status = TRANSFER_CANCELLED
        account.pending_transfer = None
        raise ConflictError("the chosen member is no longer an Admin of this account")

    previous_owner = account.owner
    previous_owner.role = Role.ADMIN
    target.role = Role.OWNER
    account.owner_id = target.user_id
    transfer.status = TRANSFER_ACCEPTED
    transfer.completed_at = clock.now()
    account.pending_transfer = None
    return transfer


def cancel_transfer(account: Account, actor_id: str) -> OwnershipTransfer:
    """The Owner withdraws the pending request."""
    permissions.require(account.member(actor_id).role, permissions.ACCOUNT_TRANSFER)
    transfer = account.pending_transfer
    if transfer is None:
        raise NotFoundError("there is no pending ownership transfer")
    transfer.status = TRANSFER_CANCELLED
    account.pending_transfer = None
    return transfer

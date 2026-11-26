"""Member management: adding, removing and changing roles.

Rules implemented here:

- **Member limit per plan** (people who use a seat, so everyone except
  guests): Free 3, Starter 10, Pro 100, Business 500, Enterprise unlimited.
  Going over raises ``ERR_LIMIT_EXCEEDED``.
- **Guest limit**: guests do not use seats. Each paid seat allows 5 guests;
  a Free account allows 5 guests in total.
- **Seats**: when a seat-using member is added and no paid seat is free, the
  seat count grows by one (billing charges it at once, prorated by day).
  Removing a seat-using member frees one seat, which billing credits on the
  next invoice, prorated by day. ``seat_credit`` returns the numbers billing
  needs; this package never charges anything itself.
- **Exactly one Owner**: the Owner cannot be removed or demoted, and nobody
  can be promoted to Owner here. Ownership only moves through an ownership
  transfer (see ``ownership``).
- **Removing a member**: needs ``members.manage`` (Owner or Admin). Access
  ends immediately and the removed member's content is reassigned to the
  person who removed them. Nobody can remove themselves.
- New members and role changes need an editable account (``trialing``,
  ``active`` or ``past_due``). Removal also works in ``read_only`` so a
  customer can cut seats, but not in ``closed`` or ``deleted``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from acme_cloud.accounts import permissions, plans
from acme_cloud.accounts.models import Account, Member
from acme_cloud.accounts.state_machine import require_editable
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    AccountReadOnlyError, ConflictError, LimitExceededError, ValidationError,
)
from acme_cloud.common.money import Money


@dataclass(frozen=True)
class RemovalResult:
    """What happened when a member was removed."""

    member: Member
    removed_at: datetime
    content_reassigned_to: str
    reassigned_content_ids: tuple[str, ...]
    seats_freed: int


@dataclass(frozen=True)
class RoleChange:
    """Result of a role change. ``seats_delta`` is +1, 0 or -1."""

    user_id: str
    old_role: Role
    new_role: Role
    seats_delta: int


@dataclass(frozen=True)
class SeatCredit:
    """Numbers billing needs to credit freed seats on the next invoice."""

    seats_freed: int
    days_remaining: int
    days_in_period: int
    amount: Money | None  # None on Enterprise, where pricing is custom


def member_limit(plan: Plan) -> int | None:
    """Seat-using members allowed on ``plan``; ``None`` means unlimited."""
    return plans.limits_for(plan).max_members


def check_member_capacity(account: Account, extra: int = 1, reserved: int = 0) -> None:
    """Raise LimitExceededError if ``extra`` more seat-using members do not fit.

    ``reserved`` counts places already promised, such as pending invitations.
    """
    limit = member_limit(account.plan)
    if limit is not None and account.seat_member_count + reserved + extra > limit:
        raise LimitExceededError(
            f"the {account.plan.value} plan allows {limit} members",
            limit=limit, current=account.seat_member_count, plan=account.plan.value,
        )


def check_guest_capacity(account: Account, extra: int = 1, reserved: int = 0) -> None:
    """Raise LimitExceededError if ``extra`` more guests do not fit (5 per paid seat)."""
    limit = plans.guest_limit(account.plan, account.seats)
    if account.guest_count + reserved + extra > limit:
        raise LimitExceededError(
            f"this account allows {limit} guests", limit=limit, current=account.guest_count,
        )


def add_member(
    account: Account, user_id: str, email: str, role: Role, clock: Clock,
    invited_by: str | None = None,
) -> Member:
    """Add a member with ``role`` and return it. Grows the seat count if needed."""
    require_editable(account)
    if role is Role.OWNER:
        raise ValidationError("an account has exactly one Owner; use an ownership transfer")
    email = email.strip().lower()
    if user_id in account.members or account.find_member_by_email(email) is not None:
        raise ConflictError(f"{email} is already a member", email=email)
    if role is Role.GUEST:
        check_guest_capacity(account)
    else:
        check_member_capacity(account)
    member = Member(user_id=user_id, email=email, role=role, joined_at=clock.now(),
                    invited_by=invited_by)
    account.members[user_id] = member
    account.seats = max(account.seats, account.seat_member_count)
    return member


def remove_member(account: Account, actor_id: str, user_id: str, clock: Clock) -> RemovalResult:
    """Remove a member; their content goes to the remover and their seat is freed."""
    if not account.state.can_log_in:
        raise AccountReadOnlyError(f"account is {account.state.value}", state=account.state.value)
    permissions.require(account.member(actor_id).role, permissions.MEMBERS_MANAGE)
    member = account.member(user_id)
    if member.role is Role.OWNER:
        raise ConflictError("the Owner cannot be removed; transfer ownership first")
    if user_id == actor_id:
        raise ValidationError("you cannot remove yourself from the account")
    del account.members[user_id]
    reassigned = tuple(cid for cid, owner in account.content_owners.items() if owner == user_id)
    for content_id in reassigned:
        account.content_owners[content_id] = actor_id
    seats_freed = 0
    if member.uses_seat and account.seats > 1:
        account.seats -= 1
        seats_freed = 1
    return RemovalResult(member, clock.now(), actor_id, reassigned, seats_freed)


def change_role(account: Account, actor_id: str, user_id: str, new_role: Role) -> RoleChange:
    """Change a member's role. The Owner's role never changes here."""
    require_editable(account)
    permissions.require(account.member(actor_id).role, permissions.MEMBERS_MANAGE)
    member = account.member(user_id)
    if member.role is Role.OWNER:
        raise ConflictError("the Owner cannot be demoted; transfer ownership first")
    if new_role is Role.OWNER:
        raise ValidationError("an account has exactly one Owner; use an ownership transfer")
    old_role, seats_delta = member.role, 0
    if old_role is Role.GUEST and new_role is not Role.GUEST:
        check_member_capacity(account)
        member.role = new_role
        grown = max(account.seats, account.seat_member_count)
        seats_delta, account.seats = grown - account.seats, grown
    elif old_role is not Role.GUEST and new_role is Role.GUEST:
        check_guest_capacity(account)
        member.role = new_role
        if account.seats > 1:
            account.seats -= 1
            seats_delta = -1
    else:
        member.role = new_role
    return RoleChange(user_id, old_role, new_role, seats_delta)


def seat_credit(
    plan: Plan, seats_freed: int, removed_on: date, period_start: date, period_end: date,
    annual: bool = False, currency: str = "USD",
) -> SeatCredit:
    """Credit owed for freed seats: whole days remaining / days in the period.

    ``period_end`` is the first day of the next period. The amount is rounded
    half up to the cent. Billing applies it on the next invoice.
    """
    days_in_period = (period_end - period_start).days
    if days_in_period <= 0:
        raise ValidationError("the billing period must be at least one day long")
    days_remaining = min(max((period_end - removed_on).days, 0), days_in_period)
    amount = None
    if plan is not Plan.ENTERPRISE:
        price = plans.seat_price(plan, annual=annual, currency=currency) * seats_freed
        amount = price.prorate(days_remaining, days_in_period)
    return SeatCredit(seats_freed, days_remaining, days_in_period, amount)

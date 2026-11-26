"""Subscription changes: upgrade, downgrade, seats, cancel and period roll-over.

Rules implemented here:

- Prices per seat: Starter $8, Pro $20, Business $45 a month. Annual billing
  costs 10 times the monthly price (two months free). EUR uses the same
  numbers. Enterprise has a custom seat price on an annual contract.
- Upgrade: takes effect immediately; the prorated price difference is charged
  at once.
- Downgrade: takes effect at the end of the billing period. It is blocked
  (``ERR_LIMIT_EXCEEDED``) while members, workspaces or storage exceed the
  lower plan's limits, for example more than 10 members when going to Starter.
- Adding seats: charged immediately, prorated by day. Removing seats: credited
  on the next invoice, prorated by day.
- Cancel: the plan stays active until the end of the paid period, then the
  account moves to Free.

The functions change the ``Subscription`` they are given and return the
amount to charge or credit. Usage numbers (members, workspaces, storage) are
passed in by the caller; this module never looks at accounts or workspaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from acme_cloud.accounts.plans import limits_for, seat_price, storage_limit_mb
from acme_cloud.billing import proration
from acme_cloud.billing.models import BillingInterval, Subscription, add_months
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import ConflictError, LimitExceededError, ValidationError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.common.money import Money


@dataclass(frozen=True)
class PlanChange:
    """Result of a plan change request."""

    old_plan: Plan
    new_plan: Plan
    effective_at: datetime   # now for an upgrade, the period end for a downgrade
    charge: Money            # prorated amount due now; zero for a downgrade
    immediate: bool


def period_end_for(start: datetime, interval: BillingInterval) -> datetime:
    """End of the period that starts at ``start``: one month or one year later."""
    return add_months(start, interval.months)


def seat_price_for(sub: Subscription, plan: Plan | None = None) -> Money:
    """Price of one seat for one period of ``sub`` on ``plan`` (default: its own plan)."""
    plan = plan or sub.plan
    if plan is Plan.ENTERPRISE:
        if sub.custom_seat_price is None:
            raise ValidationError("Enterprise needs a custom seat price from the contract")
        return sub.custom_seat_price
    return seat_price(plan, annual=sub.interval is BillingInterval.ANNUAL, currency=sub.currency)


def period_total(sub: Subscription) -> Money:
    """Full price of one billing period: seat price times seats."""
    return seat_price_for(sub) * sub.seats


def _check_seats(plan: Plan, seats: int) -> None:
    if seats < 1:
        raise ValidationError("a subscription needs at least 1 seat")
    maximum = limits_for(plan).max_members
    if maximum is not None and seats > maximum:
        raise LimitExceededError(
            f"the {plan.value} plan allows at most {maximum} members", limit=maximum, seats=seats)


def new_subscription(
    ids: IdGenerator, account_id: str, plan: Plan, interval: BillingInterval, seats: int,
    now: datetime, currency: str = "USD", custom_seat_price: Money | None = None,
) -> Subscription:
    """Create a subscription whose first period starts at ``now``."""
    _check_seats(plan, seats)
    if plan is Plan.ENTERPRISE and interval is not BillingInterval.ANNUAL:
        raise ValidationError("Enterprise is sold on an annual contract only")
    sub = Subscription(
        id=ids.new("sub"), account_id=account_id, plan=plan, interval=interval, seats=seats,
        period_start=now, period_end=period_end_for(now, interval), currency=currency,
        custom_seat_price=custom_seat_price if plan is Plan.ENTERPRISE else None,
    )
    seat_price_for(sub)  # fails early when the Enterprise price is missing
    return sub


def _proration_days(sub: Subscription, now: datetime) -> tuple[int, int]:
    return (proration.days_remaining(now, sub.period_end),
            proration.days_in_period(sub.period_start, sub.period_end))


def upgrade(sub: Subscription, new_plan: Plan, now: datetime,
            custom_seat_price: Money | None = None) -> PlanChange:
    """Move to a higher plan now and return the prorated difference to charge."""
    if new_plan.rank <= sub.plan.rank:
        raise ValidationError("an upgrade must go to a higher plan")
    if new_plan is Plan.ENTERPRISE and sub.interval is not BillingInterval.ANNUAL:
        raise ValidationError("Enterprise is sold on an annual contract only")
    old_plan, old_price = sub.plan, seat_price_for(sub)
    if new_plan is Plan.ENTERPRISE:
        sub.custom_seat_price = custom_seat_price
    remaining, total = _proration_days(sub, now)
    charge = proration.upgrade_charge(
        old_price, seat_price_for(sub, new_plan), sub.seats, remaining, total)
    sub.plan, sub.pending_plan, sub.cancel_at_period_end = new_plan, None, False
    return PlanChange(old_plan, new_plan, effective_at=now, charge=charge, immediate=True)


def downgrade_blockers(sub: Subscription, new_plan: Plan, members: int, workspaces: int,
                       storage_used_mb: int, storage_packs: int = 0) -> list[str]:
    """Names of the limits of ``new_plan`` that current usage exceeds."""
    limits = limits_for(new_plan)
    blockers = []
    if limits.max_members is not None and members > limits.max_members:
        blockers.append("members")
    if limits.max_workspaces is not None and workspaces > limits.max_workspaces:
        blockers.append("workspaces")
    if storage_used_mb > storage_limit_mb(new_plan, sub.seats, storage_packs):
        blockers.append("storage")
    return blockers


def schedule_downgrade(sub: Subscription, new_plan: Plan, members: int, workspaces: int,
                       storage_used_mb: int, storage_packs: int = 0) -> PlanChange:
    """Book a downgrade for the end of the period; blocked while usage is over the limits."""
    if new_plan.rank >= sub.plan.rank:
        raise ValidationError("a downgrade must go to a lower plan")
    blockers = downgrade_blockers(sub, new_plan, members, workspaces, storage_used_mb, storage_packs)
    if blockers:
        raise LimitExceededError(
            f"usage exceeds the {new_plan.value} plan limits: {', '.join(blockers)}",
            blockers=blockers, plan=new_plan.value)
    sub.pending_plan = new_plan
    return PlanChange(sub.plan, new_plan, effective_at=sub.period_end,
                      charge=Money.zero(sub.currency), immediate=False)


def add_seats(sub: Subscription, count: int, now: datetime) -> Money:
    """Add seats now and return the prorated charge."""
    if not sub.plan.is_paid:
        raise ConflictError("the Free plan has no paid seats")
    remaining, total = _proration_days(sub, now)
    charge = proration.seat_add_charge(seat_price_for(sub), count, remaining, total)
    _check_seats(sub.plan, sub.seats + count)
    sub.seats += count
    return charge


def remove_seats(sub: Subscription, count: int, now: datetime, members_in_use: int = 0) -> Money:
    """Remove seats now and return the credit, which is kept for the next invoice."""
    remaining, total = _proration_days(sub, now)
    credit = proration.seat_removal_credit(seat_price_for(sub), count, remaining, total)
    if sub.seats - count < max(members_in_use, 1):
        raise ConflictError("cannot remove seats that members are using",
                            seats=sub.seats, members=members_in_use)
    sub.seats -= count
    sub.pending_credit = (sub.pending_credit or Money.zero(sub.currency)) + credit
    return credit


def cancel(sub: Subscription) -> datetime:
    """Cancel at the period end and return the date the account moves to Free."""
    if not sub.plan.is_paid:
        raise ConflictError("there is no paid subscription to cancel")
    sub.cancel_at_period_end, sub.pending_plan = True, Plan.FREE
    return sub.period_end


def downgrade_to_free(sub: Subscription, now: datetime) -> None:
    """Move to Free at once (cancellation taking effect, or dunning day 44)."""
    sub.plan, sub.pending_plan, sub.cancel_at_period_end = Plan.FREE, None, False
    sub.custom_seat_price = sub.pending_credit = None
    sub.seats = min(sub.seats, limits_for(Plan.FREE).max_members)
    sub.period_start, sub.period_end = now, period_end_for(now, sub.interval)


def roll_period(sub: Subscription, now: datetime) -> bool:
    """Start the next period if the current one is over; apply a pending change.

    Returns True when a new period started. A cancelled subscription moves to
    Free; a scheduled downgrade moves to the lower plan.
    """
    if now < sub.period_end:
        return False
    if sub.cancel_at_period_end or sub.pending_plan is Plan.FREE:
        downgrade_to_free(sub, sub.period_end)
        return True
    if sub.pending_plan is not None:
        sub.plan, sub.pending_plan, sub.custom_seat_price = sub.pending_plan, None, None
    sub.period_start, sub.period_end = sub.period_end, period_end_for(sub.period_end, sub.interval)
    return True

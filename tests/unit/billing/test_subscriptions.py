"""Subscription rules: upgrade now, downgrade at period end, seats, cancel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from acme_cloud.accounts.plans import GB
from acme_cloud.billing import subscriptions as subs
from acme_cloud.billing.models import BillingInterval
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import ConflictError, LimitExceededError, ValidationError
from acme_cloud.common.money import Money

MONTHLY, ANNUAL = BillingInterval.MONTHLY, BillingInterval.ANNUAL


def make_sub(ids, clock, plan=Plan.PRO, interval=MONTHLY, seats=5, **kwargs):
    return subs.new_subscription(ids, "acc_7F3K9Q2M", plan, interval, seats, clock.now(), **kwargs)


@pytest.mark.parametrize(
    "plan, monthly_cents",
    [(Plan.STARTER, 800), (Plan.PRO, 2000), (Plan.BUSINESS, 4500)],
)
def test_annual_billing_costs_ten_times_the_monthly_price(ids, clock, plan, monthly_cents):
    monthly = make_sub(ids, clock, plan, MONTHLY, seats=1)
    annual = make_sub(ids, clock, plan, ANNUAL, seats=1)
    assert subs.period_total(monthly) == Money(monthly_cents)
    assert subs.period_total(annual) == Money(monthly_cents * 10)


def test_period_total_is_seat_price_times_seats(ids, clock):
    assert subs.period_total(make_sub(ids, clock, Plan.PRO, ANNUAL, seats=5)) == Money(100_000)


def test_periods_last_one_month_or_one_year(ids, clock):
    assert make_sub(ids, clock).period_end == datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc)
    assert make_sub(ids, clock, interval=ANNUAL).period_end.year == 2027
    end_of_january = datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert subs.period_end_for(end_of_january, MONTHLY).day == 28


def test_upgrade_is_immediate_and_charges_the_prorated_difference(ids, clock):
    sub = make_sub(ids, clock, Plan.STARTER, seats=4)
    clock.advance(days=15)  # 20 January: 16 of 31 days left
    change = subs.upgrade(sub, Plan.PRO, clock.now())
    assert sub.plan is Plan.PRO
    assert change.immediate and change.effective_at == clock.now()
    assert change.charge == Money(2477)


def test_upgrade_must_go_to_a_higher_plan(ids, clock):
    sub = make_sub(ids, clock, Plan.PRO)
    for target in (Plan.PRO, Plan.STARTER):
        with pytest.raises(ValidationError):
            subs.upgrade(sub, target, clock.now())


def test_enterprise_needs_an_annual_contract_and_a_custom_price(ids, clock):
    with pytest.raises(ValidationError):
        make_sub(ids, clock, Plan.ENTERPRISE, MONTHLY, custom_seat_price=Money(60_000))
    with pytest.raises(ValidationError):
        make_sub(ids, clock, Plan.ENTERPRISE, ANNUAL)
    sub = make_sub(ids, clock, Plan.ENTERPRISE, ANNUAL, seats=20, custom_seat_price=Money(60_000))
    assert subs.period_total(sub) == Money(1_200_000)


def test_downgrade_takes_effect_at_the_end_of_the_period(ids, clock):
    sub = make_sub(ids, clock, Plan.PRO)
    change = subs.schedule_downgrade(sub, Plan.STARTER, members=5, workspaces=1, storage_used_mb=0)
    assert not change.immediate and change.effective_at == sub.period_end
    assert change.charge.is_zero
    assert sub.plan is Plan.PRO  # unchanged until the period ends
    assert subs.roll_period(sub, clock.now()) is False
    clock.advance(days=31)
    assert subs.roll_period(sub, clock.now()) is True
    assert sub.plan is Plan.STARTER and sub.pending_plan is None


@pytest.mark.parametrize(
    "members, workspaces, storage_mb, blockers",
    [
        (10, 1, 50 * GB, []),               # exactly at the Starter limits: allowed
        (11, 1, 0, ["members"]),            # Starter allows 10 members
        (5, 2, 0, ["workspaces"]),          # Starter allows 1 workspace
        (5, 1, 50 * GB + 1, ["storage"]),   # 5 seats x 10 GB = 50 GB
        (11, 3, 60 * GB, ["members", "workspaces", "storage"]),
    ],
)
def test_downgrade_is_blocked_while_usage_exceeds_the_lower_plan(
    ids, clock, members, workspaces, storage_mb, blockers,
):
    sub = make_sub(ids, clock, Plan.PRO, seats=5)
    assert subs.downgrade_blockers(sub, Plan.STARTER, members, workspaces, storage_mb) == blockers
    if blockers:
        with pytest.raises(LimitExceededError) as error:
            subs.schedule_downgrade(sub, Plan.STARTER, members, workspaces, storage_mb)
        assert error.value.code == "ERR_LIMIT_EXCEEDED"
        assert sub.pending_plan is None


def test_adding_seats_is_charged_now_prorated_by_day(ids, clock):
    sub = make_sub(ids, clock, Plan.PRO, seats=5)
    clock.advance(days=15)
    assert subs.add_seats(sub, 2, clock.now()) == Money(2065)  # $40 x 16/31 = $20.645
    assert sub.seats == 7


def test_seats_cannot_exceed_the_plan_member_limit(ids, clock):
    sub = make_sub(ids, clock, Plan.STARTER, seats=10)
    with pytest.raises(LimitExceededError):
        subs.add_seats(sub, 1, clock.now())
    assert sub.seats == 10


def test_removing_seats_gives_a_credit_for_the_next_invoice(ids, clock):
    sub = make_sub(ids, clock, Plan.PRO, seats=5)
    clock.advance(days=15)
    assert subs.remove_seats(sub, 1, clock.now()) == Money(1032)
    assert subs.remove_seats(sub, 1, clock.now()) == Money(1032)
    assert sub.seats == 3 and sub.pending_credit == Money(2064)


def test_seats_in_use_by_members_cannot_be_removed(ids, clock):
    sub = make_sub(ids, clock, Plan.PRO, seats=5)
    with pytest.raises(ConflictError):
        subs.remove_seats(sub, 2, clock.now(), members_in_use=4)


def test_cancel_keeps_the_plan_until_the_period_ends_then_moves_to_free(ids, clock):
    sub = make_sub(ids, clock, Plan.BUSINESS, seats=8)
    assert subs.cancel(sub) == sub.period_end
    clock.advance(days=30)
    subs.roll_period(sub, clock.now())
    assert sub.plan is Plan.BUSINESS  # still inside the paid period
    clock.advance(days=1)
    subs.roll_period(sub, clock.now())
    assert sub.plan is Plan.FREE and not sub.cancel_at_period_end
    assert sub.seats == 3  # Free allows 3 members


def test_free_plan_cannot_be_cancelled(ids, clock):
    with pytest.raises(ConflictError):
        subs.cancel(make_sub(ids, clock, Plan.FREE, seats=1))

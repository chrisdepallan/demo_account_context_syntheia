"""Plans, roles, account states and regions shared by all packages."""

from __future__ import annotations

import pytest

from acme_cloud.common.enums import (
    DEFAULT_REGION, TRIAL_DAYS, TRIAL_PLAN, AccountState, Plan, Region, Role,
)


def test_plans_are_ordered_from_free_to_enterprise():
    assert [p.value for p in Plan] == ["free", "starter", "pro", "business", "enterprise"]
    assert [p.rank for p in Plan] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize(
    ("plan", "other", "expected"),
    [(Plan.PRO, Plan.PRO, True), (Plan.BUSINESS, Plan.PRO, True),
     (Plan.STARTER, Plan.PRO, False), (Plan.FREE, Plan.STARTER, False),
     (Plan.ENTERPRISE, Plan.FREE, True)],
)
def test_at_least_compares_plan_rank(plan, other, expected):
    assert plan.at_least(other) is expected


def test_every_plan_except_free_is_paid():
    assert [p for p in Plan if not p.is_paid] == [Plan.FREE]


def test_new_accounts_trial_pro_for_14_days():
    assert TRIAL_PLAN is Plan.PRO
    assert TRIAL_DAYS == 14


def test_there_are_five_roles():
    assert [r.value for r in Role] == ["owner", "admin", "billing_admin", "member", "guest"]


def test_guests_do_not_use_a_seat():
    assert [r for r in Role if not r.uses_seat] == [Role.GUEST]


def test_there_are_six_account_states():
    assert [s.value for s in AccountState] == [
        "trialing", "active", "past_due", "read_only", "closed", "deleted",
    ]


@pytest.mark.parametrize(
    ("state", "can_edit", "can_log_in"),
    [(AccountState.TRIALING, True, True),
     (AccountState.ACTIVE, True, True),
     (AccountState.PAST_DUE, True, True),
     (AccountState.READ_ONLY, False, True),
     (AccountState.CLOSED, False, False),
     (AccountState.DELETED, False, False)],
)
def test_what_each_state_allows(state, can_edit, can_log_in):
    """read_only accounts can log in but not edit; closed and deleted can do neither."""
    assert state.can_edit is can_edit
    assert state.can_log_in is can_log_in


@pytest.mark.parametrize(
    ("region", "code", "location", "minimum_plan"),
    [(Region.US_EAST, "us-east", "Virginia, USA", Plan.FREE),
     (Region.EU_CENTRAL, "eu-central", "Frankfurt, Germany", Plan.BUSINESS),
     (Region.AP_SOUTH, "ap-south", "Mumbai, India", Plan.ENTERPRISE)],
)
def test_regions(region, code, location, minimum_plan):
    assert region.value == code
    assert region.location == location
    assert region.minimum_plan is minimum_plan


def test_default_region_is_us_east():
    assert DEFAULT_REGION is Region.US_EAST


def test_enums_compare_equal_to_their_string_value():
    """The API sends plain strings; the enums accept them directly."""
    assert Plan("pro") is Plan.PRO
    assert Role.BILLING_ADMIN == "billing_admin"
    assert AccountState("past_due") is AccountState.PAST_DUE
    with pytest.raises(ValueError):
        Plan("platinum")

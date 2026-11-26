"""Plan catalogue: prices, limits and plan-gated features."""

from __future__ import annotations

import pytest

from acme_cloud.accounts import plans
from acme_cloud.accounts.plans import GB, TB, limits_for
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError
from acme_cloud.common.money import Money


def test_size_units():
    """In code, 1 GB = 1,024 MB and 1 TB = 1,024 GB."""
    assert GB == 1024
    assert TB == 1024 * 1024


@pytest.mark.parametrize(
    ("plan", "members", "workspaces", "upload_mb", "history_days", "audit_days", "api_rpm", "webhooks"),
    [(Plan.FREE, 3, 1, 250, 7, 0, 0, 0),
     (Plan.STARTER, 10, 1, 250, 30, 0, 60, 2),
     (Plan.PRO, 100, 3, 5 * GB, 180, 90, 300, 5),
     (Plan.BUSINESS, 500, 10, 5 * GB, 365, 365, 1000, 20),
     (Plan.ENTERPRISE, None, None, 5 * GB, None, 7 * 365, 5000, 50)],
)
def test_plan_limits(plan, members, workspaces, upload_mb, history_days, audit_days, api_rpm, webhooks):
    limits = limits_for(plan)
    assert limits.max_members == members
    assert limits.max_workspaces == workspaces
    assert limits.max_upload_mb == upload_mb
    assert limits.version_history_days == history_days
    assert limits.audit_retention_days == audit_days
    assert limits.api_requests_per_minute == api_rpm
    assert limits.max_webhook_endpoints == webhooks


@pytest.mark.parametrize(
    ("plan", "monthly", "annual"),
    [(Plan.FREE, 0, 0), (Plan.STARTER, 800, 8000), (Plan.PRO, 2000, 20000),
     (Plan.BUSINESS, 4500, 45000)],
)
def test_seat_prices(plan, monthly, annual):
    """Annual billing costs 10 times the monthly price (two months free)."""
    assert plans.seat_price(plan) == Money(monthly)
    assert plans.seat_price(plan, annual=True) == Money(annual)
    assert plans.ANNUAL_MULTIPLIER == 10


def test_eur_prices_use_the_same_number():
    assert plans.seat_price(Plan.PRO, currency="EUR") == Money(2000, "EUR")


def test_enterprise_has_no_list_price():
    with pytest.raises(ValueError):
        plans.seat_price(Plan.ENTERPRISE)


@pytest.mark.parametrize(
    ("plan", "seats", "packs", "expected_mb"),
    [(Plan.FREE, 1, 0, 2 * GB),
     (Plan.FREE, 3, 0, 2 * GB),            # Free is 2 GB in total, not per seat
     (Plan.FREE, 1, 2, 2 * GB),            # packs are for paid plans only
     (Plan.STARTER, 4, 0, 40 * GB),
     (Plan.PRO, 3, 0, 150 * GB),
     (Plan.PRO, 3, 2, 350 * GB),           # each pack adds 100 GB
     (Plan.BUSINESS, 1, 0, 200 * GB),
     (Plan.ENTERPRISE, 2, 0, 2 * TB),
     (Plan.PRO, 0, 0, 50 * GB)],           # an account always has one seat
)
def test_storage_limit(plan, seats, packs, expected_mb):
    assert plans.storage_limit_mb(plan, seats, packs) == expected_mb


def test_storage_pack_is_100_gb_for_10_dollars():
    assert plans.STORAGE_PACK_MB == 100 * GB
    assert plans.STORAGE_PACK_MONTHLY_CENTS == 1000


def test_storage_thresholds():
    assert plans.STORAGE_WARNING_RATIO == 0.90
    assert plans.STORAGE_BLOCK_RATIO == 1.00


@pytest.mark.parametrize(
    ("plan", "seats", "expected"),
    [(Plan.FREE, 1, 5), (Plan.FREE, 3, 5), (Plan.STARTER, 1, 5), (Plan.PRO, 4, 20),
     (Plan.BUSINESS, 10, 50)],
)
def test_guest_limit_is_five_per_paid_seat(plan, seats, expected):
    """Free accounts allow 5 guests in total."""
    assert plans.guest_limit(plan, seats) == expected


@pytest.mark.parametrize(
    ("feature", "minimum_plan"),
    [("api_keys", Plan.STARTER), ("require_mfa", Plan.PRO), ("audit_log", Plan.PRO),
     ("live_chat", Plan.PRO), ("sso", Plan.BUSINESS), ("session_length", Plan.BUSINESS),
     ("phone_support", Plan.BUSINESS), ("region_eu_central", Plan.BUSINESS),
     ("scim", Plan.ENTERPRISE), ("region_ap_south", Plan.ENTERPRISE),
     ("support_24x7", Plan.ENTERPRISE)],
)
def test_feature_is_available_from_its_minimum_plan(feature, minimum_plan):
    for plan in Plan:
        assert plans.has_feature(plan, feature) is plan.at_least(minimum_plan)


def test_require_feature_raises_plan_required_with_details():
    with pytest.raises(PlanRequiredError) as caught:
        plans.require_feature(Plan.PRO, "sso")
    assert caught.value.code == "ERR_PLAN_REQUIRED"
    assert caught.value.details == {
        "feature": "sso", "minimum_plan": "business", "current_plan": "pro",
    }
    plans.require_feature(Plan.BUSINESS, "sso")  # no error


def test_unknown_feature_is_a_programming_error():
    with pytest.raises(KeyError):
        plans.has_feature(Plan.PRO, "teleport")

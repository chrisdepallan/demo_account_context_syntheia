"""Plan catalogue: prices, limits and plan-gated features.

This module is the code copy of the plan tables in
``docs/reference/constants-and-glossary.md``. Other packages read plan
values from here and never hard-code them.
"""

from __future__ import annotations

from dataclasses import dataclass

from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError
from acme_cloud.common.money import Money

MB = 1
GB = 1024 * MB
TB = 1024 * GB

#: ``None`` means unlimited.
UNLIMITED = None

#: Annual billing costs 10 times the monthly price (two months free).
ANNUAL_MULTIPLIER = 10

#: Guests allowed per paid seat, and in total on Free.
GUESTS_PER_SEAT = 5
FREE_GUEST_LIMIT = 5

#: Storage thresholds, as a fraction of the plan's storage.
STORAGE_WARNING_RATIO = 0.90
STORAGE_BLOCK_RATIO = 1.00

#: Storage pack add-on: 100 GB for $10/month on any paid plan.
STORAGE_PACK_MB = 100 * GB
STORAGE_PACK_MONTHLY_CENTS = 1000


@dataclass(frozen=True)
class PlanLimits:
    """Limits for one plan. Sizes are in MB; ``None`` means unlimited."""

    plan: Plan
    monthly_seat_cents: int | None      # None = custom pricing (Enterprise)
    max_members: int | None
    max_workspaces: int | None
    storage_mb: int                     # total on Free, per seat on paid plans
    storage_is_per_seat: bool
    max_upload_mb: int
    version_history_days: int | None
    audit_retention_days: int           # 0 = no audit log
    api_requests_per_minute: int        # 0 = no API
    max_webhook_endpoints: int


PLAN_LIMITS: dict[Plan, PlanLimits] = {
    Plan.FREE: PlanLimits(
        plan=Plan.FREE, monthly_seat_cents=0, max_members=3, max_workspaces=1,
        storage_mb=2 * GB, storage_is_per_seat=False, max_upload_mb=250 * MB,
        version_history_days=7, audit_retention_days=0,
        api_requests_per_minute=0, max_webhook_endpoints=0,
    ),
    Plan.STARTER: PlanLimits(
        plan=Plan.STARTER, monthly_seat_cents=800, max_members=10, max_workspaces=1,
        storage_mb=10 * GB, storage_is_per_seat=True, max_upload_mb=250 * MB,
        version_history_days=30, audit_retention_days=0,
        api_requests_per_minute=60, max_webhook_endpoints=2,
    ),
    Plan.PRO: PlanLimits(
        plan=Plan.PRO, monthly_seat_cents=2000, max_members=100, max_workspaces=3,
        storage_mb=50 * GB, storage_is_per_seat=True, max_upload_mb=5 * GB,
        version_history_days=180, audit_retention_days=90,
        api_requests_per_minute=300, max_webhook_endpoints=5,
    ),
    Plan.BUSINESS: PlanLimits(
        plan=Plan.BUSINESS, monthly_seat_cents=4500, max_members=500, max_workspaces=10,
        storage_mb=200 * GB, storage_is_per_seat=True, max_upload_mb=5 * GB,
        version_history_days=365, audit_retention_days=365,
        api_requests_per_minute=1000, max_webhook_endpoints=20,
    ),
    Plan.ENTERPRISE: PlanLimits(
        plan=Plan.ENTERPRISE, monthly_seat_cents=None, max_members=UNLIMITED,
        max_workspaces=UNLIMITED, storage_mb=1 * TB, storage_is_per_seat=True,
        max_upload_mb=5 * GB, version_history_days=UNLIMITED,
        audit_retention_days=7 * 365, api_requests_per_minute=5000,
        max_webhook_endpoints=50,
    ),
}

#: Feature key -> lowest plan that includes it.
FEATURE_MIN_PLAN: dict[str, Plan] = {
    "api_keys": Plan.STARTER,
    "require_mfa": Plan.PRO,
    "audit_log": Plan.PRO,
    "live_chat": Plan.PRO,
    "sso": Plan.BUSINESS,
    "session_length": Plan.BUSINESS,
    "phone_support": Plan.BUSINESS,
    "region_eu_central": Plan.BUSINESS,
    "scim": Plan.ENTERPRISE,
    "region_ap_south": Plan.ENTERPRISE,
    "support_24x7": Plan.ENTERPRISE,
}


def limits_for(plan: Plan) -> PlanLimits:
    """Return the limits of ``plan``."""
    return PLAN_LIMITS[plan]


def has_feature(plan: Plan, feature: str) -> bool:
    """True when ``plan`` includes ``feature`` (a key of FEATURE_MIN_PLAN)."""
    if feature not in FEATURE_MIN_PLAN:
        raise KeyError(f"unknown feature: {feature}")
    return plan.at_least(FEATURE_MIN_PLAN[feature])


def require_feature(plan: Plan, feature: str) -> None:
    """Raise PlanRequiredError when ``plan`` does not include ``feature``."""
    if not has_feature(plan, feature):
        needed = FEATURE_MIN_PLAN[feature]
        raise PlanRequiredError(
            f"{feature} needs the {needed.value} plan or higher",
            feature=feature, minimum_plan=needed.value, current_plan=plan.value,
        )


def seat_price(plan: Plan, annual: bool = False, currency: str = "USD") -> Money:
    """Price of one seat for one billing period.

    EUR prices use the same number as USD. Enterprise has custom pricing,
    so asking for its list price raises ValueError.
    """
    cents = PLAN_LIMITS[plan].monthly_seat_cents
    if cents is None:
        raise ValueError("Enterprise pricing is custom; there is no list price")
    return Money(cents * (ANNUAL_MULTIPLIER if annual else 1), currency)


def storage_limit_mb(plan: Plan, seats: int, storage_packs: int = 0) -> int:
    """Total storage in MB for an account.

    Free has 2 GB in total. Paid plans have a per-seat amount times the
    number of seats. Each storage pack adds 100 GB (paid plans only).
    """
    limits = PLAN_LIMITS[plan]
    base = limits.storage_mb * (max(seats, 1) if limits.storage_is_per_seat else 1)
    packs = storage_packs if plan.is_paid else 0
    return base + packs * STORAGE_PACK_MB


def guest_limit(plan: Plan, seats: int) -> int:
    """Guests allowed: 5 per paid seat, or 5 in total on Free."""
    return GUESTS_PER_SEAT * seats if plan.is_paid else FREE_GUEST_LIMIT

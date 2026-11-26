"""Regions: which plan may use which region, and the region never changes."""

from __future__ import annotations

import pytest

from acme_cloud.common.enums import Plan, Region
from acme_cloud.common.errors import ConflictError, PlanRequiredError, ValidationError
from acme_cloud.workspaces import regions

US, EU, AP = Region.US_EAST, Region.EU_CENTRAL, Region.AP_SOUTH


@pytest.mark.parametrize(
    ("plan", "expected"),
    [(Plan.FREE, [US]), (Plan.STARTER, [US]), (Plan.PRO, [US]),
     (Plan.BUSINESS, [US, EU]), (Plan.ENTERPRISE, [US, EU, AP])],
)
def test_regions_offered_per_plan(plan, expected):
    """us-east on all plans, eu-central from Business, ap-south on Enterprise only."""
    assert regions.allowed_regions(plan) == expected
    for region in Region:
        assert regions.is_region_allowed(plan, region) is (region in expected)


@pytest.mark.parametrize("plan", list(Plan))
def test_us_east_is_available_on_every_plan(plan):
    regions.require_region(plan, US)  # no error


@pytest.mark.parametrize(
    ("plan", "region", "needed"),
    [(Plan.FREE, EU, "business"), (Plan.STARTER, EU, "business"), (Plan.PRO, EU, "business"),
     (Plan.PRO, AP, "enterprise"), (Plan.BUSINESS, AP, "enterprise")],
)
def test_region_above_the_plan_raises_plan_required(plan, region, needed):
    with pytest.raises(PlanRequiredError) as caught:
        regions.require_region(plan, region)
    assert caught.value.code == "ERR_PLAN_REQUIRED"
    assert caught.value.http_status == 403
    assert caught.value.details == {
        "region": region.value, "minimum_plan": needed, "current_plan": plan.value,
    }


def test_business_can_use_frankfurt_and_enterprise_can_use_mumbai():
    regions.require_region(Plan.BUSINESS, EU)
    regions.require_region(Plan.ENTERPRISE, EU)
    regions.require_region(Plan.ENTERPRISE, AP)


def test_error_message_names_the_location():
    with pytest.raises(PlanRequiredError, match="Mumbai, India"):
        regions.require_region(Plan.BUSINESS, AP)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, US), ("us-east", US), ("eu-central", EU), ("ap-south", AP), (EU, EU)],
)
def test_parse_region(value, expected):
    """No region given means the default, us-east."""
    assert regions.parse_region(value) is expected


@pytest.mark.parametrize("value", ["us-west", "EU-CENTRAL", "", "frankfurt"])
def test_unknown_region_code_is_a_validation_error(value):
    with pytest.raises(ValidationError) as caught:
        regions.parse_region(value)
    assert "us-east, eu-central, ap-south" in caught.value.message


def test_region_cannot_be_changed_after_creation(make_account, make_workspace):
    workspace = make_workspace(make_account(plan=Plan.ENTERPRISE), region=US)
    with pytest.raises(ConflictError) as caught:
        regions.assert_region_unchanged(workspace, "eu-central")
    assert caught.value.code == "ERR_CONFLICT"
    assert caught.value.details["current_region"] == "us-east"
    assert caught.value.details["requested_region"] == "eu-central"
    assert workspace.region is US


def test_asking_for_the_current_region_is_a_no_op(make_account, make_workspace):
    workspace = make_workspace(make_account(plan=Plan.BUSINESS), region=EU)
    regions.assert_region_unchanged(workspace, "eu-central")
    regions.assert_region_unchanged(workspace, EU)
    assert workspace.region is EU


def test_region_change_with_an_unknown_code_is_a_validation_error(make_account, make_workspace):
    workspace = make_workspace(make_account())
    with pytest.raises(ValidationError):
        regions.assert_region_unchanged(workspace, "moon-base")

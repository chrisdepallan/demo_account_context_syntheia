"""Workspace security policy: defaults, plan checks, who may change it, audit."""

from __future__ import annotations

import pytest

from acme_cloud.auth.policies import (
    DEFAULT_POLICY, SecurityPolicy, policy_after_plan_change, update_policy, validate_policy,
)
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import PermissionDeniedError, PlanRequiredError, ValidationError


def test_every_policy_is_off_by_default():
    assert DEFAULT_POLICY == SecurityPolicy(
        require_mfa=False, password_expiry_days=None, web_session_hours=None,
        require_key_expiry=False,
    )
    validate_policy(DEFAULT_POLICY, Plan.FREE)


@pytest.mark.parametrize("plan, allowed", [
    (Plan.FREE, False), (Plan.STARTER, False), (Plan.PRO, True),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_require_mfa_needs_pro_or_higher(plan, allowed):
    policy = SecurityPolicy(require_mfa=True)
    if allowed:
        validate_policy(policy, plan)
    else:
        with pytest.raises(PlanRequiredError) as error:
            validate_policy(policy, plan)
        assert error.value.details["minimum_plan"] == "pro"


@pytest.mark.parametrize("plan, allowed", [
    (Plan.PRO, False), (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_web_session_length_needs_business_or_higher(plan, allowed):
    policy = SecurityPolicy(web_session_hours=12)
    if allowed:
        validate_policy(policy, plan)
    else:
        with pytest.raises(PlanRequiredError):
            validate_policy(policy, plan)


@pytest.mark.parametrize("hours", [0, 337])
def test_web_session_length_must_be_1_hour_to_14_days(hours):
    with pytest.raises(ValidationError):
        validate_policy(SecurityPolicy(web_session_hours=hours), Plan.BUSINESS)


@pytest.mark.parametrize("days, accepted", [(30, True), (60, True), (90, True), (45, False)])
def test_password_expiry_is_30_60_or_90_days_on_any_plan(days, accepted):
    policy = SecurityPolicy(password_expiry_days=days)
    if accepted:
        validate_policy(policy, Plan.FREE)
    else:
        with pytest.raises(ValidationError):
            validate_policy(policy, Plan.FREE)


def test_require_key_expiry_needs_a_plan_with_api_keys():
    policy = SecurityPolicy(require_key_expiry=True)
    with pytest.raises(PlanRequiredError):
        validate_policy(policy, Plan.FREE)
    validate_policy(policy, Plan.STARTER)


@pytest.mark.parametrize("role, allowed", [
    (Role.OWNER, True), (Role.ADMIN, True), (Role.BILLING_ADMIN, False),
    (Role.MEMBER, False), (Role.GUEST, False),
])
def test_only_owners_and_admins_can_change_security_policies(role, allowed):
    if allowed:
        assert update_policy(DEFAULT_POLICY, Plan.PRO, role, require_mfa=True).require_mfa
    else:
        with pytest.raises(PermissionDeniedError):
            update_policy(DEFAULT_POLICY, Plan.PRO, role, require_mfa=True)


def test_update_returns_a_new_policy_and_audits_only_what_changed(audit):
    updated = update_policy(
        DEFAULT_POLICY, Plan.BUSINESS, Role.ADMIN, actor_id="usr_ADMIN001",
        account_id="acc_TEST0001", workspace_id="ws_TEST01", audit=audit,
        require_mfa=True, web_session_hours=8, require_key_expiry=False,
    )
    assert updated == SecurityPolicy(require_mfa=True, web_session_hours=8)
    assert DEFAULT_POLICY.require_mfa is False  # the original is unchanged
    assert audit.events == [(
        "policy.changed", "usr_ADMIN001", "acc_TEST0001", "ws_TEST01",
        {"require_mfa": True, "web_session_hours": 8},
    )]


def test_a_change_that_changes_nothing_is_not_audited(audit):
    update_policy(DEFAULT_POLICY, Plan.PRO, Role.OWNER, audit=audit, require_mfa=False)
    assert audit.events == []


def test_a_rejected_change_is_not_audited(audit):
    with pytest.raises(PlanRequiredError):
        update_policy(DEFAULT_POLICY, Plan.STARTER, Role.OWNER, audit=audit, require_mfa=True)
    assert audit.events == []


def test_unknown_policy_name_is_a_validation_error():
    with pytest.raises(ValidationError):
        update_policy(DEFAULT_POLICY, Plan.PRO, Role.OWNER, require_captcha=True)


def test_downgrade_switches_off_policies_the_new_plan_does_not_include():
    policy = SecurityPolicy(require_mfa=True, password_expiry_days=90, web_session_hours=8,
                            require_key_expiry=True)
    assert policy_after_plan_change(policy, Plan.ENTERPRISE) == policy
    assert policy_after_plan_change(policy, Plan.PRO) == SecurityPolicy(
        require_mfa=True, password_expiry_days=90, require_key_expiry=True)
    assert policy_after_plan_change(policy, Plan.STARTER) == SecurityPolicy(
        password_expiry_days=90, require_key_expiry=True)
    assert policy_after_plan_change(policy, Plan.FREE) == SecurityPolicy(password_expiry_days=90)

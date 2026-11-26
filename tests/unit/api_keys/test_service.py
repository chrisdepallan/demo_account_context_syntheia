"""ApiKeyService: plan and role checks, 25-key limit, shown once, expiry, authenticate."""

from __future__ import annotations

import pytest

from acme_cloud.api_keys import service as service_module
from acme_cloud.api_keys.models import KeyEnvironment, hash_key, is_well_formed
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    LimitExceededError, PermissionDeniedError, PlanRequiredError, UnauthenticatedError,
    ValidationError,
)
from acme_cloud.common.ids import is_valid_id


def test_constants_match_the_facts_sheet():
    assert service_module.MAX_ACTIVE_KEYS_PER_WORKSPACE == 25
    assert service_module.EXPIRY_CHOICES_DAYS == (30, 90, 180, 365)


@pytest.mark.parametrize("plan, allowed", [
    (Plan.FREE, False), (Plan.STARTER, True), (Plan.PRO, True),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_api_keys_need_starter_or_higher(create, plan, allowed):
    if allowed:
        key, _ = create(plan=plan)
        assert is_valid_id(key.id, "key")
    else:
        with pytest.raises(PlanRequiredError) as error:
            create(plan=plan)
        assert error.value.details["minimum_plan"] == "starter"


@pytest.mark.parametrize("role, allowed", [
    (Role.OWNER, True), (Role.ADMIN, True), (Role.BILLING_ADMIN, False),
    (Role.MEMBER, False), (Role.GUEST, False),
])
def test_only_owners_and_admins_can_create_keys(create, role, allowed):
    if allowed:
        create(actor_role=role)
    else:
        with pytest.raises(PermissionDeniedError):
            create(actor_role=role)


def test_full_key_is_returned_once_and_only_hash_and_last_4_are_stored(create, service):
    key, full_key = create(environment=KeyEnvironment.TEST)
    assert is_well_formed(full_key) and full_key.startswith("acme_test_")
    assert key.key_hash == hash_key(full_key)
    assert key.last4 == full_key[-4:]
    assert key.masked == f"acme_test_...{full_key[-4:]}"
    stored = service.get(key.id)
    assert full_key not in repr(stored)
    assert all(full_key not in repr(listed) for listed in service.list_keys("ws_TEST01"))


def test_live_is_the_default_environment(create):
    _, full_key = create()
    assert full_key.startswith("acme_live_")


@pytest.mark.parametrize("days", [30, 90, 180, 365])
def test_expiry_can_be_30_90_180_or_365_days(create, clock, days):
    key, _ = create(expires_in_days=days)
    assert (key.expires_at - clock.now()).days == days


@pytest.mark.parametrize("days", [0, 1, 60, 366])
def test_other_expiry_lengths_are_rejected(create, days):
    with pytest.raises(ValidationError):
        create(expires_in_days=days)


def test_never_is_allowed_unless_require_key_expiry_is_on(create):
    key, _ = create(expires_in_days=None)
    assert key.expires_at is None
    with pytest.raises(ValidationError) as error:
        create(expires_in_days=None, require_key_expiry=True)
    assert error.value.details["policy"] == "require_key_expiry"
    create(expires_in_days=30, require_key_expiry=True)  # an expiring key is still fine


def test_admin_cannot_put_billing_read_on_a_key_but_owner_can(create):
    with pytest.raises(PermissionDeniedError):
        create(actor_role=Role.ADMIN, scopes=["billing:read"])
    key, _ = create(actor_role=Role.OWNER, scopes=["billing:read"])
    assert key.scopes == frozenset({"billing:read"})


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_key_name_is_required_and_limited_to_100_characters(create, name):
    with pytest.raises(ValidationError):
        create(name=name)


def test_workspace_can_have_25_active_keys_but_not_26(create, service):
    for number in range(25):
        create(name=f"key {number}")
    assert len(service.list_keys("ws_TEST01", active_only=True)) == 25
    with pytest.raises(LimitExceededError) as error:
        create(name="key 26")
    assert error.value.code == "ERR_LIMIT_EXCEEDED"
    create(workspace_id="ws_TEST02", name="other workspace")  # the limit is per workspace


def test_revoked_and_expired_keys_do_not_count_towards_the_limit(create, service, clock):
    keys = [create(name=f"key {number}", expires_in_days=365)[0] for number in range(24)]
    create(name="short lived", expires_in_days=30)
    service.revoke(keys[0].id, Plan.PRO, "usr_OWNER001", Role.OWNER)
    create(name="replaces the revoked key", expires_in_days=365)
    clock.advance(days=30)
    create(name="replaces the expired key", expires_in_days=365)
    assert len(service.list_keys("ws_TEST01", active_only=True)) == 25


def test_authenticate_returns_the_scopes_of_a_valid_key(create, service):
    _, full_key = create(scopes=["files:read", "files:write"])
    assert service.authenticate(full_key) == frozenset({"files:read", "files:write"})
    assert service.authenticate(f"Bearer {full_key}") == frozenset({"files:read", "files:write"})


@pytest.mark.parametrize("presented", [
    "", "Bearer ", "acme_live_EXAMPLEEXAMPLEEXAMPLEEXAMPLE0000", "not-a-key",
])
def test_unknown_or_missing_key_is_unauthenticated(service, presented):
    with pytest.raises(UnauthenticatedError) as error:
        service.authenticate(presented)
    assert error.value.code == "ERR_UNAUTHENTICATED"
    assert error.value.http_status == 401


def test_expired_key_is_unauthenticated(create, service, clock):
    _, full_key = create(expires_in_days=30)
    clock.advance(days=29, hours=23)
    assert service.authenticate(full_key)
    clock.advance(hours=1)
    with pytest.raises(UnauthenticatedError):
        service.authenticate(full_key)


def test_creating_a_key_writes_an_audit_event(create, audit):
    key, _ = create(scopes=["projects:write", "projects:read"])
    assert audit.events == [(
        "api_key.created", "usr_OWNER001", "acc_TEST0001", "ws_TEST01",
        {"key_id": key.id, "scopes": ["projects:read", "projects:write"]},
    )]

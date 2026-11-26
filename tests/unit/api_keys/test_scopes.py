"""Scopes: the seven scopes, billing:read restricted to Owner and Billing admin."""

from __future__ import annotations

import pytest

from acme_cloud.api_keys.scopes import (
    ALL_SCOPES, BILLING_READ, grantable_scopes, has_scope, require_scope, validate_scopes,
)
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import PermissionDeniedError, ValidationError


def test_there_are_exactly_seven_scopes():
    assert ALL_SCOPES == (
        "projects:read", "projects:write", "files:read", "files:write",
        "members:read", "members:write", "billing:read",
    )


@pytest.mark.parametrize("role, allowed", [
    (Role.OWNER, True), (Role.BILLING_ADMIN, True),
    (Role.ADMIN, False), (Role.MEMBER, False), (Role.GUEST, False),
])
def test_billing_read_can_be_granted_only_by_owner_or_billing_admin(role, allowed):
    assert (BILLING_READ in grantable_scopes(role)) is allowed
    if allowed:
        assert validate_scopes(["projects:read", BILLING_READ], role) == frozenset(
            {"projects:read", BILLING_READ})
    else:
        with pytest.raises(PermissionDeniedError) as error:
            validate_scopes(["projects:read", BILLING_READ], role)
        assert error.value.code == "ERR_PERMISSION_DENIED"
        assert error.value.details["scopes"] == [BILLING_READ]


def test_admin_can_grant_the_six_other_scopes():
    six = [scope for scope in ALL_SCOPES if scope != BILLING_READ]
    assert grantable_scopes(Role.ADMIN) == six
    assert validate_scopes(six, Role.ADMIN) == frozenset(six)


def test_a_key_needs_at_least_one_scope():
    with pytest.raises(ValidationError):
        validate_scopes([], Role.OWNER)


@pytest.mark.parametrize("scope", ["projects:delete", "billing:write", "admin", "Projects:Read"])
def test_unknown_scopes_are_rejected(scope):
    with pytest.raises(ValidationError) as error:
        validate_scopes(["projects:read", scope], Role.OWNER)
    assert error.value.details["scopes"] == [scope]


def test_duplicate_scopes_collapse():
    assert validate_scopes(["files:read", "files:read"], Role.ADMIN) == frozenset({"files:read"})


def test_scopes_are_exact_write_does_not_include_read():
    granted = frozenset({"projects:write"})
    assert has_scope(granted, "projects:write")
    assert not has_scope(granted, "projects:read")


def test_missing_scope_is_permission_denied_with_http_403():
    with pytest.raises(PermissionDeniedError) as error:
        require_scope({"files:read"}, "files:write")
    assert error.value.http_status == 403
    assert error.value.details["scope"] == "files:write"
    require_scope({"files:read", "files:write"}, "files:write")  # does not raise


def test_requiring_an_unknown_scope_is_a_validation_error():
    with pytest.raises(ValidationError):
        require_scope({"files:read"}, "files:admin")

"""Role and permission matrix ("Who can do what?")."""

from __future__ import annotations

import pytest

from acme_cloud.accounts import permissions
from acme_cloud.accounts.permissions import PERMISSIONS, ROLE_PERMISSIONS, can, require, roles_with
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import PermissionDeniedError, ValidationError

O, A, B, M, G = Role.OWNER, Role.ADMIN, Role.BILLING_ADMIN, Role.MEMBER, Role.GUEST

#: Permission key -> roles that hold it, copied from the facts sheet.
MATRIX = [
    ("projects.edit", {O, A, M}),
    ("comments.write", {O, A, M, G}),
    ("members.manage", {O, A}),
    ("security.manage", {O, A}),
    ("workspace.export", {O, A}),
    ("api_keys.manage", {O, A}),
    ("audit.read", {O, A}),
    ("billing.read", {O, B}),
    ("billing.manage", {O, B}),
    ("account.transfer", {O}),
    ("account.close", {O}),
]


@pytest.mark.parametrize(("permission", "allowed_roles"), MATRIX)
def test_matrix_matches_the_facts_sheet(permission, allowed_roles):
    for role in Role:
        assert can(role, permission) is (role in allowed_roles), (role, permission)
    assert set(roles_with(permission)) == allowed_roles


def test_there_are_eleven_permission_keys():
    assert list(PERMISSIONS) == [permission for permission, _ in MATRIX]


def test_owner_holds_every_permission():
    assert ROLE_PERMISSIONS[Role.OWNER] == frozenset(PERMISSIONS)


def test_admin_cannot_see_or_change_billing():
    assert not can(Role.ADMIN, permissions.BILLING_READ)
    assert not can(Role.ADMIN, permissions.BILLING_MANAGE)


def test_billing_admin_only_has_billing_permissions():
    """A Billing admin cannot edit projects or even comment."""
    assert ROLE_PERMISSIONS[Role.BILLING_ADMIN] == {"billing.read", "billing.manage"}


def test_guest_can_only_comment():
    assert ROLE_PERMISSIONS[Role.GUEST] == {"comments.write"}


@pytest.mark.parametrize("permission", ["account.transfer", "account.close"])
@pytest.mark.parametrize("role", [Role.ADMIN, Role.BILLING_ADMIN, Role.MEMBER, Role.GUEST])
def test_only_the_owner_can_transfer_or_close(role, permission):
    with pytest.raises(PermissionDeniedError):
        require(role, permission)
    require(Role.OWNER, permission)  # no error


def test_require_reports_role_and_permission():
    with pytest.raises(PermissionDeniedError) as caught:
        require(Role.MEMBER, permissions.MEMBERS_MANAGE)
    assert caught.value.code == "ERR_PERMISSION_DENIED"
    assert caught.value.http_status == 403
    assert caught.value.details == {"role": "member", "permission": "members.manage"}


def test_require_passes_silently_when_allowed():
    assert require(Role.ADMIN, permissions.WORKSPACE_EXPORT) is None


def test_unknown_permission_key_is_rejected():
    """A typo must never silently deny or grant access."""
    with pytest.raises(ValidationError):
        can(Role.OWNER, "projects.delete")
    with pytest.raises(ValidationError):
        require(Role.OWNER, "billing.write")


def test_constants_match_the_keys():
    assert permissions.PROJECTS_EDIT == "projects.edit"
    assert permissions.COMMENTS_WRITE == "comments.write"
    assert permissions.SECURITY_MANAGE == "security.manage"
    assert permissions.API_KEYS_MANAGE == "api_keys.manage"
    assert permissions.AUDIT_READ == "audit.read"
    assert permissions.ACCOUNT_TRANSFER == "account.transfer"
    assert permissions.ACCOUNT_CLOSE == "account.close"

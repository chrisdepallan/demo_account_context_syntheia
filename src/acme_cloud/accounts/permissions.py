"""Role and permission matrix.

Acme Cloud has five roles: ``owner``, ``admin``, ``billing_admin``,
``member`` and ``guest``. Each permission key is granted to a fixed set of
roles (this is the code copy of the "Who can do what?" table):

=================== ===== ===== ============= ====== =====
Permission key      Owner Admin Billing admin Member Guest
=================== ===== ===== ============= ====== =====
``projects.edit``   yes   yes   no            yes    no
``comments.write``  yes   yes   no            yes    yes
``members.manage``  yes   yes   no            no     no
``security.manage`` yes   yes   no            no     no
``workspace.export`` yes  yes   no            no     no
``api_keys.manage`` yes   yes   no            no     no
``audit.read``      yes   yes   no            no     no
``billing.read``    yes   no    yes           no     no
``billing.manage``  yes   no    yes           no     no
``account.transfer`` yes  no    no            no     no
``account.close``   yes   no    no            no     no
=================== ===== ===== ============= ====== =====

Things worth remembering:

- The Owner holds every permission.
- An Admin manages people, security, exports, API keys and the audit log but
  cannot see or change billing.
- A Billing admin only sees and pays invoices and changes the plan or the
  payment method; a Billing admin cannot edit projects or even comment.
- Only the Owner can transfer ownership or close the account.
- A Guest can only comment.
"""

from __future__ import annotations

from acme_cloud.common.enums import Role
from acme_cloud.common.errors import PermissionDeniedError, ValidationError

PROJECTS_EDIT = "projects.edit"
COMMENTS_WRITE = "comments.write"
MEMBERS_MANAGE = "members.manage"
SECURITY_MANAGE = "security.manage"
WORKSPACE_EXPORT = "workspace.export"
API_KEYS_MANAGE = "api_keys.manage"
AUDIT_READ = "audit.read"
BILLING_READ = "billing.read"
BILLING_MANAGE = "billing.manage"
ACCOUNT_TRANSFER = "account.transfer"
ACCOUNT_CLOSE = "account.close"

#: Every permission key, in the order of the facts-sheet table.
PERMISSIONS: tuple[str, ...] = (
    PROJECTS_EDIT, COMMENTS_WRITE, MEMBERS_MANAGE, SECURITY_MANAGE,
    WORKSPACE_EXPORT, API_KEYS_MANAGE, AUDIT_READ, BILLING_READ,
    BILLING_MANAGE, ACCOUNT_TRANSFER, ACCOUNT_CLOSE,
)

_ADMIN_PERMISSIONS = frozenset({
    PROJECTS_EDIT, COMMENTS_WRITE, MEMBERS_MANAGE, SECURITY_MANAGE,
    WORKSPACE_EXPORT, API_KEYS_MANAGE, AUDIT_READ,
})

#: Role -> permission keys granted to that role.
ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.OWNER: frozenset(PERMISSIONS),
    Role.ADMIN: _ADMIN_PERMISSIONS,
    Role.BILLING_ADMIN: frozenset({BILLING_READ, BILLING_MANAGE}),
    Role.MEMBER: frozenset({PROJECTS_EDIT, COMMENTS_WRITE}),
    Role.GUEST: frozenset({COMMENTS_WRITE}),
}


def can(role: Role, permission: str) -> bool:
    """True when ``role`` is granted ``permission``.

    Raises ValidationError for a permission key that is not in ``PERMISSIONS``,
    so a typo can never silently deny (or grant) access.
    """
    if permission not in PERMISSIONS:
        raise ValidationError(f"unknown permission: {permission}", permission=permission)
    return permission in ROLE_PERMISSIONS[role]


def require(role: Role, permission: str) -> None:
    """Raise PermissionDeniedError (HTTP 403) unless ``role`` has ``permission``."""
    if not can(role, permission):
        raise PermissionDeniedError(
            f"the {role.value} role does not have the {permission} permission",
            role=role.value, permission=permission,
        )


def roles_with(permission: str) -> list[Role]:
    """Roles that hold ``permission``, for example who may export a workspace."""
    return [role for role in Role if can(role, permission)]

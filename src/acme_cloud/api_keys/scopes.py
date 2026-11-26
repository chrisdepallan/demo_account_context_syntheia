"""API key scopes.

There are seven scopes:

``projects:read``, ``projects:write``, ``files:read``, ``files:write``,
``members:read``, ``members:write`` and ``billing:read``.

Rules:

- A key needs at least one scope; pick only what the integration needs.
- ``billing:read`` can be put on a key only by an **Owner or Billing
  admin**. (Keys are created by Owners and Admins, so in practice an
  Admin cannot add ``billing:read``.)
- Scopes are exact: ``projects:write`` does not include ``projects:read``.
- A request whose key lacks the needed scope gets ``ERR_PERMISSION_DENIED``
  (HTTP 403).
"""

from __future__ import annotations

from typing import Iterable

from acme_cloud.common.enums import Role
from acme_cloud.common.errors import PermissionDeniedError, ValidationError

PROJECTS_READ = "projects:read"
PROJECTS_WRITE = "projects:write"
FILES_READ = "files:read"
FILES_WRITE = "files:write"
MEMBERS_READ = "members:read"
MEMBERS_WRITE = "members:write"
BILLING_READ = "billing:read"

ALL_SCOPES = (
    PROJECTS_READ, PROJECTS_WRITE, FILES_READ, FILES_WRITE,
    MEMBERS_READ, MEMBERS_WRITE, BILLING_READ,
)

#: Scope -> creator roles allowed to grant it. Scopes not listed here can
#: be granted by anyone who may create keys.
RESTRICTED_SCOPES: dict[str, tuple[Role, ...]] = {
    BILLING_READ: (Role.OWNER, Role.BILLING_ADMIN),
}


def grantable_scopes(creator_role: Role) -> list[str]:
    """Scopes shown in the Create key form for ``creator_role``."""
    return [scope for scope in ALL_SCOPES
            if creator_role in RESTRICTED_SCOPES.get(scope, (creator_role,))]


def validate_scopes(scopes: Iterable[str], creator_role: Role) -> frozenset[str]:
    """Check the scopes chosen for a new key and return them as a frozenset.

    Raises ValidationError for an empty list or an unknown scope, and
    PermissionDeniedError when the creator may not grant a scope
    (``billing:read`` by anyone other than an Owner or Billing admin).
    """
    chosen = frozenset(scopes)
    if not chosen:
        raise ValidationError("Choose at least one scope")
    unknown = sorted(chosen - set(ALL_SCOPES))
    if unknown:
        raise ValidationError("Unknown scope", scopes=unknown)
    allowed = set(grantable_scopes(creator_role))
    denied = sorted(chosen - allowed)
    if denied:
        raise PermissionDeniedError(
            "billing:read can be granted only by an Owner or Billing admin", scopes=denied)
    return chosen


def has_scope(granted: Iterable[str], required: str) -> bool:
    """True when ``required`` is one of the key's scopes (exact match)."""
    return required in set(granted)


def require_scope(granted: Iterable[str], required: str) -> None:
    """Raise PermissionDeniedError (HTTP 403) when the key lacks ``required``."""
    if required not in ALL_SCOPES:
        raise ValidationError("Unknown scope", scopes=[required])
    if not has_scope(granted, required):
        raise PermissionDeniedError(f"API key is missing the {required} scope", scope=required)

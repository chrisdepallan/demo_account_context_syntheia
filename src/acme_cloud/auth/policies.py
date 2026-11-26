"""Workspace security policy (Settings -> Security).

One ``SecurityPolicy`` per workspace. Owners and Admins (permission
``security.manage``) can change it; each change writes a
``policy.changed`` audit event.

| Policy | Default | Allowed values | Minimum plan |
|--------|---------|----------------|--------------|
| ``require_mfa`` | off | on / off | Pro |
| ``password_expiry_days`` | off (``None``) | 30, 60 or 90 days | any |
| ``web_session_hours`` | ``None`` (14 days) | 1 to 336 hours (14 days) | Business |
| ``require_key_expiry`` | off | on / off | Starter (needs API keys) |

- **Require MFA** gives users without MFA a 7-day grace period from
  their next login (see ``mfa.py``).
- **Require key expiry** blocks API keys that never expire (see
  ``acme_cloud.api_keys.service``).
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

from acme_cloud.accounts.plans import require_feature
from acme_cloud.auth.passwords import validate_expiry_days
from acme_cloud.auth.sessions import validate_web_session_hours
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import PermissionDeniedError, ValidationError

#: Roles with the ``security.manage`` permission.
SECURITY_MANAGER_ROLES = (Role.OWNER, Role.ADMIN)
POLICY_CHANGED_EVENT = "policy.changed"


@dataclass(frozen=True)
class SecurityPolicy:
    """Security settings of one workspace. The defaults are the product defaults."""

    require_mfa: bool = False
    password_expiry_days: int | None = None
    web_session_hours: int | None = None
    require_key_expiry: bool = False


DEFAULT_POLICY = SecurityPolicy()


def validate_policy(policy: SecurityPolicy, plan: Plan) -> None:
    """Raise when ``policy`` is not allowed on ``plan``.

    PlanRequiredError: Require MFA below Pro, a custom web session length
    below Business, Require key expiry on Free. ValidationError: a
    password expiry other than 30/60/90 days or a session length outside
    1 hour to 14 days.
    """
    if policy.require_mfa:
        require_feature(plan, "require_mfa")
    validate_expiry_days(policy.password_expiry_days)
    validate_web_session_hours(plan, policy.web_session_hours)
    if policy.require_key_expiry:
        require_feature(plan, "api_keys")


def update_policy(current: SecurityPolicy, plan: Plan, actor_role: Role, *,
                  actor_id: str = "", account_id: str = "", workspace_id: str | None = None,
                  audit: object | None = None, **changes: object) -> SecurityPolicy:
    """Return ``current`` with ``changes`` applied, after role and plan checks.

    Example: ``update_policy(policy, Plan.PRO, Role.ADMIN, require_mfa=True)``.
    Only the settings that really changed are listed in the audit event.
    """
    if actor_role not in SECURITY_MANAGER_ROLES:
        raise PermissionDeniedError("Only Owners and Admins can change security policies")
    known = {f.name for f in fields(SecurityPolicy)}
    unknown = set(changes) - known
    if unknown:
        raise ValidationError("Unknown security policy", names=sorted(unknown))
    updated = replace(current, **changes)
    validate_policy(updated, plan)
    changed = {name: getattr(updated, name) for name in sorted(known)
               if getattr(updated, name) != getattr(current, name)}
    if changed and audit is not None:
        audit.record(POLICY_CHANGED_EVENT, actor_id, account_id, workspace_id, **changed)
    return updated


def policy_after_plan_change(policy: SecurityPolicy, new_plan: Plan) -> SecurityPolicy:
    """Switch off the settings that ``new_plan`` does not include.

    Used after a downgrade so that a workspace is never left with a
    policy its plan cannot have.
    """
    result = policy
    if new_plan.rank < Plan.PRO.rank:
        result = replace(result, require_mfa=False)
    if new_plan.rank < Plan.BUSINESS.rank:
        result = replace(result, web_session_hours=None)
    if new_plan.rank < Plan.STARTER.rank:
        result = replace(result, require_key_expiry=False)
    return result

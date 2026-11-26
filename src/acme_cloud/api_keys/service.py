"""API key service: create, list, authenticate, rotate and revoke keys.

Business rules:

- API keys need the **Starter** plan or higher; Free has no API.
- Only **Owners and Admins** manage keys (permission ``api_keys.manage``).
- A workspace can have up to **25 active keys**.
- The full key (``acme_live_`` or ``acme_test_`` plus 32 characters) is
  returned **once**; only its SHA-256 hash and last 4 characters are kept.
- Expiry is **30, 90, 180 or 365 days, or never**. "Never" is blocked
  when the workspace policy **Require key expiry** is on.
- Rotating issues a new key and keeps the old one working for 24 hours;
  revoking takes effect within 60 seconds (see ``rotation.py``).
- Requests send the key as ``Authorization: Bearer <api key>``. A
  missing, unknown, expired or revoked key gets ``ERR_UNAUTHENTICATED``.

Audit events: ``api_key.created``, ``api_key.rotated``, ``api_key.revoked``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from acme_cloud.accounts.plans import require_feature
from acme_cloud.api_keys.models import ApiKey, KeyEnvironment, LAST4_LENGTH, generate_key, hash_key
from acme_cloud.api_keys.rotation import KeyCache, mark_revoked, mark_rotated, send_expiry_warnings
from acme_cloud.api_keys.scopes import validate_scopes
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    ConflictError, LimitExceededError, NotFoundError, PermissionDeniedError,
    UnauthenticatedError, ValidationError,
)
from acme_cloud.common.ids import IdGenerator

MAX_ACTIVE_KEYS_PER_WORKSPACE = 25
#: Expiry choices in days. ``None`` (never) is the fifth option.
EXPIRY_CHOICES_DAYS = (30, 90, 180, 365)
KEY_MANAGER_ROLES = (Role.OWNER, Role.ADMIN)
MAX_KEY_NAME_LENGTH = 100
BEARER_PREFIX = "Bearer "


class ApiKeyService:
    """In-memory API key store with the product's key rules."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None, *,
                 notifier: object | None = None, audit: object | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._notifier = notifier
        self._audit = audit
        self._keys: dict[str, ApiKey] = {}
        self._by_hash: dict[str, str] = {}
        self._cache = KeyCache(clock)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _check_access(plan: Plan, actor_role: Role) -> None:
        require_feature(plan, "api_keys")
        if actor_role not in KEY_MANAGER_ROLES:
            raise PermissionDeniedError("Only Owners and Admins can manage API keys")

    def _audit_event(self, event: str, actor_id: str, key: ApiKey, **metadata: object) -> None:
        if self._audit is not None:
            self._audit.record(event, actor_id, key.account_id, key.workspace_id,
                               key_id=key.id, **metadata)

    def get(self, key_id: str) -> ApiKey:
        if key_id not in self._keys:
            raise NotFoundError("API key not found", key_id=key_id)
        return self._keys[key_id]

    def list_keys(self, workspace_id: str, active_only: bool = False) -> list[ApiKey]:
        """Keys of a workspace, oldest first. Full keys are never listed."""
        now = self._clock.now()
        return [k for k in self._keys.values() if k.workspace_id == workspace_id
                and (not active_only or k.counts_as_active(now))]

    # -- create ----------------------------------------------------------

    def create_key(self, workspace_id: str, account_id: str, plan: Plan, actor_id: str,
                   actor_role: Role, name: str, scopes: Iterable[str],
                   expires_in_days: int | None = None,
                   environment: KeyEnvironment = KeyEnvironment.LIVE,
                   require_key_expiry: bool = False) -> tuple[ApiKey, str]:
        """Create a key and return ``(stored key, full key)``.

        The full key is returned only here. ``expires_in_days`` is 30, 90,
        180, 365 or ``None`` for never; ``None`` is refused when the
        Require key expiry policy is on.
        """
        self._check_access(plan, actor_role)
        name = name.strip()
        if not name or len(name) > MAX_KEY_NAME_LENGTH:
            raise ValidationError("Key name must be 1 to 100 characters")
        chosen = validate_scopes(scopes, actor_role)
        if expires_in_days is None:
            if require_key_expiry:
                raise ValidationError(
                    "Your workspace requires keys to expire. Choose 30, 90, 180 or 365 days.",
                    policy="require_key_expiry")
        elif expires_in_days not in EXPIRY_CHOICES_DAYS:
            raise ValidationError("Expiry must be 30, 90, 180 or 365 days, or never",
                                  value=expires_in_days)
        if len(self.list_keys(workspace_id, active_only=True)) >= MAX_ACTIVE_KEYS_PER_WORKSPACE:
            raise LimitExceededError("A workspace can have up to 25 active API keys",
                                     limit=MAX_ACTIVE_KEYS_PER_WORKSPACE)

        now = self._clock.now()
        full_key = generate_key(environment)
        key = ApiKey(
            id=self._ids.new("key"), workspace_id=workspace_id, account_id=account_id,
            name=name, prefix=environment.prefix, key_hash=hash_key(full_key),
            last4=full_key[-LAST4_LENGTH:], scopes=chosen, created_by=actor_id, created_at=now,
            expires_at=None if expires_in_days is None else now + timedelta(days=expires_in_days),
        )
        self._keys[key.id] = key
        self._by_hash[key.key_hash] = key.id
        self._audit_event("api_key.created", actor_id, key, scopes=sorted(chosen))
        return key, full_key

    # -- authenticate ----------------------------------------------------

    def authenticate(self, presented: str) -> frozenset[str]:
        """Return the scopes of a presented key, or raise UnauthenticatedError.

        ``presented`` is the full key, with or without the ``Bearer ``
        prefix of the Authorization header. Valid lookups are cached for
        60 seconds, which is why a revoked key can work for up to 60
        seconds more.
        """
        full_key = presented[len(BEARER_PREFIX):] if presented.startswith(BEARER_PREFIX) else presented
        key_hash = hash_key(full_key.strip())
        cached = self._cache.get(key_hash)
        if cached is not None:
            return cached.scopes
        key = self._keys.get(self._by_hash.get(key_hash, ""))
        if key is None or not key.is_usable(self._clock.now()):
            raise UnauthenticatedError("API key is missing, invalid, expired or revoked")
        self._cache.put(key_hash, key.id, key.scopes)
        return key.scopes

    # -- rotate, revoke, warn -------------------------------------------

    def rotate(self, key_id: str, plan: Plan, actor_id: str, actor_role: Role,
               require_key_expiry: bool = False) -> tuple[ApiKey, str]:
        """Issue a replacement with the same name, scopes and expiry length.

        The old key keeps working for 24 hours. Returns ``(new key, full key)``.
        """
        self._check_access(plan, actor_role)
        old = self.get(key_id)
        now = self._clock.now()
        if not old.counts_as_active(now):
            raise ConflictError("Only an active key can be rotated", key_id=key_id)
        days = None if old.expires_at is None else (old.expires_at - old.created_at).days
        if days is None and require_key_expiry:
            raise ValidationError("Your workspace requires keys to expire",
                                  policy="require_key_expiry")
        mark_rotated(old, old, now)  # frees the old key's slot before creating
        try:
            new, full_key = self.create_key(
                old.workspace_id, old.account_id, plan, actor_id, actor_role, old.name,
                old.scopes, days, old.environment, require_key_expiry)
        except Exception:
            old.rotated_at = old.grace_ends_at = old.replaced_by = None
            raise
        mark_rotated(old, new, now)
        self._audit_event("api_key.rotated", actor_id, old, new_key_id=new.id)
        return new, full_key

    def revoke(self, key_id: str, plan: Plan, actor_id: str, actor_role: Role) -> ApiKey:
        """Revoke a key. It stops working within 60 seconds."""
        self._check_access(plan, actor_role)
        key = self.get(key_id)
        if key.revoked_at is None:
            mark_revoked(key, self._clock.now())
            self._audit_event("api_key.revoked", actor_id, key)
        return key

    def send_expiry_warnings(self, workspace_id: str, owner_email: str) -> list[ApiKey]:
        """Email the Owner about keys that expire within 14 days (once per key)."""
        return send_expiry_warnings(self.list_keys(workspace_id), self._clock.now(),
                                    owner_email, self._notifier)

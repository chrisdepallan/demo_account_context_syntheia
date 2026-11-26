"""Key rotation, revocation, the key cache and expiry warnings.

Business rules:

- **Rotate**: a new key is issued and the old key keeps working for
  **24 hours**, so integrations can be switched over without downtime.
- **Revoke**: the key stops working within **60 seconds**. API nodes
  cache key lookups, and the cache lifetime is what bounds that delay.
- **Expiry warning**: the Owner is emailed (template ``key_expiring``)
  **14 days** before a key expires, once per key.

INC-2026-006: in one region the cache lifetime was set to 900 seconds
in config, so revoked keys worked for up to 15 minutes. Since release
2026.8 the lifetime is the code constant below and cannot be configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from acme_cloud.api_keys.models import ApiKey
from acme_cloud.common.clock import Clock

#: Lifetime of a cached key lookup. Fixed in code, NOT read from config:
#: see INC-2026-006 (a 900-second config value delayed revocation to 15
#: minutes in ap-south). Revocation must take effect within 60 seconds.
KEY_CACHE_TTL_SECONDS = 60

#: How long the old key keeps working after a rotation.
ROTATION_GRACE_HOURS = 24

#: The Owner is warned this many days before a key expires.
EXPIRY_WARNING_DAYS = 14
KEY_EXPIRING_TEMPLATE = "key_expiring"


def mark_rotated(old_key: ApiKey, new_key: ApiKey, now: datetime) -> None:
    """Start the 24-hour grace period of ``old_key`` after issuing ``new_key``."""
    old_key.rotated_at = now
    old_key.grace_ends_at = now + timedelta(hours=ROTATION_GRACE_HOURS)
    old_key.replaced_by = new_key.id


def mark_revoked(key: ApiKey, now: datetime) -> None:
    """Revoke ``key``. Revoking twice keeps the first revocation time."""
    if key.revoked_at is None:
        key.revoked_at = now


def revocation_effective_by(key: ApiKey) -> datetime | None:
    """Latest moment a revoked key can still be accepted (revoked_at + 60 s)."""
    if key.revoked_at is None:
        return None
    return key.revoked_at + timedelta(seconds=KEY_CACHE_TTL_SECONDS)


def needs_expiry_warning(key: ApiKey, now: datetime) -> bool:
    """True when ``key`` expires within 14 days and no warning was sent yet.

    Keys that never expire, and keys that are revoked, rotated out or
    already expired, are not warned about.
    """
    if key.expires_at is None or key.expiry_warning_sent_at is not None:
        return False
    if not key.counts_as_active(now):
        return False
    return key.expires_at - now <= timedelta(days=EXPIRY_WARNING_DAYS)


def send_expiry_warnings(keys: list[ApiKey], now: datetime, owner_email: str,
                         notifier: object | None = None) -> list[ApiKey]:
    """Send ``key_expiring`` to the Owner for every key that needs it.

    Returns the keys that were warned about. Each key is warned once.
    """
    warned = []
    for key in keys:
        if not needs_expiry_warning(key, now):
            continue
        key.expiry_warning_sent_at = now
        warned.append(key)
        if notifier is not None:
            notifier.send(KEY_EXPIRING_TEMPLATE, [owner_email], key_id=key.id,
                          key_name=key.name, expires_at=key.expires_at.isoformat())
    return warned


@dataclass(frozen=True)
class CachedLookup:
    """A cached "this key hash is valid" answer."""

    key_id: str
    scopes: frozenset[str]
    cached_at: datetime


class KeyCache:
    """Cache of successful key lookups, as used on every API node.

    An entry is served for at most ``KEY_CACHE_TTL_SECONDS`` (60 seconds).
    Only valid keys are cached, so a revoked key is rejected as soon as
    its entry runs out.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._entries: dict[str, CachedLookup] = {}

    def get(self, key_hash: str) -> CachedLookup | None:
        """Return the entry for ``key_hash`` if it is younger than 60 seconds."""
        entry = self._entries.get(key_hash)
        if entry is None:
            return None
        age = self._clock.now() - entry.cached_at
        if age >= timedelta(seconds=KEY_CACHE_TTL_SECONDS):
            del self._entries[key_hash]
            return None
        return entry

    def put(self, key_hash: str, key_id: str, scopes: frozenset[str]) -> None:
        self._entries[key_hash] = CachedLookup(key_id, scopes, self._clock.now())

    def clear(self) -> None:
        self._entries.clear()

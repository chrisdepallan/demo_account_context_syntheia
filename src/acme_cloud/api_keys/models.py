"""API key model and key material helpers.

Business rules (ADR 0005, "Hash API keys and show them once"):

- A key is a prefix plus a **32-character** secret. Production keys start
  with ``acme_live_``, sandbox keys with ``acme_test_``. Example of the
  shape (not a real key): ``acme_test_EXAMPLEEXAMPLEEXAMPLEEXAMPLE0000``.
- Only the **SHA-256 hash** and the **last 4 characters** are stored. The
  full key is shown once, when it is created or rotated.
- Key IDs look like ``key_5T9W3E7Y``.
- A key stops working when it is revoked, when it expires, or 24 hours
  after it was rotated (see ``rotation.py``).
"""

from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

LIVE_PREFIX = "acme_live_"
TEST_PREFIX = "acme_test_"
KEY_SECRET_LENGTH = 32
LAST4_LENGTH = 4

_SECRET_ALPHABET = string.ascii_letters + string.digits


class KeyEnvironment(str, Enum):
    """Production (``acme_live_``) or sandbox (``acme_test_``)."""

    LIVE = "live"
    TEST = "test"

    @property
    def prefix(self) -> str:
        return LIVE_PREFIX if self is KeyEnvironment.LIVE else TEST_PREFIX


def generate_key(environment: KeyEnvironment = KeyEnvironment.LIVE) -> str:
    """Return a new full key: prefix plus 32 random letters and digits."""
    body = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(KEY_SECRET_LENGTH))
    return environment.prefix + body


def hash_key(full_key: str) -> str:
    """SHA-256 hex digest of the full key; this is what the database stores."""
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def is_well_formed(full_key: str) -> bool:
    """True when ``full_key`` has a known prefix and a 32-character secret."""
    for prefix in (LIVE_PREFIX, TEST_PREFIX):
        if full_key.startswith(prefix):
            body = full_key[len(prefix):]
            return len(body) == KEY_SECRET_LENGTH and all(c in _SECRET_ALPHABET for c in body)
    return False


@dataclass
class ApiKey:
    """A stored API key. It never holds the full key, only hash and last 4."""

    id: str
    workspace_id: str
    account_id: str
    name: str
    prefix: str
    key_hash: str
    last4: str
    scopes: frozenset[str]
    created_by: str
    created_at: datetime
    #: ``None`` means the key never expires.
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    #: Set on the old key when it is rotated; it works until ``grace_ends_at``.
    rotated_at: datetime | None = None
    grace_ends_at: datetime | None = None
    replaced_by: str | None = None
    expiry_warning_sent_at: datetime | None = None

    @property
    def environment(self) -> KeyEnvironment:
        return KeyEnvironment.LIVE if self.prefix == LIVE_PREFIX else KeyEnvironment.TEST

    @property
    def masked(self) -> str:
        """How the key is listed in Settings -> API keys, for example ``acme_live_...x7Qp``."""
        return f"{self.prefix}...{self.last4}"

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at

    def in_rotation_grace(self, now: datetime) -> bool:
        """True for a rotated (old) key that still works."""
        return self.grace_ends_at is not None and now < self.grace_ends_at

    def is_usable(self, now: datetime) -> bool:
        """True when a request with this key should be accepted at ``now``."""
        if self.revoked_at is not None or self.is_expired(now):
            return False
        if self.rotated_at is not None:
            return self.in_rotation_grace(now)
        return True

    def counts_as_active(self, now: datetime) -> bool:
        """True when the key counts towards the 25-active-keys limit.

        Revoked, expired and rotated-out keys do not count, so a workspace
        at the limit can still rotate a key.
        """
        return self.revoked_at is None and self.rotated_at is None and not self.is_expired(now)

"""Password rules, hashing, history, expiry and reset links.

Business rules (see ``docs/reference/constants-and-glossary.md``):

- A password is **12 to 128 characters** long.
- It must not be on the breached-password list, must not contain the
  user's email address and must not match any of the last **5 passwords**.
- Passwords are stored only as salted PBKDF2-HMAC-SHA256 hashes.
- A reset link is valid for **60 minutes** and works **once**. Using it
  signs out all other sessions and clears any login lockout (the
  ``AuthService`` does both when it redeems the token).
- The password expiry policy is off by default; an Admin can set it to
  **30, 60 or 90 days**.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from acme_cloud.common.clock import Clock
from acme_cloud.common.errors import ValidationError

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
#: A new password must differ from this many most recent passwords.
PASSWORD_HISTORY_SIZE = 5
#: A reset link works for 60 minutes, and only once.
RESET_TOKEN_TTL_MINUTES = 60
#: Allowed values of the password expiry policy (``None`` means off).
PASSWORD_EXPIRY_CHOICES_DAYS = (30, 60, 90)

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 50_000
SALT_BYTES = 16

#: Small built-in sample of the breached-password list. Production checks
#: a much larger list; the comparison is case-insensitive.
BREACHED_PASSWORDS = frozenset({
    "password1234", "passwordpassword", "qwertyuiop12", "qwertyuiopasdf",
    "letmein12345", "iloveyou1234", "welcome12345", "changeme1234",
    "administrator", "trustno1trustno1", "correcthorsebatterystaple",
})


@dataclass(frozen=True)
class PasswordHash:
    """A salted PBKDF2 hash. The plain password is never stored."""

    salt: str
    digest: str
    iterations: int = PBKDF2_ITERATIONS


@dataclass
class PasswordRecord:
    """A user's current password hash plus the history used for reuse checks."""

    current: PasswordHash
    changed_at: datetime
    #: Most recent first, at most ``PASSWORD_HISTORY_SIZE`` entries,
    #: including the current password.
    history: list[PasswordHash] = field(default_factory=list)


def hash_password(password: str, salt: str | None = None,
                  iterations: int = PBKDF2_ITERATIONS) -> PasswordHash:
    """Hash ``password`` with PBKDF2-HMAC-SHA256 and a random 16-byte salt."""
    salt = salt or secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt), iterations
    )
    return PasswordHash(salt=salt, digest=digest.hex(), iterations=iterations)


def verify_password(password: str, stored: PasswordHash) -> bool:
    """True when ``password`` matches ``stored`` (constant-time comparison)."""
    candidate = hash_password(password, stored.salt, stored.iterations)
    return hmac.compare_digest(candidate.digest, stored.digest)


def validate_password(password: str, email: str,
                      history: list[PasswordHash] | None = None) -> None:
    """Raise ValidationError unless ``password`` meets every password rule.

    Rules: 12 to 128 characters, not on the breached list, does not contain
    the email address, and does not match any of the last 5 passwords.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters", rule="min_length")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValidationError(
            f"Password must be at most {PASSWORD_MAX_LENGTH} characters", rule="max_length")
    if password.lower() in BREACHED_PASSWORDS:
        raise ValidationError("Password appears on a breached-password list", rule="breached")
    if email and email.lower() in password.lower():
        raise ValidationError("Password must not contain your email address", rule="contains_email")
    for old in (history or [])[:PASSWORD_HISTORY_SIZE]:
        if verify_password(password, old):
            raise ValidationError(
                f"Password must not match any of your last {PASSWORD_HISTORY_SIZE} passwords",
                rule="reused",
            )


def set_password(record: PasswordRecord | None, password: str, email: str,
                 now: datetime) -> PasswordRecord:
    """Validate ``password`` and return the updated record (history trimmed to 5)."""
    history = record.history if record else []
    validate_password(password, email, history)
    new_hash = hash_password(password)
    return PasswordRecord(
        current=new_hash, changed_at=now,
        history=([new_hash] + history)[:PASSWORD_HISTORY_SIZE],
    )


def validate_expiry_days(days: int | None) -> None:
    """The expiry policy is ``None`` (off, the default) or 30, 60 or 90 days."""
    if days is not None and days not in PASSWORD_EXPIRY_CHOICES_DAYS:
        raise ValidationError("Password expiry must be off or 30, 60 or 90 days", value=days)


def is_password_expired(record: PasswordRecord, expiry_days: int | None, now: datetime) -> bool:
    """True when the expiry policy is on and the password is at least that old."""
    if expiry_days is None:
        return False
    return now - record.changed_at >= timedelta(days=expiry_days)


@dataclass
class ResetToken:
    """A password reset link. Only the SHA-256 hash of the token is kept."""

    token_hash: str
    user_id: str
    expires_at: datetime
    used_at: datetime | None = None


class PasswordResetManager:
    """Issues and redeems reset links: valid 60 minutes, single use."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tokens: dict[str, ResetToken] = {}

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, user_id: str) -> str:
        """Create a reset token for ``user_id`` and return it (shown once, in the email)."""
        token = secrets.token_urlsafe(32)
        expires = self._clock.now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        self._tokens[self._hash(token)] = ResetToken(self._hash(token), user_id, expires)
        return token

    def redeem(self, token: str) -> str:
        """Mark ``token`` used and return its user ID.

        Raises ValidationError when the token is unknown, already used or
        older than 60 minutes.
        """
        record = self._tokens.get(self._hash(token))
        if record is None:
            raise ValidationError("Reset link is not valid", reason="unknown")
        if record.used_at is not None:
            raise ValidationError("Reset link has already been used", reason="used")
        if self._clock.now() >= record.expires_at:
            raise ValidationError("Reset link has expired", reason="expired")
        record.used_at = self._clock.now()
        return record.user_id

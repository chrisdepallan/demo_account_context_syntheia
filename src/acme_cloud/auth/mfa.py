"""Multi-factor authentication: methods, TOTP, backup codes and the Require MFA grace period.

Business rules:

- Methods are ``totp`` (authenticator app), ``webauthn`` (security key or
  passkey) and ``sms``. SMS is **hidden for Admins and Owners on Business
  and Enterprise** (release 2026.3).
- TOTP follows RFC 6238: HMAC-SHA1, 30-second steps, 6 digits; one step
  either side of the current one is accepted.
- Enrolling gives **10 single-use backup codes**. Generating new codes
  invalidates all the old ones at once.
- The **Require MFA** policy (Pro and above) gives users without MFA a
  **7-day grace period** that starts at their next login. After that they
  must set up MFA before they can continue.
- An Owner or Admin can reset another member's MFA (``mfa.reset`` audit
  event). Support never resets MFA based on email alone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import NotFoundError, PermissionDeniedError, ValidationError

BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 10
REQUIRE_MFA_GRACE_DAYS = 7
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6
#: Steps accepted either side of the current one, to allow for slow typing.
TOTP_WINDOW_STEPS = 1

_BACKUP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class MfaMethod(str, Enum):
    TOTP = "totp"
    WEBAUTHN = "webauthn"
    SMS = "sms"


def available_methods(plan: Plan, role: Role) -> list[MfaMethod]:
    """Methods offered under Profile -> Security for this plan and role.

    SMS is hidden for Admins and Owners on Business and Enterprise.
    """
    methods = [MfaMethod.TOTP, MfaMethod.WEBAUTHN]
    sms_hidden = role in (Role.OWNER, Role.ADMIN) and plan.at_least(Plan.BUSINESS)
    if not sms_hidden:
        methods.append(MfaMethod.SMS)
    return methods


def generate_totp_secret() -> str:
    """Return a new random base32 secret (160 bits) for an authenticator app."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def totp_code(secret: str, at: datetime | int, step: int = TOTP_STEP_SECONDS,
              digits: int = TOTP_DIGITS) -> str:
    """Compute the RFC 6238 code for base32 ``secret`` at time ``at``."""
    seconds = int(at.timestamp()) if isinstance(at, datetime) else int(at)
    counter = struct.pack(">Q", seconds // step)
    mac = hmac.new(base64.b32decode(secret, casefold=True), counter, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    number = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, now: datetime, window: int = TOTP_WINDOW_STEPS) -> bool:
    """True when ``code`` matches the current step or one within ``window`` steps."""
    seconds = int(now.timestamp())
    return any(
        hmac.compare_digest(totp_code(secret, seconds + drift * TOTP_STEP_SECONDS), code.strip())
        for drift in range(-window, window + 1)
    )


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


@dataclass
class MfaEnrollment:
    """One user's MFA setup. Backup codes are stored only as hashes."""

    user_id: str
    method: MfaMethod
    enrolled_at: datetime
    #: TOTP and SMS: base32 secret used to compute codes. WebAuthn: credential ID.
    credential: str = ""
    backup_code_hashes: set[str] = field(default_factory=set)


class MfaManager:
    """Keeps enrollments, verifies codes and tracks the Require MFA grace period."""

    def __init__(self, clock: Clock, audit: object | None = None) -> None:
        self._clock = clock
        self._audit = audit
        self._enrollments: dict[str, MfaEnrollment] = {}
        self._grace_started: dict[str, datetime] = {}

    def is_enrolled(self, user_id: str) -> bool:
        return user_id in self._enrollments

    def get(self, user_id: str) -> MfaEnrollment:
        if user_id not in self._enrollments:
            raise NotFoundError("User has no MFA method", user_id=user_id)
        return self._enrollments[user_id]

    def enroll(self, user_id: str, method: MfaMethod, plan: Plan, role: Role,
               credential: str = "", account_id: str = "") -> tuple[MfaEnrollment, list[str]]:
        """Set up ``method`` and return the enrollment with 10 new backup codes."""
        if method not in available_methods(plan, role):
            raise ValidationError("This MFA method is not available for your role and plan",
                                  method=method.value)
        if method is not MfaMethod.WEBAUTHN and not credential:
            credential = generate_totp_secret()
        enrollment = MfaEnrollment(user_id, method, self._clock.now(), credential)
        self._enrollments[user_id] = enrollment
        self._grace_started.pop(user_id, None)
        if self._audit is not None:
            self._audit.record("mfa.enrolled", user_id, account_id, None, method=method.value)
        return enrollment, self.regenerate_backup_codes(user_id)

    def regenerate_backup_codes(self, user_id: str) -> list[str]:
        """Issue 10 new single-use backup codes; the old ones stop working at once."""
        enrollment = self.get(user_id)
        codes = ["".join(secrets.choice(_BACKUP_ALPHABET) for _ in range(BACKUP_CODE_LENGTH))
                 for _ in range(BACKUP_CODE_COUNT)]
        enrollment.backup_code_hashes = {_hash_code(code) for code in codes}
        return codes

    def verify(self, user_id: str, code: str) -> bool:
        """Check a login code: the method's own code first, then a backup code.

        A backup code is removed when used, so it works only once. WebAuthn
        is modelled simply: the "code" is the registered credential ID.
        SMS codes are computed like TOTP codes and texted to the user.
        """
        enrollment = self.get(user_id)
        if enrollment.method is MfaMethod.WEBAUTHN:
            if hmac.compare_digest(enrollment.credential, code):
                return True
        elif enrollment.credential and code.strip().isdigit():
            if verify_totp(enrollment.credential, code, self._clock.now()):
                return True
        hashed = _hash_code(code)
        if hashed in enrollment.backup_code_hashes:
            enrollment.backup_code_hashes.discard(hashed)
            return True
        return False

    def admin_reset(self, user_id: str, actor_id: str, actor_role: Role,
                    account_id: str = "") -> None:
        """Remove a member's MFA so they can enroll again. Owners and Admins only."""
        if actor_role not in (Role.OWNER, Role.ADMIN):
            raise PermissionDeniedError("Only an Owner or Admin can reset MFA")
        self.get(user_id)
        del self._enrollments[user_id]
        if self._audit is not None:
            self._audit.record("mfa.reset", actor_id, account_id, None, target_user_id=user_id)

    def check_requirement(self, user_id: str) -> datetime | None:
        """Apply the Require MFA policy at login.

        Returns ``None`` for enrolled users. For others the 7-day grace
        period starts at this (their next) login and the deadline is
        returned; once it has passed PermissionDeniedError is raised.
        """
        if self.is_enrolled(user_id):
            return None
        started = self._grace_started.setdefault(user_id, self._clock.now())
        deadline = started + timedelta(days=REQUIRE_MFA_GRACE_DAYS)
        if self._clock.now() >= deadline:
            raise PermissionDeniedError(
                "Your workspace requires MFA. Set it up to continue.",
                mfa_enrollment_required=True,
            )
        return deadline

"""Login lockout after repeated failed attempts.

Business rules:

- **5 failed attempts within 15 minutes** lock login for **15 minutes**.
- **10 failed attempts within 1 hour** lock login for **1 hour** and the
  user is emailed (template ``login_locked``).
- A password reset unlocks the user at once and clears the counters.
- While locked, every login attempt is refused with ``ERR_LOCKED_OUT``
  (HTTP 423) before the password is checked, so it does not count as a
  further failure.

Each lock writes a ``login.locked`` audit event. Failures are counted in
sliding windows; a successful login does not erase earlier failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from acme_cloud.common.clock import Clock
from acme_cloud.common.errors import LockedOutError

SHORT_LOCK_THRESHOLD = 5
SHORT_LOCK_WINDOW = timedelta(minutes=15)
SHORT_LOCK_DURATION = timedelta(minutes=15)

LONG_LOCK_THRESHOLD = 10
LONG_LOCK_WINDOW = timedelta(hours=1)
LONG_LOCK_DURATION = timedelta(hours=1)

LOGIN_LOCKED_TEMPLATE = "login_locked"
LOGIN_LOCKED_EVENT = "login.locked"


@dataclass
class _UserState:
    failures: list[datetime] = field(default_factory=list)
    locked_until: datetime | None = None


class LockoutTracker:
    """Counts failed logins per user and applies the two lockout rules."""

    def __init__(self, clock: Clock, notifier: object | None = None,
                 audit: object | None = None) -> None:
        self._clock = clock
        self._notifier = notifier
        self._audit = audit
        self._state: dict[str, _UserState] = {}

    def locked_until(self, user_id: str) -> datetime | None:
        """Return when the current lock ends, or ``None`` if not locked."""
        state = self._state.get(user_id)
        if state and state.locked_until and self._clock.now() < state.locked_until:
            return state.locked_until
        return None

    def is_locked(self, user_id: str) -> bool:
        return self.locked_until(user_id) is not None

    def check(self, user_id: str) -> None:
        """Raise LockedOutError (with ``retry_after`` seconds) while the user is locked."""
        until = self.locked_until(user_id)
        if until is not None:
            retry_after = int((until - self._clock.now()).total_seconds())
            raise LockedOutError(
                "Too many failed attempts. Try again later or reset your password.",
                retry_after=retry_after, locked_until=until.isoformat(),
            )

    def failures_within(self, user_id: str, window: timedelta) -> int:
        """Number of failed attempts in the last ``window``."""
        state = self._state.get(user_id)
        if not state:
            return 0
        now = self._clock.now()
        return sum(1 for moment in state.failures if now - moment < window)

    def record_failure(self, user_id: str, email: str, account_id: str = "",
                       workspace_id: str | None = None) -> datetime | None:
        """Record one failed attempt and return the lock end time if it caused a lock.

        The 10-in-1-hour rule is checked first because it gives the longer
        lock; it also sends the ``login_locked`` email.
        """
        now = self._clock.now()
        state = self._state.setdefault(user_id, _UserState())
        state.failures = [m for m in state.failures if now - m < LONG_LOCK_WINDOW]
        state.failures.append(now)

        duration: timedelta | None = None
        if self.failures_within(user_id, LONG_LOCK_WINDOW) >= LONG_LOCK_THRESHOLD:
            duration = LONG_LOCK_DURATION
        elif self.failures_within(user_id, SHORT_LOCK_WINDOW) >= SHORT_LOCK_THRESHOLD:
            duration = SHORT_LOCK_DURATION
        if duration is None:
            return None

        state.locked_until = now + duration
        minutes = int(duration.total_seconds() // 60)
        if self._audit is not None:
            self._audit.record(LOGIN_LOCKED_EVENT, user_id, account_id, workspace_id,
                               lock_minutes=minutes)
        if duration == LONG_LOCK_DURATION and self._notifier is not None:
            self._notifier.send(LOGIN_LOCKED_TEMPLATE, [email], user_id=user_id,
                                locked_until=state.locked_until.isoformat())
        return state.locked_until

    def reset(self, user_id: str) -> None:
        """Unlock ``user_id`` and forget the failures (called on password reset)."""
        self._state.pop(user_id, None)

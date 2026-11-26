"""Login sessions and inactivity timeouts.

Business rules:

- A web session ends after **14 days** of inactivity, a mobile session
  after **90 days**.
- Business and Enterprise workspaces can set the web limit to anything
  between **1 hour and 14 days** (the "Web session length" policy). The
  mobile limit cannot be changed.
- "Sign out everywhere" ends every session of a user. A password reset
  uses it to sign out all other sessions.

Session IDs look like ``ses_`` plus 12 characters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from acme_cloud.accounts.plans import require_feature
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import UnauthenticatedError, ValidationError
from acme_cloud.common.ids import IdGenerator

WEB_SESSION_INACTIVITY_DAYS = 14
MOBILE_SESSION_INACTIVITY_DAYS = 90
MIN_WEB_SESSION_HOURS = 1
MAX_WEB_SESSION_HOURS = WEB_SESSION_INACTIVITY_DAYS * 24  # 336


class Device(str, Enum):
    WEB = "web"
    MOBILE = "mobile"


@dataclass
class Session:
    id: str
    user_id: str
    device: Device
    created_at: datetime
    last_active_at: datetime
    revoked_at: datetime | None = None


def validate_web_session_hours(plan: Plan, hours: int | None) -> None:
    """Check a custom web session length.

    ``None`` keeps the 14-day default and is always allowed. A custom
    value needs Business or Enterprise and must be 1 to 336 hours.
    """
    if hours is None:
        return
    require_feature(plan, "session_length")
    if not MIN_WEB_SESSION_HOURS <= hours <= MAX_WEB_SESSION_HOURS:
        raise ValidationError("Web session length must be between 1 hour and 14 days",
                              value=hours)


def inactivity_limit(device: Device, web_session_hours: int | None = None) -> timedelta:
    """How long a session on ``device`` may stay idle before it ends."""
    if device is Device.MOBILE:
        return timedelta(days=MOBILE_SESSION_INACTIVITY_DAYS)
    if web_session_hours is not None:
        return timedelta(hours=web_session_hours)
    return timedelta(days=WEB_SESSION_INACTIVITY_DAYS)


class SessionManager:
    """In-memory session store."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, device: Device = Device.WEB) -> Session:
        """Start a session for a user who has just logged in."""
        now = self._clock.now()
        session = Session(self._ids.new("ses"), user_id, device, now, now)
        self._sessions[session.id] = session
        return session

    def is_active(self, session: Session, web_session_hours: int | None = None) -> bool:
        """True when the session is not signed out and not idle for too long."""
        if session.revoked_at is not None:
            return False
        idle = self._clock.now() - session.last_active_at
        return idle < inactivity_limit(session.device, web_session_hours)

    def touch(self, session_id: str, web_session_hours: int | None = None) -> Session:
        """Validate a session on a request and restart its inactivity timer.

        Raises UnauthenticatedError when the session is unknown, signed
        out or has been idle past its limit.
        """
        session = self._sessions.get(session_id)
        if session is None or not self.is_active(session, web_session_hours):
            raise UnauthenticatedError("Session has ended. Sign in again.")
        session.last_active_at = self._clock.now()
        return session

    def sign_out(self, session_id: str) -> None:
        """End one session."""
        session = self._sessions.get(session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = self._clock.now()

    def sign_out_all(self, user_id: str, except_session_id: str | None = None) -> int:
        """End every session of ``user_id`` and return how many were ended.

        ``except_session_id`` keeps the session the user is working in.
        """
        ended = 0
        for session in self._sessions.values():
            if (session.user_id == user_id and session.id != except_session_id
                    and session.revoked_at is None):
                session.revoked_at = self._clock.now()
                ended += 1
        return ended

    def active_sessions(self, user_id: str, web_session_hours: int | None = None) -> list[Session]:
        """Sessions shown under Profile -> Security -> Devices."""
        return [s for s in self._sessions.values()
                if s.user_id == user_id and self.is_active(s, web_session_hours)]
